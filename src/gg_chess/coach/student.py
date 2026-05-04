"""Student model — per-user persistent record of coaching history.

Persisted in SQLite (tables `student_state` and `lesson_progress` —
schemas live in db.py). The student model lets the coach:

  - Avoid repeating positions/themes the user has mastered.
  - Surface concrete claims like "you've blundered a piece in 4/last 10
    tactical positions" with a real audit trail.
  - Resume in-progress lessons across sessions.

This module is the only place the rest of the codebase reads/writes
student data. Routes and modes call into it; they don't query the
SQLite tables directly.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass
class StudentSnapshot:
    user_id: str
    rating_estimate: int
    seen_themes: dict[str, int]            # theme -> times encountered
    weak_themes: list[str]                 # themes with high error rate
    recent_blunders: list[dict]            # last 50 blunders: {fen, theme, cp_loss, ts}
    current_lesson_id: str | None
    current_puzzle_id: str | None


# ── Public API ─────────────────────────────────────────────────────────────────

def load_snapshot(db: sqlite3.Connection, user_id: str) -> StudentSnapshot:
    """Load (or create on first call) the student record for `user_id`."""
    raise NotImplementedError


def record_attempt(
    db: sqlite3.Connection,
    user_id: str,
    *,
    fen: str,
    user_move: str,
    correct: bool,
    cp_loss: int,
    themes: list[str],
    mode: str,                              # "puzzle" | "qa" | "spar" | "lesson" | ...
) -> None:
    """Append one attempt to the student's history.

    Updates aggregate counters (per-theme correct/total) atomically.
    """
    raise NotImplementedError


def update_rating_estimate(db: sqlite3.Connection, user_id: str, delta: int) -> int:
    """Adjust the rating estimate after a puzzle-rated attempt.

    Use a simple Glicko-lite or fixed K-factor (32) Elo update — exact
    formula is fine to choose at impl time, just make it consistent.

    Returns the new rating.
    """
    raise NotImplementedError


def set_current_activity(
    db: sqlite3.Connection,
    user_id: str,
    *,
    lesson_id: str | None = None,
    puzzle_id: str | None = None,
) -> None:
    """Record what the user is currently working on so we can resume."""
    raise NotImplementedError
