import json
from pathlib import Path

import anthropic
import chess
import chess.engine

from ..config import ANTHROPIC_API_KEY, CLAUDE_CONCEPT_MODEL, STOCKFISH_PATH
from ..ingestion.parser import Game
from .engine import ErrorPosition

CONCEPTS_FILE = Path(__file__).parent.parent.parent.parent / "chess_concepts.md"


def identify_concept(error_pos: ErrorPosition, game: Game) -> tuple[str, str]:
    """Ask Claude to identify the chess concept missed in this position.

    Claude can interactively query Stockfish to verify hypotheses before naming
    a concept. Returns (concept_name, explanation). Both are empty strings if
    nothing notable is found or if the API call fails.
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    return _identify_concept_claude(error_pos, game)


def _identify_concept_claude(error_pos: ErrorPosition, game: Game) -> tuple[str, str]:
    """Run the Claude tool-use loop to identify the chess concept."""
    board = chess.Board(error_pos.fen_before)
    try:
        player_san = board.san(chess.Move.from_uci(error_pos.player_move))
    except Exception:
        player_san = error_pos.player_move

    pv_str = " ".join(error_pos.pv_san) if error_pos.pv_san else "?"
    user_side = "White" if game.player_color == "white" else "Black"
    move_num = error_pos.move_number

    alt_pvs = error_pos.alt_pvs_san if error_pos.alt_pvs_san else []
    alt_lines_text = ""
    for i, alt_pv in enumerate(alt_pvs, start=2):
        alt_lines_text += f"  Line {i}: {' '.join(alt_pv) if alt_pv else '?'}\n"

    concepts_reference = CONCEPTS_FILE.read_text(encoding="utf-8") if CONCEPTS_FILE.exists() else ""

    prompt = f"""You are an expert chess coach analysing a position where {game.username} ({user_side}) missed an opportunity.

Use the following chess concepts reference when naming concepts:

{concepts_reference}

Position details:
  Move {move_num} — {user_side} played: {player_san}
  FEN: {error_pos.fen_before}
  Evaluation drop: {error_pos.eval_drop_cp} centipawns ({error_pos.win_pct_drop:.1f}% winning chances lost)
  Classification: {error_pos.move_classification}

Stockfish best line: {pv_str}
Alternative lines considered:
{alt_lines_text}
Step 1 — Analyse the position: What are the key threats, weak squares, or tactical motifs present? What does the best line exploit that the alternatives miss?
Step 2 — Name the chess concept most clearly illustrated by the best line.
Step 3 — Write a 1-2 sentence coach explanation mentioning specific moves. Write naturally, as a coach speaking directly to the player. Never mention engines or analysis tools.

You have access to a `query_stockfish` tool. Use it to verify your hypotheses by evaluating specific positions or continuations before naming a concept.

Only flag a concept if it is genuinely and clearly present — the best line should directly illustrate or set up the concept. If no concept is clearly present, use empty strings for name and explanation."""

    query_stockfish_tool = {
        "name": "query_stockfish",
        "description": "Evaluate a chess position with Stockfish. Returns eval in centipawns (from White's perspective), best moves, and principal variation lines.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fen": {"type": "string", "description": "FEN string of the position to evaluate"},
                "depth": {"type": "integer", "description": "Search depth (default 14, max 18)"},
                "multipv": {"type": "integer", "description": "Number of best lines to return (default 3, max 5)"},
            },
            "required": ["fen"],
        },
    }

    report_concept_tool = {
        "name": "report_concept",
        "description": "Report the chess concept identified in the position.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reasoning": {"type": "string", "description": "Step-by-step analysis of the position"},
                "name": {"type": "string", "description": "Name of the chess concept, or empty string if none"},
                "explanation": {"type": "string", "description": "1-2 sentence coach explanation mentioning specific moves, or empty string if no concept"},
            },
            "required": ["reasoning", "name", "explanation"],
        },
    }

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    messages = [{"role": "user", "content": prompt}]

    with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
        engine.configure({"Threads": 2, "Hash": 64})

        for iteration in range(6):  # 5 queries + 1 final report
            response = client.messages.create(
                model=CLAUDE_CONCEPT_MODEL,
                max_tokens=2048,
                temperature=0,
                tools=[query_stockfish_tool, report_concept_tool],
                tool_choice={"type": "auto"},
                messages=messages,
            )
            print(f"[identify_concept] iter={iteration} stop_reason={response.stop_reason}")

            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if not tool_uses:
                break

            report = next((b for b in tool_uses if b.name == "report_concept"), None)
            if report:
                data = report.input
                print(f"[identify_concept] response: {data!r}")
                return (data.get("name", ""), data.get("explanation", ""))

            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for tu in tool_uses:
                if tu.name == "query_stockfish":
                    result = _run_stockfish_query(engine, tu.input)
                    print(f"[identify_concept] stockfish query fen={tu.input.get('fen', '')[:40]} -> eval={result.get('eval_cp')}")
                else:
                    result = {"error": f"Unknown tool: {tu.name}"}
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": json.dumps(result),
                })
            messages.append({"role": "user", "content": tool_results})

    return ("", "")


def _run_stockfish_query(engine, params: dict) -> dict:
    fen = params.get("fen", "")
    depth = min(int(params.get("depth", 14)), 18)
    multipv = min(int(params.get("multipv", 3)), 5)
    try:
        board = chess.Board(fen)
    except Exception as e:
        return {"error": f"Invalid FEN: {e}"}

    results = engine.analyse(board, chess.engine.Limit(depth=depth), multipv=multipv)
    if not isinstance(results, list):
        results = [results]

    pv_lines = []
    best_moves = []
    eval_cp = None

    for i, info in enumerate(results):
        score = info["score"].white().score(mate_score=10000)
        if i == 0:
            eval_cp = score
        pv_moves = []
        temp_board = board.copy()
        for mv in info.get("pv", [])[:8]:
            try:
                pv_moves.append(temp_board.san(mv))
                temp_board.push(mv)
            except Exception:
                break
        pv_lines.append(pv_moves)
        if pv_moves:
            best_moves.append(pv_moves[0])

    return {"eval_cp": eval_cp, "best_moves": best_moves, "pv_lines": pv_lines}
