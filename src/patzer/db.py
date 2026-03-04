import sqlite3
from pathlib import Path

from .config import DB_PATH

DDL = """
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(id),
    game_id TEXT NOT NULL,
    source TEXT NOT NULL,
    result TEXT NOT NULL,
    time_control TEXT,
    played_at TIMESTAMP,
    pgn_text TEXT NOT NULL,
    analysed INTEGER DEFAULT 0,
    UNIQUE(game_id, source)
);

CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL REFERENCES games(id),
    move_number INTEGER NOT NULL,
    fen_before TEXT NOT NULL,
    fen_after TEXT NOT NULL,
    player_move TEXT NOT NULL,
    best_move TEXT NOT NULL,
    eval_drop_cp INTEGER NOT NULL,
    themes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS player_themes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(id),
    theme_name TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    correct INTEGER NOT NULL DEFAULT 0,
    game_errors INTEGER NOT NULL DEFAULT 0,
    last_seen TIMESTAMP,
    sr_interval INTEGER NOT NULL DEFAULT 1,
    sr_easiness REAL NOT NULL DEFAULT 2.5,
    sr_repetitions INTEGER NOT NULL DEFAULT 0,
    sr_due_date DATE,
    UNIQUE(player_id, theme_name)
);

CREATE TABLE IF NOT EXISTS puzzles (
    puzzle_id TEXT PRIMARY KEY,
    fen TEXT NOT NULL,
    moves TEXT NOT NULL,
    rating INTEGER NOT NULL,
    themes TEXT NOT NULL DEFAULT '',
    game_url TEXT
);
CREATE INDEX IF NOT EXISTS idx_puzzles_rating ON puzzles(rating);
CREATE INDEX IF NOT EXISTS idx_puzzles_themes ON puzzles(themes);

CREATE TABLE IF NOT EXISTS training_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(id),
    puzzle_id TEXT NOT NULL REFERENCES puzzles(puzzle_id),
    theme_name TEXT NOT NULL,
    correct INTEGER NOT NULL,
    quality INTEGER NOT NULL,
    attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def get_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = get_db(db_path)
    conn.executescript(DDL)
    conn.commit()
    return conn
