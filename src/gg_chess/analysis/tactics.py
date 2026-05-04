"""Tactical motif detection.

Two layers:
  1. find_tactics — generic "is this position sharp?" detector. Runs
     Stockfish briefly, returns the eval-swing line.
  2. tag_motif — pattern-match the resulting line against a hand-rolled
     library of motifs (fork, pin, skewer, discovered attack, deflection,
     decoy, removal_of_defender, overload, x_ray, double_attack, mate_threat).

Pure-pattern detection is brittle; the recommended approach is
"engine finds the line, structural rules tag the motif." If no rule fires
the motif is null and the explanation falls back to "engine line, no named
pattern."
"""
from __future__ import annotations

import chess


MOTIFS = (
    "fork",
    "pin",
    "skewer",
    "discovered_attack",
    "discovered_check",
    "double_check",
    "deflection",
    "decoy",
    "removal_of_defender",
    "overload",
    "x_ray",
    "double_attack",
    "back_rank_mate",
    "smothered_mate",
    "mate_threat",
    "trapped_piece",
    "zugzwang",
)


# ── Tools ──────────────────────────────────────────────────────────────────────

def find_tactics(fen: str, depth: int = 12, eval_swing_threshold_cp: int = 150) -> dict:
    """Search for a forcing line that produces a sharp eval swing.

    Strategy:
      1. Run Stockfish at the given depth, multipv=2.
      2. If best line's eval_after - second-best's eval_after >= threshold,
         the position has a tactic; otherwise it's "quiet."
      3. Apply tag_motif() to the PV to label the pattern.

    Returns:
        {
          "has_tactic":      bool,
          "eval_swing_cp":   int,
          "best_pv_san":     [str, ...],
          "best_pv_uci":     [str, ...],
          "second_pv_san":   [str, ...],
          "motif":           str | null,   # one of MOTIFS
          "motif_evidence":  {             # optional structured proof of the tag
            "attacker_square": "f3",
            "targets": [{"piece":"K","square":"g8"},{"piece":"Q","square":"d8"}],
            ...
          } | null,
        }
    """
    raise NotImplementedError


def tag_motif(fen: str, pv_uci: list[str]) -> dict:
    """Classify the tactical motif present in a PV.

    Implementation sketch (in priority order; first match wins):
      - mate-in-1/2 sequences        → mate_threat / back_rank_mate / smothered_mate
      - move that gives check + attacks another piece on a shared line → discovered_check / double_check
      - move that attacks 2+ pieces  → fork / double_attack
      - move that pins a piece to king or higher-value piece → pin (king pin) / skewer
      - move that captures a defender of a hanging target → removal_of_defender
      - move that displaces a defender by sac/threat → deflection / decoy
      - piece with too many duties   → overload
      - long-diagonal / file pressure through own piece → x_ray
      - piece with 0 escape squares + threatened → trapped_piece

    Returns:
        {"motif": str | null, "evidence": dict | null}
    """
    raise NotImplementedError
