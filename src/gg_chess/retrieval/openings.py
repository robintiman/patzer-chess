"""Opening book lookup.

Two implementation options (pick one in the impl doc):
  A) Polyglot .bin file via python-chess.polyglot. Fast, exact-FEN keys, but
     no opening *names* — just move frequencies.
  B) Lichess Masters / Lichess DB API. Returns names + ECO + frequencies,
     but is a network dependency.

Recommended: A for in-position move suggestions, plus a static ECO -> name
JSON (small, ~500 entries) keyed by truncated FEN for naming.
"""
from __future__ import annotations


# ── LLM tool ───────────────────────────────────────────────────────────────────

def opening_lookup(fen: str) -> dict:
    """Identify the opening at this position and list common continuations.

    Returns:
        {
          "in_book":       bool,
          "eco":           str | null,   # e.g. "C42"
          "name":          str | null,   # e.g. "Petroff Defense, Classical"
          "continuations": [
            {"move_san": str, "move_uci": str, "weight": int, "win_pct_white": float}, ...
          ],
        }

    Args:
        fen: position FEN (full FEN; the lookup canonicalises piece/castling/ep fields).
    """
    raise NotImplementedError
