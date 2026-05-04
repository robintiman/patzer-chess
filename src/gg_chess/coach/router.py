"""Top-level mode router.

A coaching turn is a (user_id, mode, payload) triple. The router
dispatches to the right mode module, threads the student snapshot
through, and runs sanitizer/auditor on the result before returning.

Modes:
  - qa       : Q&A about an arbitrary position (current teach.py behaviour)
  - review   : walk through a finished game's inflection points
  - puzzle   : present puzzle, judge user's moves, explain
  - lesson   : scripted themed lesson (e.g. "pawn levers")
  - spar     : coach picks a position, plays opposite side, comments
  - opening  : opening trainer over user's repertoire
  - endgame  : drill from a theoretical endgame position
"""
from __future__ import annotations

import sqlite3


# Mode names exposed to the API layer.
MODES = ("qa", "review", "puzzle", "lesson", "spar", "opening", "endgame")


def handle_turn(db: sqlite3.Connection, user_id: str, mode: str, payload: dict) -> dict:
    """Dispatch one coaching turn.

    Returns a mode-specific response dict; the API layer streams it.
    All responses share a common envelope:

        {
          "mode":         str,
          "action":       "text" | "demo" | "puzzle" | "position" | "verdict",
          "data":         dict,           # mode-specific
          "student_diff": dict,           # what changed in the student record
        }

    The router is responsible for:
      - Loading the student snapshot.
      - Selecting the right mode handler.
      - Running coach.sanitizer.verify on any free-form text in the response.
      - Optionally running coach.auditor.audit (configurable per mode).
      - Persisting the student_diff back to the DB.
    """
    raise NotImplementedError
