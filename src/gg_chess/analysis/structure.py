"""Static (engine-free) position structure tools.

Every function here returns a deterministic JSON-serialisable dict computed
from python-chess only. They are cheap, do not require Stockfish, and form
the base layer of "ground truth" the LLM is allowed to cite.

Functions in this module are exposed as LLM tools via tools.py.
"""
from __future__ import annotations

import chess


# ── Tools ──────────────────────────────────────────────────────────────────────

def pawn_structure(fen: str) -> dict:
    """Classify pawn structure features for both colours.

    Returns:
        {
          "white": {
            "isolated":  ["a2", ...],
            "doubled":   [["a2","a4"], ...],
            "backward":  ["d3", ...],
            "passed":    ["e5", ...],
            "islands":   int,
          },
          "black": { ... },
          "iqp":         "white" | "black" | null,
          "pawn_chains": [["e5","d4","c3"], ...],
        }
    """
    raise NotImplementedError


def king_safety(fen: str, color: str) -> dict:
    """Quantify king safety for `color`.

    Returns:
        {
          "king_square":     "g1",
          "shield_holes":    ["g2", "h2"],   # missing/advanced shield pawns
          "open_files_near": ["f", "h"],     # open or half-open files within 1 of king file
          "attackers":       [{"piece": "Q", "square": "h4"}, ...],
          "defenders":       [{"piece": "N", "square": "f3"}, ...],
          "attacker_count":  int,
          "defender_count":  int,
          "ring_squares":    ["f1","f2",...,"h2"],
          "weak_ring_squares": ["g2"],       # ring squares we attack but they can't defend
        }

    Args:
        fen: FEN of the position.
        color: 'white' or 'black' — whose king to evaluate.
    """
    raise NotImplementedError


def piece_activity(fen: str) -> dict:
    """Per-piece mobility and positional flags.

    Returns:
        {
          "white": [
            {"piece":"N","square":"f3","mobility":int,"is_outpost":bool,"on_open_file":bool,"on_half_open_file":bool,"is_bad_bishop":bool}
            , ...
          ],
          "black": [...],
          "open_files":      ["d", "e"],
          "half_open_files": {"white": ["c"], "black": ["f"]},
        }

    Note:
        Mobility = count of pseudo-legal moves for the piece.
        Outpost = square defended by own pawn, not attackable by enemy pawn, on rank 4-6 from owner's side.
        Bad bishop = bishop blocked by own pawns on its colour complex.
    """
    raise NotImplementedError


def material_imbalance(fen: str) -> dict:
    """Material count, balance, and imbalance flags.

    Returns:
        {
          "white": {"P":int,"N":int,"B":int,"R":int,"Q":int,"total":int},
          "black": {"P":int,"N":int,"B":int,"R":int,"Q":int,"total":int},
          "diff_cp":        int,             # white minus black, in centipawns (P=100,N=320,B=330,R=500,Q=900)
          "bishop_pair":    "white" | "black" | "both" | null,
          "imbalance_tags": ["minor_for_rook", "two_minors_for_rook_pawn", ...],
        }
    """
    raise NotImplementedError


def describe_position(fen: str) -> dict:
    """Render the position as a flat, LLM-friendly text block.

    Used as a system-prompt prefix so the model never has to parse FEN.

    Returns:
        {
          "fen":    str,                  # echoed back
          "to_move": "white" | "black",
          "castling_rights": "KQkq",
          "halfmove_clock": int,
          "fullmove_number": int,
          "ascii":  str,                  # python-chess board.unicode() / str
          "by_square": [                  # only occupied squares, reading order a8..h1
            {"square":"a8","piece":"R","color":"black"}, ...
          ],
          "legal_moves_san": [str, ...],  # all legal moves in SAN
        }
    """
    board = chess.Board(fen)
    fen_parts = fen.split()
    castling = fen_parts[2] if len(fen_parts) > 2 else "-"

    by_square = []
    for rank in range(7, -1, -1):
        for file in range(8):
            sq = chess.square(file, rank)
            piece = board.piece_at(sq)
            if piece is None:
                continue
            by_square.append({
                "square": chess.square_name(sq),
                "piece":  piece.symbol().upper(),
                "color":  "white" if piece.color == chess.WHITE else "black",
            })

    return {
        "fen":             fen,
        "to_move":         "white" if board.turn == chess.WHITE else "black",
        "castling_rights": castling,
        "halfmove_clock":  board.halfmove_clock,
        "fullmove_number": board.fullmove_number,
        "ascii":           board.unicode(borders=True, empty_square="·"),
        "by_square":       by_square,
        "legal_moves_san": [board.san(m) for m in board.legal_moves],
    }
