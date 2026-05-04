"""Engine-grounded move judgment tools.

Every function here calls Stockfish (via the shared engine handle in tools.py)
and returns deterministic numbers. The LLM uses these to grade user candidates,
explain refutations, and never has to "decide" what's good itself.

set_engine() in tools.py must be called before any of these run.
"""
from __future__ import annotations

import chess
import chess.engine

# Centipawn-loss thresholds for move classification (Lichess-style).
# Mirror BLUNDER/MISTAKE/INACCURACY win-pct thresholds in config.py but use
# raw cp here so a single position decision is stateless.
CLASS_BEST = "best"
CLASS_EXCELLENT = "excellent"   # cp_loss < 20
CLASS_GOOD = "good"             # cp_loss < 50
CLASS_INACCURACY = "inaccuracy" # cp_loss < 100
CLASS_MISTAKE = "mistake"       # cp_loss < 200
CLASS_BLUNDER = "blunder"       # cp_loss >= 200


# ── Tools ──────────────────────────────────────────────────────────────────────

def classify_move(fen: str, move: str, depth: int = 14) -> dict:
    """Grade a single move against Stockfish's preferred line.

    Returns:
        {
          "move_san":      str,
          "move_uci":      str,
          "is_legal":      bool,
          "eval_before_cp": int,         # from side-to-move POV
          "eval_after_cp":  int,         # from same POV (so positive = good for the mover)
          "cp_loss":        int,         # max(0, eval_before - eval_after)
          "engine_best_san":  str,
          "engine_best_uci":  str,
          "engine_pv_san":  [str, ...],  # up to 8 plies
          "classification": "best" | "excellent" | "good" | "inaccuracy" | "mistake" | "blunder",
          "is_only_move":  bool,         # second-best is much worse (>= 150 cp gap)
        }

    Args:
        fen: FEN before the move.
        move: UCI ('e2e4') or SAN ('Nf3').
        depth: Stockfish search depth (default 14, capped at 18).
    """
    raise NotImplementedError


def compare_candidates(fen: str, moves: list[str], depth: int = 14) -> dict:
    """Rank a list of candidate moves by Stockfish.

    Use when the user proposes several moves and wants them compared.
    The ranking is by post-move eval (from side-to-move POV).

    Returns:
        {
          "engine_best_san": str,
          "ranked": [
            {"move_san":..., "move_uci":..., "eval_after_cp":int, "cp_loss":int,
             "classification":..., "rank":int},
            ...
          ]
        }
    """
    raise NotImplementedError


def refute(fen: str, move: str, depth: int = 14) -> dict:
    """Find the engine's punishing reply to a (presumably bad) move.

    Returns:
        {
          "move_san":          str,        # the move being refuted
          "fen_after":         str,
          "refutation_san":    str,        # opponent's best reply
          "refutation_uci":    str,
          "refutation_pv_san": [str,...],  # 4-8 plies showing the punishment
          "tactical_motif":    str | null, # tag from tactics.find_tactics if applicable
          "eval_swing_cp":     int,        # eval before vs eval after refutation, side-to-move POV
        }

    Use when explaining "why was my move bad?" — the answer is almost
    always a concrete forcing sequence, not an abstract weakness.
    """
    raise NotImplementedError


def find_threats(fen: str, depth: int = 12) -> dict:
    """Identify what the opponent would play if it were their move.

    Implementation hint: flip the side-to-move bit in the FEN (a "null move"
    isn't quite legal in python-chess, so build the mirror FEN manually) and
    run a Stockfish search. Surface the top reply + tactical_motif tag.

    Returns:
        {
          "threats": [
            {"move_san":..., "move_uci":..., "eval_after_cp":int,
             "tactical_motif": str | null, "pv_san":[str,...]}
          ],
          "best_defence": {"move_san":..., "move_uci":...} | null,
        }
    """
    raise NotImplementedError


def mate_search(fen: str, max_n: int = 5) -> dict:
    """Search for a forced mate up to max_n moves.

    Returns:
        {
          "found":   bool,
          "mate_in": int | null,         # in moves (not plies)
          "pv_san":  [str, ...],
          "pv_uci":  [str, ...],
        }

    Args:
        max_n: cap on mate length (in full moves). Larger values cost more.
    """
    raise NotImplementedError
