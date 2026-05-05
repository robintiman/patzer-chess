"""Engine-grounded move judgment tools.

Every function here calls Stockfish (via the shared engine handle in tools.py)
and returns deterministic numbers. The LLM uses these to grade user candidates,
explain refutations, and never has to "decide" what's good itself.

set_engine() in tools.py must be called before any of these run.

Classification convention: win_pct_drop (Lichess methodology). Reuses
cp_to_win_pct + _classify_drop from analysis/engine.py so the whole
codebase agrees on what a "blunder" is.
"""
from __future__ import annotations

import chess
import chess.engine

from . import tools as _tools
from .engine import _classify_drop, cp_to_win_pct

CLASS_BEST = "best"
CLASS_EXCELLENT = "excellent"   # win_pct_drop < 2
CLASS_GOOD = "good"             # win_pct_drop < INACCURACY_WIN_PCT_THRESHOLD
CLASS_INACCURACY = "inaccuracy"
CLASS_MISTAKE = "mistake"
CLASS_BLUNDER = "blunder"
CLASS_ILLEGAL = "illegal"

_MAX_DEPTH = 18
_ONLY_MOVE_GAP_CP = 150         # second-best is this much worse → it's the only move


# ── Tools ──────────────────────────────────────────────────────────────────────

def classify_move(fen: str, move: str, depth: int = 14) -> dict:
    """Grade a single move against Stockfish's preferred line.

    Returns:
        {
          "move_san":      str,
          "move_uci":      str,
          "is_legal":      bool,
          "eval_before_cp": int,           # from MOVER POV (positive = mover is winning)
          "eval_after_cp":  int | null,    # same POV; null if move is illegal
          "cp_loss":        int | null,    # max(0, eval_before - eval_after)
          "win_pct_drop":   float | null,  # Lichess sigmoid drop, 0-100
          "engine_best_san":  str,
          "engine_best_uci":  str,
          "engine_pv_san":  [str, ...],    # up to 8 plies
          "classification": "best" | "excellent" | "good" | "inaccuracy" | "mistake" | "blunder" | "illegal",
          "is_only_move":  bool,           # second-best PV is >= 150 cp worse
        }

    Args:
        fen: FEN before the move.
        move: UCI ('e2e4') or SAN ('Nf3').
        depth: Stockfish search depth (default 14, capped at 18).
    """
    if _tools._engine is None:
        raise RuntimeError("classify_move requires tools.set_engine() to have been called")
    depth = min(int(depth), _MAX_DEPTH)
    board = chess.Board(fen)

    chess_move = _parse_move(board, move)
    is_legal = chess_move is not None and chess_move in board.legal_moves
    move_uci = chess_move.uci() if chess_move is not None else move
    move_san = board.san(chess_move) if is_legal else move

    # Eval before — multipv=2 to detect "only move"
    before = _tools._engine.analyse(board, chess.engine.Limit(depth=depth), multipv=2)
    if not isinstance(before, list):
        before = [before]
    eval_before_white = before[0]["score"].white().score(mate_score=10000) or 0
    engine_pv = before[0].get("pv", [])
    engine_best = engine_pv[0] if engine_pv else None

    is_only_move = False
    if len(before) > 1:
        second_white = before[1]["score"].white().score(mate_score=10000) or 0
        gap_white = eval_before_white - second_white
        gap_mover = gap_white if board.turn == chess.WHITE else -gap_white
        is_only_move = gap_mover >= _ONLY_MOVE_GAP_CP

    sign = 1 if board.turn == chess.WHITE else -1
    eval_before_mover = sign * eval_before_white

    pre_board = chess.Board(fen)
    engine_best_san = pre_board.san(engine_best) if engine_best is not None else ""
    engine_best_uci = engine_best.uci() if engine_best is not None else ""
    engine_pv_san = _pv_to_san(pre_board, engine_pv[:8])

    if not is_legal:
        return {
            "move_san": move_san, "move_uci": move_uci,
            "is_legal": False,
            "eval_before_cp": eval_before_mover,
            "eval_after_cp": None,
            "cp_loss": None, "win_pct_drop": None,
            "engine_best_san": engine_best_san,
            "engine_best_uci": engine_best_uci,
            "engine_pv_san": engine_pv_san,
            "classification": CLASS_ILLEGAL,
            "is_only_move": is_only_move,
        }

    board.push(chess_move)
    after = _tools._engine.analyse(board, chess.engine.Limit(depth=depth))
    eval_after_white = after["score"].white().score(mate_score=10000) or 0
    eval_after_mover = sign * eval_after_white  # same sign — mover POV preserved

    cp_loss = max(0, eval_before_mover - eval_after_mover)
    win_pct_drop = round(
        cp_to_win_pct(eval_before_mover) - cp_to_win_pct(eval_after_mover), 1
    )
    classification = _classify_label(win_pct_drop, engine_best, chess_move)

    return {
        "move_san": move_san, "move_uci": move_uci,
        "is_legal": True,
        "eval_before_cp": eval_before_mover,
        "eval_after_cp": eval_after_mover,
        "cp_loss": cp_loss,
        "win_pct_drop": win_pct_drop,
        "engine_best_san": engine_best_san,
        "engine_best_uci": engine_best_uci,
        "engine_pv_san": engine_pv_san,
        "classification": classification,
        "is_only_move": is_only_move,
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_move(board: chess.Board, move: str) -> chess.Move | None:
    """Try UCI first, then SAN. Returns None if neither parses."""
    try:
        m = chess.Move.from_uci(move)
        if m in board.legal_moves:
            return m
        # UCI shape parsed but not legal — keep going to try SAN
    except Exception:
        m = None
    try:
        return board.parse_san(move)
    except Exception:
        return m  # may be a parsable-but-illegal UCI; return so caller can flag


def _pv_to_san(board: chess.Board, pv: list[chess.Move]) -> list[str]:
    out: list[str] = []
    b = board.copy()
    for mv in pv:
        try:
            out.append(b.san(mv))
            b.push(mv)
        except Exception:
            break
    return out


def _classify_label(
    win_pct_drop: float, engine_best: chess.Move | None, played: chess.Move
) -> str:
    """Extend engine._classify_drop with sub-error tiers."""
    err = _classify_drop(win_pct_drop)
    if err is not None:
        return err  # blunder | mistake | inaccuracy
    if engine_best is not None and played == engine_best:
        return CLASS_BEST
    if win_pct_drop < 2:
        return CLASS_EXCELLENT
    return CLASS_GOOD


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
