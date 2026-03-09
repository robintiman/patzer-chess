import json
import re
from pathlib import Path

import anthropic
import chess

from ..config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from ..ingestion.parser import Game
from .engine import ErrorPosition

CONCEPTS_FILE = Path(__file__).parent.parent.parent.parent / "chess_concepts.md"
_PV_MOVES = 8


def identify_concept(error_pos: ErrorPosition, game: Game) -> tuple[str, str]:
    """Ask Claude to identify the chess concept missed in this position.

    Returns (concept_name, explanation). Both are empty strings if nothing notable
    is found or if the API call fails.
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    # Convert player move from UCI to SAN for the prompt
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
  Evaluation drop: {error_pos.eval_drop_cp} centipawns

Stockfish best line: {pv_str}
Alternative lines considered:
{alt_lines_text}
Step 1 — Analyse the position: What are the key threats, weak squares, or tactical motifs present? What does the best line exploit that the alternatives miss?
Step 2 — Name the chess concept most clearly illustrated by the best line.
Step 3 — Write a 1-2 sentence coach explanation mentioning specific moves. Write naturally, as a coach speaking directly to the player. Never mention engines or analysis tools.

Only flag a concept if it is genuinely and clearly present — the best line should directly illustrate or set up the concept. Skip positions with no standout theme.

Respond ONLY with valid JSON:
{{"reasoning": "step-by-step analysis", "name": "concept name", "explanation": "1-2 sentences mentioning specific moves from the best line"}}

If no concept is clearly present, respond with:
{{"reasoning": "no clear concept", "name": "", "explanation": ""}}"""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=512,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    print(f"[identify_concept] raw response: {raw!r}")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[identify_concept] JSON parse error: {e}")
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            return ("", "")

    return (data.get("name", ""), data.get("explanation", ""))
