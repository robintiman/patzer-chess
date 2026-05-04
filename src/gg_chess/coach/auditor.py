"""Claim auditor — second-pass verification of LLM prose.

Where sanitizer.py checks moves, the auditor checks adjectives and
relational claims:

  - "the knight on f5 is unprotected"     → re-run get_square_info
  - "white has a passed pawn on the e-file" → re-run pawn_structure
  - "this is winning for black" (-200cp+) → re-run query_stockfish
  - "the bishop is bad"                   → re-run piece_activity

How it works (cheap path):
  1. Send the draft + the full tool transcript to a small/fast model.
  2. Ask it to emit a JSON list of claims, each tagged
     VERIFIED-BY-TOOL or UNSUPPORTED with a citation.
  3. Reject the draft if any UNSUPPORTED claim is non-trivial; otherwise
     pass it through.

Skip this for casual conversational replies; run it for game review
narration and create_board_demo summaries where errors mislead users.
"""
from __future__ import annotations


def audit(
    draft_text: str,
    tool_transcript: list[dict],
    *,
    strict: bool = False,
) -> dict:
    """Verify chess claims in draft_text against the tool transcript.

    Returns:
        {
          "ok":           bool,
          "claims":       [{"text": str, "status": "verified"|"unsupported", "tool_ref": str|None}, ...],
          "redacted":     str,         # draft_text with UNSUPPORTED claims removed
          "blocking":     bool,        # if True, caller should regenerate rather than redact
        }

    Args:
        strict: if True, any UNSUPPORTED claim makes ok=False. Otherwise
                only "load-bearing" claims (eval/winning, concrete piece
                relations) block.
    """
    raise NotImplementedError
