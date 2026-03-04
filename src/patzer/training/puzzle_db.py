import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Puzzle:
    puzzle_id: str
    fen: str
    moves: str        # space-separated UCI solution
    rating: int
    themes: str       # space-separated
    game_url: str


def load_puzzle_db(db: sqlite3.Connection, csv_path: Path) -> int:
    """Bulk import Lichess puzzle CSV into SQLite. Returns total rows imported."""
    total = 0
    chunk: list[tuple] = []
    chunk_size = 10_000

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            chunk.append((
                row["PuzzleId"],
                row["FEN"],
                row["Moves"],
                int(row["Rating"]),
                row.get("Themes", ""),
                row.get("GameUrl", ""),
            ))
            if len(chunk) >= chunk_size:
                _insert_chunk(db, chunk)
                total += len(chunk)
                chunk = []

        if chunk:
            _insert_chunk(db, chunk)
            total += len(chunk)

    return total


def _insert_chunk(db: sqlite3.Connection, chunk: list[tuple]) -> None:
    db.executemany(
        """INSERT OR IGNORE INTO puzzles (puzzle_id, fen, moves, rating, themes, game_url)
           VALUES (?, ?, ?, ?, ?, ?)""",
        chunk,
    )
    db.commit()


def get_puzzles_for_themes(
    db: sqlite3.Connection,
    themes: list[str],
    rating_range: tuple[int, int],
    limit: int = 20,
) -> list[Puzzle]:
    if not themes:
        return []

    low, high = rating_range
    results: list[Puzzle] = []

    for theme in themes:
        rows = db.execute(
            """SELECT puzzle_id, fen, moves, rating, themes, game_url
               FROM puzzles
               WHERE themes LIKE ?
                 AND rating BETWEEN ? AND ?
               ORDER BY RANDOM()
               LIMIT ?""",
            (f"%{theme}%", low, high, limit),
        ).fetchall()

        for row in rows:
            results.append(Puzzle(
                puzzle_id=row["puzzle_id"],
                fen=row["fen"],
                moves=row["moves"],
                rating=row["rating"],
                themes=row["themes"],
                game_url=row["game_url"],
            ))

    return results
