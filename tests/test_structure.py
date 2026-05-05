"""Tests for analysis/structure.py — pure python-chess, no engine."""
from __future__ import annotations

import chess

from gg_chess.analysis.structure import describe_position


STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
AFTER_E4_FEN = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
# Fool's mate — 1.f3 e5 2.g4 Qh4#. Black has just delivered mate, white to move, no legal moves.
FOOLS_MATE_FEN = "rnb1kbnr/pppp1ppp/8/4p3/6PQ/5P2/PPPPP2P/RNB1KBNR w KQkq - 1 3"
# (Construct a real mate FEN — fool's mate position after 2...Qh4#)
REAL_MATE_FEN = "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"


def test_starting_position_basics():
    desc = describe_position(STARTING_FEN)
    assert desc["fen"] == STARTING_FEN
    assert desc["to_move"] == "white"
    assert desc["castling_rights"] == "KQkq"
    assert desc["halfmove_clock"] == 0
    assert desc["fullmove_number"] == 1
    assert len(desc["by_square"]) == 32
    assert len(desc["legal_moves_san"]) == 20


def test_starting_position_corner_pieces():
    desc = describe_position(STARTING_FEN)
    by_sq = {s["square"]: s for s in desc["by_square"]}
    # Reading order: a8 first, h1 last
    assert desc["by_square"][0]["square"] == "a8"
    assert desc["by_square"][-1]["square"] == "h1"
    assert by_sq["a8"] == {"square": "a8", "piece": "R", "color": "black"}
    assert by_sq["e1"] == {"square": "e1", "piece": "K", "color": "white"}


def test_after_e4():
    desc = describe_position(AFTER_E4_FEN)
    assert desc["to_move"] == "black"
    assert desc["fullmove_number"] == 1
    by_sq = {s["square"]: s["piece"] for s in desc["by_square"]}
    assert "e4" in by_sq and by_sq["e4"] == "P"
    assert "e2" not in by_sq


def test_mate_position_has_no_legal_moves():
    desc = describe_position(REAL_MATE_FEN)
    # Sanity: it really is mate
    assert chess.Board(REAL_MATE_FEN).is_checkmate()
    assert desc["legal_moves_san"] == []


def test_ascii_is_a_string_with_pieces():
    desc = describe_position(STARTING_FEN)
    assert isinstance(desc["ascii"], str)
    assert len(desc["ascii"]) > 0
    # python-chess unicode pieces — kings always present in starting position
    assert "♔" in desc["ascii"] or "K" in desc["ascii"]
