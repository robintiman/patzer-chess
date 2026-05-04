"""Move-token sanitizer.

The LLM is forbidden from inventing moves. This module enforces that by:

  1. Extracting every SAN/UCI-shaped token from the LLM's final text.
  2. Verifying each token (a) parses as a real chess move and (b) appeared
     in a tool-call result this turn (Stockfish PV, apply_move return,
     puzzle.moves_uci, etc.).
  3. Returning either OK or a list of unsupported tokens; the caller then
     re-prompts the LLM with the violations or strips them.

This generalises the create_board_demo validation already done in teach.py.
"""
from __future__ import annotations

import re

# Loose patterns — false positives are OK because we re-validate against the
# tool transcript. False NEGATIVES (missing a real move token) are bad.
_SAN_PATTERN = re.compile(
    r"\b("
    r"O-O-O|O-O|"                                    # castling
    r"[KQRBN][a-h]?[1-8]?x?[a-h][1-8](=[QRBN])?[+#]?|"  # piece move
    r"[a-h]x?[a-h][1-8](=[QRBN])?[+#]?|"             # pawn move/cap
    r"[a-h][1-8](=[QRBN])?[+#]?"                      # plain pawn push
    r")\b"
)
_UCI_PATTERN = re.compile(r"\b([a-h][1-8][a-h][1-8][qrbn]?)\b")


def extract_move_tokens(text: str) -> list[str]:
    """Pull every move-shaped substring out of LLM prose.

    Returns a deduplicated, order-preserving list.
    """
    raise NotImplementedError


def collect_supported_moves(tool_transcript: list[dict]) -> set[str]:
    """Build the set of moves the LLM is allowed to mention.

    `tool_transcript` is the list of {tool_name, args, result} dicts
    accumulated during the tool-use loop. We pull moves out of:
      - query_stockfish.pv_lines
      - apply_move.move_san / .fen_after
      - classify_move.engine_pv_san / .move_san
      - refute.refutation_pv_san
      - find_tactics.best_pv_san
      - puzzle_search.puzzles[].moves_uci
      - opening_lookup.continuations[].move_san
      - mate_search.pv_san

    Returns SAN AND UCI representations for each move (callers compare loosely).
    """
    raise NotImplementedError


def verify(text: str, tool_transcript: list[dict], starting_fen: str) -> dict:
    """Top-level check: does the text only mention supported moves?

    Returns:
        {
          "ok":          bool,
          "violations":  [{"token": str, "reason": str}, ...],
          "supported":   [str, ...],   # moves the LLM did mention that are fine
        }
    """
    raise NotImplementedError
