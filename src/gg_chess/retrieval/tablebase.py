"""Syzygy endgame tablebase lookup.

Use python-chess's chess.syzygy.open_tablebase(path). Tablebases are
provided as .rtbw / .rtbz files; 6-piece set is ~150GB, 5-piece is ~1GB.
Path is configured via TABLEBASE_PATH in config.py.

If TABLEBASE_PATH is unset or the position has too many pieces, return
{"available": False}.
"""
from __future__ import annotations


# ── LLM tool ───────────────────────────────────────────────────────────────────

def tablebase_lookup(fen: str) -> dict:
    """Exact endgame result + DTZ for ≤7-piece positions.

    Returns:
        {
          "available":    bool,                 # false if no tablebase or > N pieces
          "wdl":          -2 | -1 | 0 | 1 | 2,  # python-chess WDL: loss/blessed-loss/draw/cursed-win/win
          "result":       "win" | "loss" | "draw" | "cursed-win" | "blessed-loss",
          "dtz":          int | null,           # plies to zeroing move
          "best_move_san":str | null,
          "best_move_uci":str | null,
        }
    """
    raise NotImplementedError
