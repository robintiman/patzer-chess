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
    interest_score REAL,
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
    win_pct_drop REAL NOT NULL DEFAULT 0,
    move_classification TEXT NOT NULL DEFAULT 'blunder',
    pv_san TEXT NOT NULL DEFAULT '',
    alt_pvs_san TEXT NOT NULL DEFAULT '',
    concept_name TEXT NOT NULL DEFAULT '',
    concept_explanation TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS game_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    phase TEXT NOT NULL DEFAULT 'self_analysis',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    UNIQUE(game_id)
);

CREATE TABLE IF NOT EXISTS move_evals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    half_move_index INTEGER NOT NULL,
    eval_cp INTEGER NOT NULL,
    UNIQUE(game_id, half_move_index)
);

CREATE TABLE IF NOT EXISTS move_annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    move_number INTEGER NOT NULL,
    fen_before TEXT NOT NULL,
    user_thought TEXT NOT NULL DEFAULT '',
    error_classification TEXT NOT NULL DEFAULT '',
    error_type TEXT NOT NULL DEFAULT '',
    annotated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_id, move_number)
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
    return conn
