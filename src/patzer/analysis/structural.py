import chess

from ..themes import TACTICAL_THEMES


def detect_themes(board: chess.Board, best_move: chess.Move) -> list[str]:
    """Detect tactical themes present in `best_move` that the player missed."""
    themes: list[str] = []

    if _is_fork(board, best_move):
        themes.append("fork")
    if _is_hanging_piece(board, best_move):
        themes.append("hangingPiece")
    if _is_double_check(board, best_move):
        themes.append("doubleCheck")
    if _is_discovered_attack(board, best_move):
        themes.append("discoveredAttack")
    if _is_pin(board, best_move):
        themes.append("pin")
    if _is_skewer(board, best_move):
        themes.append("skewer")
    if _is_back_rank_mate(board, best_move):
        themes.append("backRankMate")

    return [t for t in themes if t in TACTICAL_THEMES]


def _is_fork(board: chess.Board, move: chess.Move) -> bool:
    test_board = board.copy()
    test_board.push(move)

    moving_piece = test_board.piece_at(move.to_square)
    if moving_piece is None:
        return False

    # After pushing white's move, test_board.turn is black — that's the opponent
    opponent_color = test_board.turn
    attacked_squares = test_board.attacks(move.to_square)

    valuable_attacked = 0
    for sq in attacked_squares:
        piece = test_board.piece_at(sq)
        if piece and piece.color == opponent_color and piece.piece_type in (
            chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.KING
        ):
            valuable_attacked += 1

    return valuable_attacked >= 2


def _is_hanging_piece(board: chess.Board, move: chess.Move) -> bool:
    """The best move captures a hanging (undefended) piece."""
    if board.is_capture(move):
        captured_sq = move.to_square
        captured_piece = board.piece_at(captured_sq)
        if captured_piece is None:
            return False
        # Piece is hanging if no defenders of that color attack the square
        defenders = board.attackers(captured_piece.color, captured_sq)
        return len(defenders) == 0
    return False


def _is_double_check(board: chess.Board, move: chess.Move) -> bool:
    test_board = board.copy()
    test_board.push(move)
    if not test_board.is_check():
        return False
    checkers = test_board.checkers()
    return len(checkers) >= 2


def _is_discovered_attack(board: chess.Board, move: chess.Move) -> bool:
    from_sq = move.from_square
    to_sq = move.to_square

    test_board = board.copy()
    test_board.push(move)

    moving_color = board.turn
    opponent_color = not moving_color

    # Check if a piece on same rank/file/diagonal as from_sq now attacks an opponent piece
    directions = [
        chess.BB_RANKS[chess.square_rank(from_sq)],
        chess.BB_FILES[chess.square_file(from_sq)],
    ]
    # Check diagonal
    for piece_sq in chess.scan_reversed(test_board.occupied_co[moving_color]):
        if piece_sq == to_sq:
            continue
        piece = test_board.piece_at(piece_sq)
        if piece is None:
            continue
        if piece.piece_type in (chess.BISHOP, chess.QUEEN, chess.ROOK):
            attacks = test_board.attacks(piece_sq)
            for opp_sq in chess.scan_reversed(test_board.occupied_co[opponent_color]):
                if opp_sq in attacks:
                    orig_attacks = board.attacks(piece_sq)
                    if opp_sq not in orig_attacks:
                        return True
    return False


def _is_pin(board: chess.Board, move: chess.Move) -> bool:
    """The best move exploits a pin (moves to attack a pinned piece)."""
    test_board = board.copy()
    test_board.push(move)

    opponent_color = not board.turn

    for sq in chess.scan_reversed(test_board.occupied_co[opponent_color]):
        if test_board.is_pinned(opponent_color, sq):
            # If the best move attacks this pinned piece, it's exploiting a pin
            attacks_after = test_board.attacks(move.to_square)
            if sq in attacks_after:
                return True
    return False


def _is_skewer(board: chess.Board, move: chess.Move) -> bool:
    """A skewer: move attacks a valuable piece that, when it moves, exposes another."""
    test_board = board.copy()
    test_board.push(move)

    moving_piece = test_board.piece_at(move.to_square)
    if moving_piece is None:
        return False
    if moving_piece.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        return False

    opponent_color = not test_board.turn
    attacks = test_board.attacks(move.to_square)

    for attacked_sq in attacks:
        attacked_piece = test_board.piece_at(attacked_sq)
        if attacked_piece is None or attacked_piece.color != opponent_color:
            continue
        if attacked_piece.piece_type not in (chess.KING, chess.QUEEN):
            continue
        # Check if there's a less valuable piece behind
        direction = chess.square_file(attacked_sq) - chess.square_file(move.to_square)
        rank_dir = chess.square_rank(attacked_sq) - chess.square_rank(move.to_square)
        file_step = 0 if direction == 0 else (1 if direction > 0 else -1)
        rank_step = 0 if rank_dir == 0 else (1 if rank_dir > 0 else -1)

        check_sq = attacked_sq
        while True:
            f = chess.square_file(check_sq) + file_step
            r = chess.square_rank(check_sq) + rank_step
            if not (0 <= f <= 7 and 0 <= r <= 7):
                break
            check_sq = chess.square(f, r)
            behind = test_board.piece_at(check_sq)
            if behind is not None:
                if behind.color == opponent_color:
                    return True
                break

    return False


def _is_back_rank_mate(board: chess.Board, move: chess.Move) -> bool:
    test_board = board.copy()
    test_board.push(move)

    if not test_board.is_checkmate():
        return False

    king_sq = test_board.king(not test_board.turn)
    if king_sq is None:
        return False

    king_rank = chess.square_rank(king_sq)
    return king_rank in (0, 7)
