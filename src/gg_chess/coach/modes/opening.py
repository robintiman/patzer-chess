"""Mode: opening trainer.

Walks a user's repertoire (a tree of expected moves) and quizzes them at
each branch point. Repertoires are stored per-user in the
`opening_repertoire` table (schema in db.py): one row per (user_id, fen)
with the expected reply.

Two flows:
  - "drill":  start from move 1, follow user's repertoire; if user deviates
              from repertoire, show the expected move + book continuation.
  - "edit":   add/change/remove an expected move at a given FEN.
"""
from __future__ import annotations


def handle(payload: dict, snapshot, db) -> dict:
    """Handle an opening-mode turn.

    Sub-actions:
      - "drill_next":  return the current FEN + book continuation hint (no answer reveal).
      - "drill_move":  judge user's move against repertoire + book; advance.
      - "edit":        upsert an expected move into the repertoire.
      - "list":        list openings in the repertoire grouped by ECO.
    """
    raise NotImplementedError
