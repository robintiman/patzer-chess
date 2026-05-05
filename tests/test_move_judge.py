"""Tests for analysis/move_judge.classify_move.

Engine-dependent: skipped when Stockfish isn't on PATH.
"""
from __future__ import annotations

import shutil

import chess
import chess.engine
import pytest

from gg_chess.analysis import tools as chess_tools
from gg_chess.analysis.move_judge import classify_move
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

# A simple "drop the queen" position: white to move, queen on d4 hanging
# to a black pawn on e5. Best move: anything. Blunder: any move that leaves
# the queen there.
# Use a constructed position where moving rook to a3 simply hangs the queen.
HANGING_QUEEN_FEN = "4k3/8/8/4p3/3Q4/8/8/4K2R w K - 0 1"

# Mate-in-1 position: white plays Qh7# (Qh4-h7 mate? Construct simply.)
# Use a back-rank mate: White Q on h8 already mates? Simpler: only move = mate.
# Use: black king on h8, white queen ready to mate; only-move scenario for black.
# Skip "only move" for now — assert is_only_move type only, not value.


def test_legal_good_move(engine):
    result = classify_move(NF3_OK_FEN, "Nf3", depth=10)
    assert result["is_legal"] is True
    assert result["move_san"] == "Nf3"
    assert result["move_uci"] == "g1f3"
    assert result["cp_loss"] is not None
    assert result["cp_loss"] < 50  # Nf3 is a top move; small/zero cp_loss
    assert result["classification"] in {"best", "excellent", "good"}
    assert result["engine_best_uci"]  # non-empty
    assert isinstance(result["is_only_move"], bool)


def test_uci_input_works(engine):
    result = classify_move(NF3_OK_FEN, "g1f3", depth=10)
    assert result["is_legal"] is True
    assert result["move_uci"] == "g1f3"


def test_illegal_move(engine):
    # a1a8 is not legal in the starting-after-e4 position
    result = classify_move(NF3_OK_FEN, "a1a8", depth=10)
    assert result["is_legal"] is False
    assert result["classification"] == "illegal"
    assert result["cp_loss"] is None
    assert result["eval_after_cp"] is None
    assert result["engine_best_uci"]  # engine still suggests its best move


def test_fools_mate_blunder(engine):
    # After 1.f3 e5, white plays 2.g4?? — black mates with Qh4#.
    # Roughly equal position turns into immediate mate → catastrophic blunder.
    fen = "rnbqkbnr/pppp1ppp/8/4p3/8/5P2/PPPPP1PP/RNBQKBNR w KQkq - 0 2"
    result = classify_move(fen, "g4", depth=12)
    assert result["is_legal"] is True
    assert result["cp_loss"] >= 500
    assert result["classification"] == "blunder"


def test_pv_returned_in_san(engine):
    result = classify_move(NF3_OK_FEN, "Nf3", depth=10)
    assert isinstance(result["engine_pv_san"], list)
    if result["engine_pv_san"]:
        # Each PV entry should be a SAN-shaped string
        assert all(isinstance(s, str) and s for s in result["engine_pv_san"])


def test_requires_engine():
    # Without set_engine, classify_move should raise
    chess_tools.set_engine(None)
    with pytest.raises(RuntimeError, match="set_engine"):
        classify_move(NF3_OK_FEN, "Nf3", depth=8)
