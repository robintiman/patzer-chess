"""Mode: practice / sparring.

Coach picks a starting position (or uses a user-provided FEN), then plays
the opposite side via Stockfish at a limited skill level matched to the
student's rating. Between moves, the LLM offers one-line commentary.

Key knobs:
  - Skill level: chess.engine.SimpleEngine supports `engine.configure({"Skill Level": 0-20})`
  - UCI_LimitStrength + UCI_Elo for fine-grained rating targeting (Stockfish 16+).
"""
from __future__ import annotations


def handle(payload: dict, snapshot, db) -> dict:
    """Handle a spar-mode turn.

    Sub-actions:
      - "new":    start a sparring game from start_fen + target_elo.
                  Returns {"action":"position", "data":{fen, side_to_move, target_elo}}
      - "move":   user submits SAN/UCI; engine replies; LLM comments.
                  Returns {"action":"position", "data":{fen, engine_move_san,
                           classification_of_user_move, comment}}
      - "resign": end the session, return summary of mistakes.
    """
    raise NotImplementedError
