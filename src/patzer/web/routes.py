import json
import re
from pathlib import Path

import chess
import chess.engine
import anthropic
from flask import Blueprint, Response, current_app, g, jsonify, request, stream_with_context

from ..config import ANTHROPIC_API_KEY, CLAUDE_MODEL, STOCKFISH_PATH
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


@bp.get("/games")
def list_games():
    username = request.args.get("username", "")
    db = get_db()

    rows = db.execute(
        """
        SELECT g.id, g.game_id, g.source, g.result, g.time_control, g.played_at,
               g.pgn_text, COUNT(p.id) AS error_count
        FROM players pl
        JOIN games g ON g.player_id = pl.id
        LEFT JOIN positions p ON p.game_id = g.id
        WHERE pl.username = ? AND g.analysed = 1
        GROUP BY g.id
        ORDER BY g.played_at DESC
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
        "SELECT pgn_text FROM games WHERE id = ?", (game_db_id,)
    ).fetchone()
    if game_row is None:
        return jsonify({"error": "Game not found"}), 404

    error_rows = db.execute(
        """
        SELECT fen_before, fen_after, player_move, best_move, eval_drop_cp,
               pv_san, concept_name, concept_explanation, move_number
        FROM positions
        WHERE game_id = ?
        ORDER BY move_number
        """,
        (game_db_id,),
    ).fetchall()

    errors = [dict(r) for r in error_rows]
    # Index by fen_before for O(1) frontend lookup
    errors_by_fen = {e["fen_before"]: e for e in errors}

    return jsonify({
        "pgn": game_row["pgn_text"],
        "errors": errors,
        "errors_by_fen": errors_by_fen,
    })


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


@bp.post("/ask")
def ask_claude():
    data = request.get_json(force=True)
    fen = data.get("fen", "")
    player_move = data.get("player_move", "")
    best_move = data.get("best_move", "")
    eval_drop_cp = data.get("eval_drop_cp", 0)
    concept_name = data.get("concept_name", "")
    question = data.get("question", "")

    if not question:
        return jsonify({"error": "question is required"}), 400

    prompt = f"""You are a chess coach helping a player understand their mistakes.

Position (FEN): {fen}
Player's move (UCI): {player_move}
Best move (UCI): {best_move}
Evaluation drop: {eval_drop_cp} centipawns
Concept: {concept_name}

Player's question: {question}

Provide a clear, educational explanation focused on chess improvement. Be concise but thorough."""

    def generate():
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        with client.messages.stream(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                yield f"data: {json.dumps({'text': text})}\n\n"
        yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
