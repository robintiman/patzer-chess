import sqlite3

from ..player_model import get_weakest_themes, get_all_theme_performance
from .puzzle_db import Puzzle, get_puzzles_for_themes


DEFAULT_RATING = 1400
RATING_TARGET_OFFSET = 100
RATING_WINDOW = 200


def build_training_queue(
    db: sqlite3.Connection,
    username: str,
    n: int = 10,
) -> list[Puzzle]:
    player_rating = _estimate_player_rating(db, username)
    rating_low = player_rating - RATING_WINDOW
    rating_high = player_rating + RATING_TARGET_OFFSET + RATING_WINDOW

    weakest = get_weakest_themes(db, username, n=5)
    all_perf = get_all_theme_performance(db, username)

    weak_theme_names = [t.theme_name for t in weakest]
    error_theme_names = [t.theme_name for t in all_perf if t.game_errors > 0 and t.theme_name not in weak_theme_names]

    n_weak = round(n * 0.7)
    n_error = n - n_weak

    queue: list[Puzzle] = []
    seen_ids: set[str] = set()

    weak_puzzles = get_puzzles_for_themes(db, weak_theme_names, (rating_low, rating_high), limit=n_weak * 3)
    for p in weak_puzzles:
        if p.puzzle_id not in seen_ids:
            queue.append(p)
            seen_ids.add(p.puzzle_id)
        if len(queue) >= n_weak:
            break

    error_puzzles = get_puzzles_for_themes(db, error_theme_names, (rating_low, rating_high), limit=n_error * 3)
    for p in error_puzzles:
        if p.puzzle_id not in seen_ids:
            queue.append(p)
            seen_ids.add(p.puzzle_id)
        if len(queue) >= n:
            break

    # Fill remaining slots from weakest if needed
    if len(queue) < n:
        extra = get_puzzles_for_themes(db, weak_theme_names, (rating_low, rating_high), limit=(n - len(queue)) * 3)
        for p in extra:
            if p.puzzle_id not in seen_ids:
                queue.append(p)
                seen_ids.add(p.puzzle_id)
            if len(queue) >= n:
                break

    return queue[:n]


def _estimate_player_rating(db: sqlite3.Connection, username: str) -> int:
    row = db.execute(
        """SELECT g.pgn_text FROM games g
           JOIN players p ON p.id = g.player_id
           WHERE p.username = ?
           ORDER BY g.played_at DESC
           LIMIT 1""",
        (username,),
    ).fetchone()

    if row is None:
        return DEFAULT_RATING

    pgn_text: str = row["pgn_text"]
    import re
    white_elo = re.search(r'\[WhiteElo "(\d+)"\]', pgn_text)
    black_elo = re.search(r'\[BlackElo "(\d+)"\]', pgn_text)

    # Determine player color
    white_match = re.search(r'\[White "([^"]+)"\]', pgn_text)
    is_white = white_match and white_match.group(1).lower() == username.lower()

    if is_white and white_elo:
        return int(white_elo.group(1)) + RATING_TARGET_OFFSET
    elif not is_white and black_elo:
        return int(black_elo.group(1)) + RATING_TARGET_OFFSET

    return DEFAULT_RATING
