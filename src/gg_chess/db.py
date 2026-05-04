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

-- ── Coach / retrieval tables ──────────────────────────────────────────────────

-- Lichess puzzle DB. Loaded once via retrieval/puzzles.index_puzzles().
CREATE TABLE IF NOT EXISTS puzzles (
    puzzle_id   TEXT PRIMARY KEY,
    fen         TEXT NOT NULL,
    moves_uci   TEXT NOT NULL,            -- space-separated
    rating      INTEGER NOT NULL,
    rating_dev  INTEGER NOT NULL DEFAULT 0,
    popularity  INTEGER NOT NULL DEFAULT 0,
    nb_plays    INTEGER NOT NULL DEFAULT 0,
    themes      TEXT NOT NULL DEFAULT '', -- space-separated tags
    opening_tag TEXT NOT NULL DEFAULT '',
    game_url    TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_puzzles_rating ON puzzles(rating);
-- Themes are queried with `themes LIKE '%fork%'`. For large-scale theme search,
-- consider an FTS5 virtual table (see COACH_IMPLEMENTATION.md).

-- Per-user persistent record. One row per user.
CREATE TABLE IF NOT EXISTS student_state (
    user_id          TEXT PRIMARY KEY,
    rating_estimate  INTEGER NOT NULL DEFAULT 1200,
    current_lesson   TEXT,
    current_puzzle   TEXT,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Per-attempt history. Drives weak-theme detection.
CREATE TABLE IF NOT EXISTS student_attempts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT NOT NULL,
    mode        TEXT NOT NULL,            -- "puzzle" | "qa" | "spar" | "lesson" | "review" | "opening" | "endgame"
    fen         TEXT NOT NULL,
    user_move   TEXT NOT NULL DEFAULT '',
    correct     INTEGER NOT NULL DEFAULT 0,
    cp_loss     INTEGER NOT NULL DEFAULT 0,
    themes      TEXT NOT NULL DEFAULT '', -- space-separated
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_attempts_user ON student_attempts(user_id, created_at DESC);

-- Lesson progress (resumable themed lessons).
CREATE TABLE IF NOT EXISTS lesson_progress (
    user_id      TEXT NOT NULL,
    lesson_id    TEXT NOT NULL,
    step_index   INTEGER NOT NULL DEFAULT 0,
    completed    INTEGER NOT NULL DEFAULT 0,
    started_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    PRIMARY KEY (user_id, lesson_id)
);

-- User opening repertoire: expected reply at each FEN.
CREATE TABLE IF NOT EXISTS opening_repertoire (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT NOT NULL,
    fen             TEXT NOT NULL,         -- canonicalised (no halfmove/fullmove)
    side            TEXT NOT NULL,         -- 'white' | 'black' (which side user is training)
    expected_uci    TEXT NOT NULL,
    note            TEXT NOT NULL DEFAULT '',
    UNIQUE(user_id, fen, side)
);
CREATE INDEX IF NOT EXISTS ix_repertoire_user ON opening_repertoire(user_id, side);
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
