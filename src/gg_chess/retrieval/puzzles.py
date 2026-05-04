"""Lichess puzzle DB indexer and search.

Source CSV: https://database.lichess.org/lichess_db_puzzle.csv.zst
Path is configured via PUZZLE_CSV_PATH in config.py.

Schema (one row per puzzle):
  PuzzleId,FEN,Moves,Rating,RatingDeviation,Popularity,NbPlays,
  Themes,GameUrl,OpeningTags

Themes are space-separated tags ("fork middlegame short" etc) — see
https://github.com/lichess-org/lila/blob/master/translation/source/puzzleTheme.xml
for the full taxonomy.

The indexer loads the CSV once into the `puzzles` table (schema in db.py).
puzzle_search() is a thin SQL wrapper used as an LLM tool.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


# ── Indexer (run once) ─────────────────────────────────────────────────────────

def index_puzzles(csv_path: Path, db: sqlite3.Connection, batch_size: int = 5000) -> int:
    """Load the Lichess puzzle CSV into the `puzzles` table.

    Idempotent: uses INSERT OR IGNORE on PuzzleId.

    Args:
        csv_path: path to lichess_db_puzzle.csv (decompressed).
        db:       open sqlite3 connection (init_db will create the table).
        batch_size: rows per executemany.

    Returns:
        Number of new puzzles inserted.
    """
    raise NotImplementedError


# ── LLM tool ───────────────────────────────────────────────────────────────────

def puzzle_search(
    themes: list[str] | None = None,
    rating_min: int = 800,
    rating_max: int = 3000,
    color_to_move: str | None = None,
    count: int = 1,
) -> dict:
    """Sample puzzles by theme and rating.

    Returns:
        {
          "puzzles": [
            {
              "puzzle_id": str,
              "fen":       str,
              "moves_uci": [str, ...],   # solution sequence; first is opponent's setup move,
                                         # subsequent moves alternate (player solves odd indices)
              "rating":    int,
              "themes":    [str, ...],
              "game_url":  str,
            }, ...
          ],
          "matched_count": int,          # how many puzzles matched the filter (may exceed count)
        }

    Args:
        themes: list of Lichess theme tags to require (AND-match). None = any.
        rating_min, rating_max: inclusive rating window.
        color_to_move: 'white' | 'black' | None — filter by side to move at puzzle start
                       (note: in Lichess puzzles, the "first move" is the OPPONENT's;
                       the side that solves is the OTHER colour. Account for that here.)
        count: how many to return (random sample within the filter).
    """
    raise NotImplementedError
