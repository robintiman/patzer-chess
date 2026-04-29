import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import chess
import chess.engine
from flask import Blueprint, Response, current_app, g, jsonify, request, stream_with_context

from ..analysis.llm import chat_stream
from ..analysis.teach import teach_position
from ..config import STOCKFISH_PATH
from ..db import init_db

bp = Blueprint("api", __name__, url_prefix="/api")


def get_db():
    if "db" not in g:
        db_path: Path = current_app.config["DB_PATH"]
        g.db = init_db(db_path)
    return g.db


@bp.teardown_app_request
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _pgn_header(pgn: str, tag: str) -> str:
    m = re.search(rf'\[{tag} "([^"]+)"\]', pgn)
    return m.group(1) if m else "?"


# TODO: GET /api/patterns?username=<user> — aggregate concept_name counts across positions,
#   grouped by concept_name, with trend (compare last 30 days vs prior 30 days).
#   Powers the PatternInsights sidebar and PATTERN_STATS fixture.

# TODO: GET /api/drills?username=<user> — generate drill suggestions from recurring error
#   patterns (query positions by concept_name frequency, map to drill templates).

# TODO: POST /api/games/<id>/review/judge — evaluate a user-proposed SAN move with Stockfish,
#   return { verdict: "best"|"close"|"inaccurate"|"blunder"|"unknown", note: str, evalAfter: int }.
#   Powers the Judge tab in CoachPanel.

@bp.get("/games")
def list_games():
    username = request.args.get("username", "")
    db = get_db()

    # TODO: Add missing fields to this query:
    #   - oppRating / youRating: parse WhiteElo/BlackElo from pgn_text headers
    #   - opening / ecoCode: parse Opening/ECO from pgn_text headers
    #   - ply: count half-moves from pgn_text and store on games row
    #   - phase: translate game_reviews.phase (null→"unreviewed", "self_analysis"→"in_progress",
    #            "comparison"→"done") and include in response
    rows = db.execute(
        """
        SELECT g.id, g.game_id, g.source, g.result, g.time_control, g.played_at,
               g.pgn_text, g.analysed, COUNT(p.id) AS error_count
        FROM players pl
        JOIN games g ON g.player_id = pl.id
        LEFT JOIN positions p ON p.game_id = g.id
        WHERE pl.username = ?
        GROUP BY g.id
        ORDER BY g.played_at DESC
        LIMIT 50
        """,
        (username,),
    ).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        pgn = d.pop("pgn_text", "") or ""
        white = _pgn_header(pgn, "White")
        black = _pgn_header(pgn, "Black")
        is_white = username.lower() in white.lower()
        d["opponent"] = black if is_white else white
        d["player_color"] = "white" if is_white else "black"
        result.append(d)
    return jsonify(result)


@bp.get("/game/<int:game_db_id>")
def get_game(game_db_id: int):
    db = get_db()

    game_row = db.execute(
        "SELECT pgn_text, analysed FROM games WHERE id = ?", (game_db_id,)
    ).fetchone()
    if game_row is None:
        return jsonify({"error": "Game not found"}), 404

    error_rows = db.execute(
        """
        SELECT fen_before, fen_after, player_move, best_move, eval_drop_cp,
               win_pct_drop, move_classification, pv_san, alt_pvs_san,
               concept_name, concept_explanation, move_number
        FROM positions
        WHERE game_id = ?
        ORDER BY move_number
        """,
        (game_db_id,),
    ).fetchall()

    errors = [dict(r) for r in error_rows]
    # Index by fen_before for O(1) frontend lookup
    errors_by_fen = {e["fen_before"]: e for e in errors}

    eval_rows = db.execute(
        "SELECT half_move_index, eval_cp FROM move_evals WHERE game_id = ? ORDER BY half_move_index",
        (game_db_id,),
    ).fetchall()

    return jsonify({
        "pgn": game_row["pgn_text"],
        "analysed": bool(game_row["analysed"]),
        "errors": errors,
        "errors_by_fen": errors_by_fen,
        "move_evals": [dict(r) for r in eval_rows],
    })


@bp.post("/sync")
def sync_games():
    data = request.get_json(force=True)
    username = data.get("username", "")

    if not username:
        return jsonify({"error": "username required"}), 400

    db_path: Path = current_app.config["DB_PATH"]

    def generate():
        import sqlite3

        from ..ingestion.chesscom import fetch_games
        from ..ingestion.parser import parse_pgn

        def send(event_type, **kwargs):
            return f"data: {json.dumps({'type': event_type, **kwargs})}\n\n"

        db = init_db(db_path)
        db.row_factory = sqlite3.Row

        try:
            yield send("status", message="Fetching games from Chess.com…")
            pgn_list = fetch_games(username)

            db.execute(
                "INSERT OR IGNORE INTO players (username, source) VALUES (?, ?)",
                (username, "chesscom"),
            )
            db.commit()
            player_id = db.execute(
                "SELECT id FROM players WHERE username = ?", (username,)
            ).fetchone()["id"]

            new_games = 0
            for pgn_text in pgn_list:
                game = parse_pgn(pgn_text, username, "chesscom")
                if game is None:
                    continue
                # Chess.com uses [Date "YYYY.MM.DD"] and [StartTime "HH:MM:SS"]
                date = game.headers.get("Date", game.headers.get("UTCDate", "")).replace(".", "-")
                time_ = game.headers.get("StartTime", game.headers.get("UTCTime", ""))
                played_at = (date + " " + time_).strip()
                cur = db.execute(
                    """INSERT OR IGNORE INTO games
                       (player_id, game_id, source, result, time_control, played_at, pgn_text, analysed)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 0)""",
                    (player_id, game.game_id, game.source, game.result,
                     game.time_control, played_at, game.pgn_text),
                )
                db.commit()
                if cur.rowcount > 0:
                    new_games += 1

            yield send("done", new_games=new_games, total=len(pgn_list))
        except Exception as e:
            yield send("error", message=str(e))
        finally:
            db.close()

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@bp.post("/analyse-game/<int:game_db_id>")
def analyse_game_route(game_db_id: int):
    db_path: Path = current_app.config["DB_PATH"]

    def generate():
        import sqlite3

        from ..analysis.engine import analyse_game, sweep_game_evals
        from ..analysis.tactics import identify_tactic
        from ..ingestion.parser import parse_pgn

        def send(event_type, **kwargs):
            return f"data: {json.dumps({'type': event_type, **kwargs})}\n\n"

        db = init_db(db_path)
        db.row_factory = sqlite3.Row

        try:
            row = db.execute(
                """SELECT g.pgn_text, pl.username
                   FROM games g JOIN players pl ON pl.id = g.player_id
                   WHERE g.id = ?""",
                (game_db_id,),
            ).fetchone()
            if row is None:
                yield send("error", message="Game not found")
                return

            game = parse_pgn(row["pgn_text"], row["username"], "chesscom")
            if game is None:
                yield send("error", message="Could not parse PGN")
                return

            yield send("status", message="Running Stockfish analysis…")
            errors = []
            try:
                for event in analyse_game(game):
                    if event["type"] == "progress":
                        yield send("analyzing_move",
                                   half_move_index=event["half_move_index"],
                                   san=event["san"])
                    elif event["type"] == "done":
                        errors = event["errors"]
            except Exception as e:
                yield send("error", message=f"Engine error: {e}")
                return

            yield send("status", message=f"Found {len(errors)} errors — identifying concepts…")

            db.execute("DELETE FROM positions WHERE game_id = ?", (game_db_id,))

            def call_concept(err):
                try:
                    return err, identify_tactic(err, game)
                except Exception as e:
                    import traceback
                    print(f"[identify_tactic] error at move {err.move_number}: {e}")
                    traceback.print_exc()
                    return err, ("", "")

            with ThreadPoolExecutor(max_workers=3) as pool:
                future_to_err = {pool.submit(call_concept, err): err for err in errors}
                for future in as_completed(future_to_err):
                    err, (concept_name, concept_explanation) = future.result()
                    db.execute(
                        """INSERT INTO positions
                           (game_id, move_number, fen_before, fen_after, player_move, best_move,
                            eval_drop_cp, win_pct_drop, move_classification,
                            pv_san, alt_pvs_san, concept_name, concept_explanation)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (game_db_id, err.move_number, err.fen_before, err.fen_after,
                         err.player_move, err.best_move, err.eval_drop_cp,
                         err.win_pct_drop, err.move_classification,
                         " ".join(err.pv_san), json.dumps(err.alt_pvs_san),
                         concept_name, concept_explanation),
                    )
                    yield send("concept_identified",
                               move_number=err.move_number,
                               half_move_index=err.half_move_index,
                               player_move=err.player_move,
                               fen_before=err.fen_before,
                               eval_drop_cp=err.eval_drop_cp,
                               win_pct_drop=err.win_pct_drop,
                               move_classification=err.move_classification,
                               concept_name=concept_name)

            db.execute("UPDATE games SET analysed = 1 WHERE id = ?", (game_db_id,))
            db.commit()

            yield send("status", message="Computing eval graph…")
            move_evals = sweep_game_evals(game)
            db.execute("DELETE FROM move_evals WHERE game_id = ?", (game_db_id,))
            db.executemany(
                "INSERT INTO move_evals (game_id, half_move_index, eval_cp) VALUES (?, ?, ?)",
                [(game_db_id, ev["half_move_index"], ev["eval_cp"]) for ev in move_evals],
            )
            db.commit()

            from ..analysis.interest import score_game_from_db
            score_game_from_db(db, game_db_id)

            yield send("done", error_count=len(errors))
        except Exception as e:
            yield send("error", message=str(e))
        finally:
            db.close()

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@bp.post("/analyse")
def analyse_position():
    data = request.get_json(force=True)
    fen = data.get("fen", "")
    depth = int(data.get("depth", 14))

    try:
        board = chess.Board(fen)
    except ValueError:
        return jsonify({"error": "Invalid FEN"}), 400

    stockfish_path = STOCKFISH_PATH
    try:
        with chess.engine.SimpleEngine.popen_uci(stockfish_path) as engine:
            info = engine.analyse(board, chess.engine.Limit(depth=depth))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    score = info["score"]
    pov_score = score.white()
    eval_cp = pov_score.score(mate_score=10000)

    pv_moves = [m.uci() for m in info.get("pv", [])]
    best_move = pv_moves[0] if pv_moves else None

    return jsonify({
        "eval_cp": eval_cp,
        "best_move": best_move,
        "pv": pv_moves[:5],
    })


@bp.get("/games/<int:game_db_id>/review")
def get_review(game_db_id: int):
    db = get_db()

    review = db.execute(
        "SELECT phase, started_at, completed_at FROM game_reviews WHERE game_id = ?",
        (game_db_id,),
    ).fetchone()

    annotation_rows = db.execute(
        """SELECT move_number, fen_before, user_thought, error_classification, error_type
           FROM move_annotations WHERE game_id = ? ORDER BY move_number""",
        (game_db_id,),
    ).fetchall()

    annotations = {str(r["move_number"]): dict(r) for r in annotation_rows}

    return jsonify({
        "phase": review["phase"] if review else None,
        "started_at": review["started_at"] if review else None,
        "completed_at": review["completed_at"] if review else None,
        "annotations": annotations,
    })


@bp.post("/games/<int:game_db_id>/review/annotate")
def annotate_move(game_db_id: int):
    data = request.get_json(force=True)
    move_number = data.get("move_number")
    fen_before = data.get("fen_before", "")
    user_thought = data.get("user_thought", "")
    error_classification = data.get("error_classification", "")
    error_type = data.get("error_type", "")

    if move_number is None:
        return jsonify({"error": "move_number required"}), 400

    db = get_db()

    db.execute(
        "INSERT OR IGNORE INTO game_reviews (game_id, phase) VALUES (?, 'self_analysis')",
        (game_db_id,),
    )
    db.execute(
        """INSERT INTO move_annotations
           (game_id, move_number, fen_before, user_thought, error_classification, error_type)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(game_id, move_number) DO UPDATE SET
               user_thought = excluded.user_thought,
               error_classification = excluded.error_classification,
               error_type = excluded.error_type,
               annotated_at = CURRENT_TIMESTAMP""",
        (game_db_id, move_number, fen_before, user_thought, error_classification, error_type),
    )
    db.commit()
    return jsonify({"ok": True})


@bp.post("/games/<int:game_db_id>/review/hint")
def get_hint(game_db_id: int):
    data = request.get_json(force=True)
    fen = data.get("fen", "")
    move_number = data.get("move_number", "?")
    player_move = data.get("player_move", "")
    user_thought = data.get("user_thought", "")

    system = (
        "You are a chess coach using the Socratic method. "
        "Your ONLY job is to ask guiding questions that help the player discover the right idea themselves. "
        "NEVER reveal the best move, engine evaluations, centipawn scores, or the solution. "
        "Ask 1-2 short questions that direct attention to the key feature of the position. "
        "Focus on: piece activity, king safety, material threats, or tactical motifs — "
        "but phrase everything as questions, not answers."
    )

    prompt = (
        f"Position (FEN): {fen}\n"
        f"Move number: {move_number}\n"
        f"Player's move (UCI): {player_move}\n"
        f"Player's reasoning: {user_thought or '(not provided)'}\n\n"
        "Ask 1-2 Socratic questions to guide the player without revealing the answer."
    )

    def generate():
        for text in chat_stream(prompt, system=system):
            yield f"data: {json.dumps({'text': text})}\n\n"
        yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@bp.post("/games/<int:game_db_id>/review/compare")
def compare_review(game_db_id: int):
    data = request.get_json(force=True)
    user_annotations = data.get("annotations", [])
    db_path: Path = current_app.config["DB_PATH"]

    def generate():
        import sqlite3

        def send(event_type, **kwargs):
            return f"data: {json.dumps({'type': event_type, **kwargs})}\n\n"

        db = init_db(db_path)
        db.row_factory = sqlite3.Row

        try:
            engine_errors = db.execute(
                """SELECT move_number, player_move, best_move, eval_drop_cp,
                          win_pct_drop, move_classification, concept_name, concept_explanation
                   FROM positions WHERE game_id = ? ORDER BY move_number""",
                (game_db_id,),
            ).fetchall()

            engine_by_move = {r["move_number"]: dict(r) for r in engine_errors}
            annotations_by_move = {a["move_number"]: a for a in user_annotations if "move_number" in a}

            annotated_moves = sorted(set(annotations_by_move.keys()) | set(engine_by_move.keys()))

            for move_num in annotated_moves:
                user = annotations_by_move.get(move_num, {})
                engine = engine_by_move.get(move_num)

                user_thought = user.get("user_thought", "")
                user_class = user.get("error_classification", "")
                user_type = user.get("error_type", "")

                if engine:
                    eng_class = engine["move_classification"]
                    eng_concept = engine["concept_name"]
                    eng_explanation = engine["concept_explanation"]
                    eval_drop = engine["eval_drop_cp"]
                    best_move = engine["best_move"]
                    player_move = engine["player_move"]
                else:
                    eng_class = eng_concept = eng_explanation = best_move = player_move = ""
                    eval_drop = 0

                prompt = (
                    f"Move {move_num}: player played {player_move}, best was {best_move}.\n"
                    f"Engine classification: {eng_class or 'none'} ({eval_drop} cp drop).\n"
                    f"Engine concept: {eng_concept}. {eng_explanation}\n\n"
                    f"Player's self-assessment — classification: {user_class or 'not classified'}, "
                    f"type: {user_type or 'not specified'}, "
                    f"reasoning: {user_thought or 'not provided'}.\n\n"
                    "In 2-3 sentences: compare the player's assessment to reality. "
                    "If they identified the error correctly, affirm it. "
                    "If they missed or misclassified it, explain what they overlooked and why it matters. "
                    "Be direct and educational."
                )

                yield send("feedback", move_number=move_num, engine_classification=eng_class,
                           user_classification=user_class, concept=eng_concept)

                feedback_text = ""
                for text in chat_stream(prompt):
                    feedback_text += text
                    yield f"data: {json.dumps({'type': 'feedback_text', 'move_number': move_num, 'text': text})}\n\n"

            summary_prompt = (
                f"The player just reviewed a chess game with {len(engine_errors)} errors "
                f"and annotated {len(annotations_by_move)} moves. "
                "In 2-3 sentences, give an overall learning takeaway: "
                "what pattern should they focus on improving? Be specific and encouraging."
            )
            yield send("summary_start")
            for text in chat_stream(summary_prompt):
                yield f"data: {json.dumps({'type': 'summary_text', 'text': text})}\n\n"

            db.execute(
                """INSERT INTO game_reviews (game_id, phase, completed_at)
                   VALUES (?, 'comparison', CURRENT_TIMESTAMP)
                   ON CONFLICT(game_id) DO UPDATE SET
                       phase = 'comparison', completed_at = CURRENT_TIMESTAMP""",
                (game_db_id,),
            )
            db.commit()
            yield send("done")

        except Exception as e:
            yield send("error", message=str(e))
        finally:
            db.close()

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@bp.post("/ask")
def ask():
    data = request.get_json(force=True)
    fen = data.get("fen", "")
    player_move = data.get("player_move", "")
    best_move = data.get("best_move", "")
    eval_drop_cp = data.get("eval_drop_cp", 0)
    concept_name = data.get("concept_name", "")
    question = data.get("question", "")
    rating = int(data.get("rating", 1200))

    if not question:
        return jsonify({"error": "question is required"}), 400

    # Infer attacking color from FEN active side
    fen_parts = fen.split(" ")
    player_color = "white" if len(fen_parts) > 1 and fen_parts[1] == "w" else "black"

    # Add position context to the question so Claude has the full picture
    context_question = question
    if player_move or best_move or concept_name:
        parts = []
        if player_move:
            parts.append(f"Player played: {player_move}")
        if best_move:
            parts.append(f"Best move was: {best_move}")
        if eval_drop_cp:
            parts.append(f"Eval drop: {eval_drop_cp}cp")
        if concept_name:
            parts.append(f"Pattern: {concept_name}")
        context_question = question + "\n\n[Context: " + "; ".join(parts) + "]"

    def generate():
        result = teach_position(fen, context_question, player_color, rating)
        if result["action"] == "demo":
            plan = result["plan"]
            yield f"data: {json.dumps({'type': 'plan', 'plan': plan})}\n\n"
            theme = plan.get("theme", "this position")
            for text in chat_stream(f"In one punchy sentence introduce this chess demonstration to the player: {theme}"):
                yield f"data: {json.dumps({'type': 'text', 'text': text})}\n\n"
        else:
            # Yield the pre-generated text directly — don't pipe through chat_stream
            # (chat_stream would treat it as a new prompt and generate a new response)
            yield f"data: {json.dumps({'type': 'text', 'text': result['text']})}\n\n"
        yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
