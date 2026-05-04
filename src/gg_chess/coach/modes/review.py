"""Mode: game review.

Two-pass:
  1. Engine pass (already implemented in analysis/engine.analyse_game) finds
     all errors and stores them in `positions`.
  2. Narration pass — for each top-K inflection point (largest win_pct_drop
     spikes), walk the LLM through:
       - position context (describe_position + structure tools)
       - what the player played, what the engine wanted
       - refute(player_move) for the punishment line
       - one-sentence takeaway

This module is the narration pass. The engine pass is upstream.
"""
from __future__ import annotations


def handle(payload: dict, snapshot, db) -> dict:
    """Handle a game-review turn.

    payload:
      {
        "game_db_id":     int,
        "focus_count":    int,    # default 5; how many inflection points to narrate
      }

    Returns the router envelope with:
        "data": {
          "narrations": [
            {"move_number": int, "fen": str, "player_move": str, "best_move": str,
             "verdict": str, "narration": str, "demo_plan": dict|null}
            ...
          ],
          "summary": str
        }
    """
    raise NotImplementedError


def pick_inflection_points(errors: list[dict], k: int) -> list[dict]:
    """Choose the K most teachable error positions.

    Heuristic: rank by win_pct_drop, but penalise neighbours within 2 moves
    (don't narrate two adjacent blunders) and bias toward ones with a
    tagged tactical motif (more concrete to explain).
    """
    raise NotImplementedError
