"""Mode: themed lesson.

A lesson is a hand-authored JSON file under data/lessons/<id>.json:

    {
      "id":    "iqp-basics",
      "title": "Isolated Queen's Pawn — strengths & weaknesses",
      "rating_band": [1000, 1600],
      "steps": [
        {"type": "explain", "fen": "...", "narration": "..."},
        {"type": "quiz",    "fen": "...", "prompt": "...", "expected_uci": "...",
         "alternatives_ok": ["..."], "explanation_correct": "...", "explanation_wrong": "..."},
        ...
      ],
      "summary": "..."
    }

The lesson is mostly scripted; the LLM only fills in adaptive feedback
on quiz answers and final summary tone.
"""
from __future__ import annotations


def handle(payload: dict, snapshot, db) -> dict:
    """Handle a lesson-mode turn.

    Sub-actions:
      - "list":   return available lessons appropriate for student rating
      - "start":  begin a lesson by id (resumes if in progress)
      - "next":   advance to next step
      - "answer": submit a quiz answer; return verdict + LLM feedback
    """
    raise NotImplementedError


def load_lesson(lesson_id: str) -> dict:
    """Load lesson JSON from disk; raise FileNotFoundError if missing."""
    raise NotImplementedError
