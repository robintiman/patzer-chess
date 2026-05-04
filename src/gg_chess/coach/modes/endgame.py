"""Mode: endgame drill.

Start the user from a known theoretical endgame position (KQ vs K, KR vs K,
Lucena, Philidor, opposition pawn endings, etc.) and require them to
convert against Stockfish. Use the tablebase for ground-truth feedback:
every user move is judged against the perfect tablebase reply.

Drill positions live in data/endgames/<id>.json:

    {
      "id":    "lucena",
      "title": "Lucena Position (rook ending)",
      "fen":   "...",
      "goal":  "win as white",
      "max_moves": 20,
    }
"""
from __future__ import annotations


def handle(payload: dict, snapshot, db) -> dict:
    """Handle an endgame-drill turn.

    Sub-actions:
      - "start": load a drill by id; return position.
      - "move":  user plays a move; judge via tablebase_lookup; advance.
                 If user move worsens DTZ significantly, surface the better move.
      - "give_up": reveal the winning plan + walk through the tablebase line.
    """
    raise NotImplementedError
