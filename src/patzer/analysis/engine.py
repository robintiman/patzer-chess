import io
from dataclasses import dataclass, field

import chess
import chess.engine
import chess.pgn

from ..config import BLUNDER_THRESHOLD_CP, MULTI_PV_COUNT, STOCKFISH_DEPTH, STOCKFISH_PATH
from ..ingestion.parser import Game

OPENING_MOVES_SKIP = 5
MAX_ERRORS_PER_GAME = 50


@dataclass
class ErrorPosition:
    move_number: int
    fen_before: str
    fen_after: str
    player_move: str  # UCI
    best_move: str    # UCI
    eval_drop_cp: int
    pv_san: list[str]       # Best line in SAN notation (from position before player's move)
    alt_pvs_san: list[list[str]] = field(default_factory=list)  # 2nd and 3rd best lines


def analyse_game(game: Game, depth: int = STOCKFISH_DEPTH) -> list[ErrorPosition]:
    pgn_game = chess.pgn.read_game(io.StringIO(game.pgn_text))
    if pgn_game is None:
        return []

    player_is_white = game.player_color == "white"
    errors: list[ErrorPosition] = []

    with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
        board = pgn_game.board()
        move_number = 0

        for node in pgn_game.mainline():
            move = node.move
            is_player_turn = board.turn == chess.WHITE if player_is_white else board.turn == chess.BLACK

            if not is_player_turn:
                board.push(move)
                continue

            move_number += 1
            if move_number <= OPENING_MOVES_SKIP:
                board.push(move)
                continue

            if len(errors) >= MAX_ERRORS_PER_GAME:
                break

            fen_before = board.fen()

            results = engine.analyse(board, chess.engine.Limit(depth=depth), multipv=MULTI_PV_COUNT)
            info_before = results[0]
            score_before = _score_from_player_pov(info_before["score"], player_is_white)
            best_move_obj = info_before.get("pv", [None])[0]

            pv_san: list[str] = []
            temp_board = board.copy()
            for pv_move in info_before.get("pv", [])[:8]:
                try:
                    pv_san.append(temp_board.san(pv_move))
                    temp_board.push(pv_move)
                except Exception:
                    break

            alt_pvs_san: list[list[str]] = []
            for alt_info in results[1:]:
                alt_pv: list[str] = []
                temp_board = board.copy()
                for pv_move in alt_info.get("pv", [])[:8]:
                    try:
                        alt_pv.append(temp_board.san(pv_move))
                        temp_board.push(pv_move)
                    except Exception:
                        break
                alt_pvs_san.append(alt_pv)

            board.push(move)
            fen_after = board.fen()

            info_after = engine.analyse(board, chess.engine.Limit(depth=depth))
            score_after = _score_from_player_pov(info_after["score"], player_is_white)
            # Negate because now it's opponent's turn
            score_after = -score_after

            drop = score_before - score_after

            if drop >= BLUNDER_THRESHOLD_CP and best_move_obj is not None:
                player_move_uci = move.uci()
                best_move_uci = best_move_obj.uci()

                if player_move_uci != best_move_uci:
                    errors.append(ErrorPosition(
                        move_number=move_number,
                        fen_before=fen_before,
                        fen_after=fen_after,
                        player_move=player_move_uci,
                        best_move=best_move_uci,
                        eval_drop_cp=drop,
                        pv_san=pv_san,
                        alt_pvs_san=alt_pvs_san,
                    ))

    return errors


def _score_from_player_pov(score: chess.engine.PovScore, player_is_white: bool) -> int:
    if player_is_white:
        cp = score.white().score(mate_score=10000)
    else:
        cp = score.black().score(mate_score=10000)
    return cp if cp is not None else 0
