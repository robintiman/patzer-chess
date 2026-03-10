import io
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

import chess
import chess.engine
import chess.pgn

from ..config import (
    BLUNDER_WIN_PCT_THRESHOLD,
    INACCURACY_WIN_PCT_THRESHOLD,
    MISTAKE_WIN_PCT_THRESHOLD,
    MULTI_PV_COUNT,
    STOCKFISH_NODES,
    STOCKFISH_NODES_AFTER,
    STOCKFISH_NODES_SCAN,
    STOCKFISH_PATH,
)
from ..ingestion.parser import Game

MAX_ERRORS_PER_GAME = 50
_ANALYSIS_WORKERS = 3


@dataclass
class ErrorPosition:
    move_number: int
    fen_before: str
    fen_after: str
    player_move: str        # UCI
    best_move: str          # UCI
    eval_drop_cp: int
    win_pct_drop: float
    move_classification: str  # "blunder", "mistake", "inaccuracy"
    pv_san: list[str]
    alt_pvs_san: list[list[str]] = field(default_factory=list)
    half_move_index: int = 0


def cp_to_win_pct(cp: int) -> float:
    """Convert centipawns (player's perspective) to win probability 0-100.

    Lichess sigmoid fitted to 75k+ games at 2300+ ELO.
    """
    cp_capped = max(-1000, min(1000, cp))
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp_capped)) - 1)


def _classify_drop(win_pct_drop: float) -> str | None:
    if win_pct_drop >= BLUNDER_WIN_PCT_THRESHOLD:
        return "blunder"
    if win_pct_drop >= MISTAKE_WIN_PCT_THRESHOLD:
        return "mistake"
    if win_pct_drop >= INACCURACY_WIN_PCT_THRESHOLD:
        return "inaccuracy"
    return None


def _uci_to_san(board: chess.Board, uci_moves: list[str]) -> list[str]:
    san_moves: list[str] = []
    b = board.copy()
    for uci in uci_moves:
        try:
            move = chess.Move.from_uci(uci)
            san_moves.append(b.san(move))
            b.push(move)
        except Exception:
            break
    return san_moves


# ---------------------------------------------------------------------------
# Per-position analysis worker (runs in a thread)
# ---------------------------------------------------------------------------

def _analyse_position_task(task: dict) -> ErrorPosition | None:
    """Analyse one player position.

    Two-pass strategy:
    - Pass 1 (STOCKFISH_NODES_SCAN): fast — find best move and rough eval.
    - Pass 2 (STOCKFISH_NODES): full multipv — only for confirmed errors.

    Returns an ErrorPosition or None if the move is not notable.
    """
    fen_before: str = task["fen_before"]
    fen_after: str = task["fen_after"]
    player_move_uci: str = task["player_move_uci"]
    player_is_white: bool = task["player_is_white"]
    move_number: int = task["move_number"]
    half_move_index: int = task["half_move_index"]

    board_before = chess.Board(fen_before)
    board_after = chess.Board(fen_after)

    with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
        engine.configure({"Threads": 2, "Hash": 128})

        # ------------------------------------------------------------------
        # Pass 1: quick scan — find best move and rough eval
        # ------------------------------------------------------------------
        r1 = engine.analyse(
            board_before.copy(),
            chess.engine.Limit(nodes=STOCKFISH_NODES_SCAN),
            multipv=1,
        )
        if not isinstance(r1, list):
            r1 = [r1]
        scan_eval_cp_white = r1[0]["score"].white().score(mate_score=1000) or 0
        best_mv = r1[0].get("pv", [None])[0]
        best_move_uci = best_mv.uci() if best_mv else None

        # Player played the top engine choice — can't be a notable error
        if not best_move_uci or player_move_uci == best_move_uci:
            return None

        # ------------------------------------------------------------------
        # Evaluate position after player's move
        # ------------------------------------------------------------------
        info_after = engine.analyse(
            board_after.copy(),
            chess.engine.Limit(nodes=STOCKFISH_NODES_AFTER),
        )
        after_eval_cp_white = info_after["score"].white().score(mate_score=1000) or 0

        # Convert to player's perspective (positive = player is winning)
        score_before_scan = scan_eval_cp_white if player_is_white else -scan_eval_cp_white
        score_after = after_eval_cp_white if player_is_white else -after_eval_cp_white

        # Quick filter: bail early if not even an inaccuracy by scan eval
        scan_drop_pct = cp_to_win_pct(score_before_scan) - cp_to_win_pct(score_after)
        if scan_drop_pct < INACCURACY_WIN_PCT_THRESHOLD:
            return None

        # ------------------------------------------------------------------
        # Pass 2: full multipv analysis for accurate eval + PV lines
        # ------------------------------------------------------------------
        r2 = engine.analyse(
            board_before.copy(),
            chess.engine.Limit(nodes=STOCKFISH_NODES),
            multipv=MULTI_PV_COUNT,
        )
        if not isinstance(r2, list):
            r2 = [r2]
        full_eval_cp_white = r2[0]["score"].white().score(mate_score=1000) or 0
        best_mv_full = r2[0].get("pv", [None])[0]
        best_move_uci_full = best_mv_full.uci() if best_mv_full else best_move_uci
        pv_uci = [m.uci() for m in r2[0].get("pv", [])[:8]]
        alt_pvs_uci = [[m.uci() for m in info.get("pv", [])[:8]] for info in r2[1:]]

        # Final classification using the more accurate pass-2 eval
        score_before_full = full_eval_cp_white if player_is_white else -full_eval_cp_white
        final_drop_pct = cp_to_win_pct(score_before_full) - cp_to_win_pct(score_after)
        classification = _classify_drop(final_drop_pct)
        if classification is None:
            return None

        eval_drop_cp = score_before_full - score_after
        pv_san = _uci_to_san(board_before, pv_uci)
        alt_pvs_san = [_uci_to_san(board_before, pv) for pv in alt_pvs_uci]

        return ErrorPosition(
            move_number=move_number,
            fen_before=fen_before,
            fen_after=fen_after,
            player_move=player_move_uci,
            best_move=best_move_uci_full or best_move_uci or "",
            eval_drop_cp=max(0, eval_drop_cp),
            win_pct_drop=round(final_drop_pct, 1),
            move_classification=classification,
            pv_san=pv_san,
            alt_pvs_san=alt_pvs_san,
            half_move_index=half_move_index,
        )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def analyse_game(game: Game):
    """Generator that yields dicts:
      {"type": "progress", "half_move_index": int, "san": str}
      {"type": "done", "errors": list[ErrorPosition]}

    Phase 1 (fast, sequential): pre-scan the game to collect player positions
    and emit progress events for frontend board animation.

    Phase 2 (parallel): analyse all collected positions with _ANALYSIS_WORKERS
    concurrent Stockfish instances.
    """
    pgn_game = chess.pgn.read_game(io.StringIO(game.pgn_text))
    if pgn_game is None:
        yield {"type": "done", "errors": []}
        return

    player_is_white = game.player_color == "white"

    # ------------------------------------------------------------------
    # Phase 1: pre-scan — collect positions, emit progress events
    # ------------------------------------------------------------------
    tasks: list[dict] = []
    board = pgn_game.board()
    move_number = 0
    half_move_index = 0

    for node in pgn_game.mainline():
        move = node.move
        half_move_index += 1
        is_player_turn = board.turn == (chess.WHITE if player_is_white else chess.BLACK)

        if not is_player_turn:
            board.push(move)
            continue

        move_number += 1
        san = board.san(move)
        yield {"type": "progress", "half_move_index": half_move_index, "san": san}

        fen_before = board.fen()
        player_move_uci = move.uci()
        board.push(move)
        fen_after = board.fen()

        tasks.append({
            "half_move_index": half_move_index,
            "move_number": move_number,
            "fen_before": fen_before,
            "fen_after": fen_after,
            "player_move_uci": player_move_uci,
            "player_is_white": player_is_white,
        })

    # ------------------------------------------------------------------
    # Phase 2: parallel Stockfish analysis
    # ------------------------------------------------------------------
    errors: list[ErrorPosition] = []
    with ThreadPoolExecutor(max_workers=_ANALYSIS_WORKERS) as pool:
        futures = [pool.submit(_analyse_position_task, task) for task in tasks]
        for future in as_completed(futures):
            try:
                result = future.result()
                if result is not None:
                    errors.append(result)
            except Exception as e:
                print(f"[analyse_game] worker error: {e}")

    errors.sort(key=lambda e: e.move_number)
    errors = errors[:MAX_ERRORS_PER_GAME]
    yield {"type": "done", "errors": errors}
