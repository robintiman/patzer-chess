"""Mode: free-form Q&A about a position.

This is a refactor of analysis/teach.py:teach_position into the
coach-router framework. Keep the existing implementation as the
reference; the only changes are:

  - System prompt is augmented with structure.describe_position(fen).
  - Tool transcript is passed to coach.sanitizer.verify before returning.
  - Result envelope matches the router contract.
"""
from __future__ import annotations


def handle(payload: dict, snapshot, db) -> dict:
    """Handle a Q&A turn.

    payload:
      {
        "fen":      str,
        "question": str,
      }

    Returns the router envelope: {"mode": "qa", "action": "text"|"demo", "data": ...}.
    """
    raise NotImplementedError
