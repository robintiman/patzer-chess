"""Coach orchestration layer.

The coach package sits ABOVE the analysis tools. It does three things the
raw tool-use loop in analysis/teach.py doesn't:

  1. Routes user requests to the right "mode" (qa, review, puzzle, lesson,
     spar, opening, endgame).
  2. Holds session/student state across turns (what positions they've seen,
     what they got wrong, current lesson).
  3. Validates LLM output against the tool transcript before returning it
     to the user (sanitizer + auditor).

Public entry point: coach.router.handle_turn(user_id, payload).
"""
