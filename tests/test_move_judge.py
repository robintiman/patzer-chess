"""Tests for analysis/move_judge.classify_move and refute.

Engine-dependent: skipped when Stockfish isn't on PATH.
"""
from __future__ import annotations

import shutil

import chess
import chess.engine
import pytest

from gg_chess.analysis import tools as chess_tools
from gg_chess.analysis.move_judge import classify_move, refute
from gg_chess.config import STOCKFISH_HASH, STOCKFISH_PATH, STOCKFISH_THREADS


def _stockfish_available() -> bool:
    return shutil.which(STOCKFISH_PATH) is not None


pytestmark = pytest.mark.skipif(
    not _stockfish_available(), reason="stockfish binary not on PATH"
)


@pytest.fixture
def engine():
    eng = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    eng.configure({"Threads": STOCKFISH_THREADS, "Hash": STOCKFISH_HASH})
    chess_tools.set_engine(eng)
    try:
        yield eng
    finally:
        chess_tools.set_engine(None)
        eng.quit()


# Position after 1.e4 e5 — Nf3 is universally accepted as a top move.
NF3_OK_FEN = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"


def test_legal_good_move(engine):
    result = classify_move(NF3_OK_FEN, "Nf3", depth=10)
    assert result.is_legal is True
    assert result.move_san == "Nf3"
    assert result.move_uci == "g1f3"
    assert result.cp_loss is not None
    assert result.cp_loss < 50  # Nf3 is a top move; small/zero cp_loss
    assert result.classification in {"best", "excellent", "good"}
    assert result.engine_best_uci  # non-empty
    assert isinstance(result.is_only_move, bool)


def test_uci_input_works(engine):
    result = classify_move(NF3_OK_FEN, "g1f3", depth=10)
    assert result.is_legal is True
    assert result.move_uci == "g1f3"


def test_illegal_move(engine):
    # a1a8 is not legal in the starting-after-e4 position
    result = classify_move(NF3_OK_FEN, "a1a8", depth=10)
    assert result.is_legal is False
    assert result.classification == "illegal"
    assert result.cp_loss is None
    assert result.eval_after_cp is None
    assert result.engine_best_uci  # engine still suggests its best move


def test_fools_mate_blunder(engine):
    # After 1.f3 e5, white plays 2.g4?? — black mates with Qh4#.
    # Roughly equal position turns into immediate mate → catastrophic blunder.
    fen = "rnbqkbnr/pppp1ppp/8/4p3/8/5P2/PPPPP1PP/RNBQKBNR w KQkq - 0 2"
    result = classify_move(fen, "g4", depth=12)
    assert result.is_legal is True
    assert result.cp_loss >= 500
    assert result.classification == "blunder"


def test_pv_returned_in_san(engine):
    result = classify_move(NF3_OK_FEN, "Nf3", depth=10)
    assert isinstance(result.engine_pv_san, list)
    if result.engine_pv_san:
        # Each PV entry should be a SAN-shaped string
        assert all(isinstance(s, str) and s for s in result.engine_pv_san)


def test_requires_engine():
    # Without set_engine, classify_move should raise
    chess_tools.set_engine(None)
    with pytest.raises(RuntimeError, match="set_engine"):
        classify_move(NF3_OK_FEN, "Nf3", depth=8)


# ── refute ─────────────────────────────────────────────────────────────────────

# White to move; queen on h1 reaches h7 along the h-file. Qxh7 grabs a pawn
# but hangs the queen to Rxh7. Demonstrates that refute produces the capture.
HANGING_QUEEN_REFUTE_FEN = "4k2r/7p/8/8/8/8/8/4K2Q w k - 0 1"


def test_refute_finds_capture(engine):
    result = refute(HANGING_QUEEN_REFUTE_FEN, "Qxh7", depth=10)
    assert result.is_legal is True
    assert result.terminal is None
    assert result.refutation_uci == "h8h7"  # Rxh7 punishes
    assert result.refutation_san.startswith("R")
    assert len(result.refutation_pv_san) >= 1
    assert result.tactical_motif is None  # find_tactics still a stub
    assert isinstance(result.eval_after_refutation_cp, int)


def test_refute_on_good_move_still_returns(engine):
    # On a top move there's still a "best reply" — refute should not crash
    # and should return a small/neutral eval rather than a punishing swing.
    result = refute(NF3_OK_FEN, "Nf3", depth=10)
    assert result.is_legal is True
    assert result.refutation_uci  # engine always has *some* reply
    assert isinstance(result.eval_after_refutation_cp, int)


def test_refute_illegal_move(engine):
    result = refute(NF3_OK_FEN, "a1a8", depth=10)
    assert result.is_legal is False
    assert result.refutation_san is None
    assert result.refutation_uci is None
    assert result.refutation_pv_san == []
    assert result.eval_after_refutation_cp is None
    assert result.terminal is None


def test_refute_terminal_child(engine):
    # Scholar's mate: white to move with Bc4 + Qh5 set up; Qxf7 delivers mate.
    fen_pre_mate = "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 0 4"
    result = refute(fen_pre_mate, "Qxf7", depth=8)
    assert result.is_legal is True
    assert result.terminal == "checkmate"
    assert result.refutation_san is None
    assert result.refutation_pv_san == []
    assert result.eval_after_refutation_cp is None
