"""Mode: puzzle session.

A puzzle session is a small state machine:

  pick_puzzle  → present  → user_move → judge → (correct? next ply : explain & reset)

State lives in `student_state.current_puzzle_id` + `lesson_progress`.

The judge step uses analysis.move_judge.classify_move against the
puzzle's recorded solution AND Stockfish — the puzzle is "solved" when
the user matches the recorded line OR finds an alternative the engine
agrees is just as good (within ~30cp).
"""
from __future__ import annotations


def handle(payload: dict, snapshot, db) -> dict:
    """Handle a puzzle-mode turn.

    Sub-actions (payload.sub_action):
      - "next":  pick a new puzzle (uses student weak themes / rating).
                 Returns {"action":"puzzle", "data": {puzzle_id, fen, side_to_move, theme_hint}}
      - "guess": user submits a move.
                 Returns {"action":"verdict", "data": {correct, expected_san,
                          your_san, cp_loss, explanation, advance: bool}}
      - "hint":  Socratic hint without revealing the answer.
                 Returns {"action":"text", "data": {text}}
      - "give_up": reveal solution and explain.
                 Returns {"action":"text", "data": {solution_san, explanation}}
    """
    raise NotImplementedError


def pick_puzzle_for_user(snapshot, db) -> dict:
    """Sample a puzzle tuned to the student's level and weak themes.

    Strategy:
      - Rating window: snapshot.rating_estimate ± 100.
      - Theme bias: 70% from snapshot.weak_themes if any, 30% mixed.
      - Avoid puzzle_ids already attempted in last 30 days.
    """
    raise NotImplementedError
