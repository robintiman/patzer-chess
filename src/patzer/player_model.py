import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

from .training.scheduler import SM2State, calculate_next_review


@dataclass
class ThemePerformance:
    theme_name: str
    attempts: int
    correct: int
    game_errors: int
    accuracy: float          # 0.0 – 1.0
    sr_interval: int
    sr_easiness: float
    sr_repetitions: int
    sr_due_date: str | None


def _ensure_player(db: sqlite3.Connection, username: str, source: str = "lichess") -> int:
    db.execute(
        "INSERT OR IGNORE INTO players (username, source) VALUES (?, ?)",
        (username, source),
    )
    db.commit()
    row = db.execute("SELECT id FROM players WHERE username = ?", (username,)).fetchone()
    return row["id"]


def upsert_theme_error(db: sqlite3.Connection, username: str, theme: str) -> None:
    player_id = _ensure_player(db, username)
    db.execute(
        """INSERT INTO player_themes (player_id, theme_name, game_errors)
           VALUES (?, ?, 1)
           ON CONFLICT(player_id, theme_name)
           DO UPDATE SET game_errors = game_errors + 1,
                         last_seen = CURRENT_TIMESTAMP""",
        (player_id, theme),
    )
    db.commit()


def upsert_theme_result(
    db: sqlite3.Connection,
    username: str,
    theme: str,
    correct: bool,
    quality: int,
) -> None:
    player_id = _ensure_player(db, username)

    row = db.execute(
        """SELECT sr_interval, sr_easiness, sr_repetitions
           FROM player_themes
           WHERE player_id = ? AND theme_name = ?""",
        (player_id, theme),
    ).fetchone()

    if row:
        state = SM2State(
            interval=row["sr_interval"],
            easiness=row["sr_easiness"],
            repetitions=row["sr_repetitions"],
        )
    else:
        state = SM2State(interval=1, easiness=2.5, repetitions=0)

    new_state = calculate_next_review(state, quality)
    due_date = (date.today() + timedelta(days=new_state.interval)).isoformat()

    db.execute(
        """INSERT INTO player_themes (player_id, theme_name, attempts, correct, sr_interval, sr_easiness, sr_repetitions, sr_due_date, last_seen)
           VALUES (?, ?, 1, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(player_id, theme_name)
           DO UPDATE SET
               attempts = attempts + 1,
               correct = correct + ?,
               sr_interval = ?,
               sr_easiness = ?,
               sr_repetitions = ?,
               sr_due_date = ?,
               last_seen = CURRENT_TIMESTAMP""",
        (
            player_id, theme, 1 if correct else 0,
            new_state.interval, new_state.easiness, new_state.repetitions, due_date,
            1 if correct else 0,
            new_state.interval, new_state.easiness, new_state.repetitions, due_date,
        ),
    )
    db.commit()


def get_weakest_themes(db: sqlite3.Connection, username: str, n: int = 5) -> list[ThemePerformance]:
    all_perf = get_all_theme_performance(db, username)
    # Sort by accuracy ascending (worst first), then by game_errors descending
    sorted_perf = sorted(all_perf, key=lambda t: (t.accuracy, -t.game_errors))
    return sorted_perf[:n]


def get_all_theme_performance(db: sqlite3.Connection, username: str) -> list[ThemePerformance]:
    row = db.execute("SELECT id FROM players WHERE username = ?", (username,)).fetchone()
    if row is None:
        return []

    player_id = row["id"]
    rows = db.execute(
        """SELECT theme_name, attempts, correct, game_errors,
                  sr_interval, sr_easiness, sr_repetitions, sr_due_date
           FROM player_themes
           WHERE player_id = ?
           ORDER BY theme_name""",
        (player_id,),
    ).fetchall()

    result = []
    for r in rows:
        attempts = r["attempts"]
        correct = r["correct"]
        accuracy = correct / attempts if attempts > 0 else 0.0
        result.append(ThemePerformance(
            theme_name=r["theme_name"],
            attempts=attempts,
            correct=correct,
            game_errors=r["game_errors"],
            accuracy=accuracy,
            sr_interval=r["sr_interval"],
            sr_easiness=r["sr_easiness"],
            sr_repetitions=r["sr_repetitions"],
            sr_due_date=r["sr_due_date"],
        ))

    return result
