import io
import sqlite3
from datetime import datetime
from pathlib import Path

import chess
import chess.pgn
import click

from .config import BLUNDER_THRESHOLD_CP, DB_PATH, PUZZLE_CSV_PATH
from .db import init_db
from .ingestion import lichess as lichess_client
from .ingestion import chesscom as chesscom_client
from .ingestion.parser import Game, parse_pgn
from .analysis.engine import analyse_game, ErrorPosition
from .analysis.structural import detect_themes
from .player_model import (
    ThemePerformance,
    get_all_theme_performance,
    upsert_theme_error,
    upsert_theme_result,
)
from .training.puzzle_db import Puzzle, load_puzzle_db
from .training.queue import build_training_queue


@click.group()
def cli() -> None:
    """Patzer — chess improvement through game analysis and spaced repetition."""


@cli.command("import")
@click.argument("username")
@click.option("--source", default="lichess", type=click.Choice(["lichess", "chesscom"]), show_default=True)
@click.option("--max-games", default=50, show_default=True)
@click.option("--db-path", default=None, help="Override database path")
def import_games(username: str, source: str, max_games: int, db_path: str | None) -> None:
    """Fetch, analyse, and store games for USERNAME."""
    resolved_db = Path(db_path) if db_path else DB_PATH
    db = init_db(resolved_db)

    click.echo(f"Fetching up to {max_games} games for {username} from {source}...")

    if source == "lichess":
        pgn_texts = lichess_client.fetch_games(username, max_games=max_games)
    else:
        pgn_texts = chesscom_client.fetch_games(username, max_games=max_games)

    click.echo(f"Fetched {len(pgn_texts)} games. Analysing...")

    _ensure_player(db, username, source)
    player_id = db.execute("SELECT id FROM players WHERE username = ?", (username,)).fetchone()["id"]

    total_errors = 0
    theme_counts: dict[str, int] = {}
    games_analysed = 0

    with click.progressbar(pgn_texts, label="Analysing games") as bar:
        for pgn_text in bar:
            game = parse_pgn(pgn_text, username, source)
            if game is None:
                continue

            # Store game in DB
            game_db_id = _store_game(db, player_id, game)
            if game_db_id is None:
                continue  # duplicate

            # Analyse with Stockfish
            try:
                errors = analyse_game(game)
            except Exception as e:
                click.echo(f"\nWarning: engine error for game {game.game_id}: {e}", err=True)
                errors = []

            # Tag themes and store positions
            for err in errors:
                board = chess.Board(err.fen_before)
                best_move = chess.Move.from_uci(err.best_move)
                themes = detect_themes(board, best_move)

                # Strategic themes for large blunders
                if err.eval_drop_cp >= 200:
                    try:
                        from .analysis.strategic import detect_strategic_themes
                        strategic = detect_strategic_themes(err, game)
                        themes.extend(strategic)
                    except Exception:
                        pass

                themes_str = " ".join(themes)
                db.execute(
                    """INSERT OR IGNORE INTO positions
                       (game_id, move_number, fen_before, fen_after, player_move, best_move, eval_drop_cp, themes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (game_db_id, err.move_number, err.fen_before, err.fen_after,
                     err.player_move, err.best_move, err.eval_drop_cp, themes_str),
                )

                for theme in themes:
                    upsert_theme_error(db, username, theme)
                    theme_counts[theme] = theme_counts.get(theme, 0) + 1

                total_errors += 1

            db.execute("UPDATE games SET analysed = 1 WHERE id = ?", (game_db_id,))
            db.commit()
            games_analysed += 1

    click.echo(f"\nAnalysed {games_analysed} games, found {total_errors} errors across {len(theme_counts)} themes.")
    if theme_counts:
        click.echo("\nTop themes:")
        for theme, count in sorted(theme_counts.items(), key=lambda x: -x[1])[:5]:
            click.echo(f"  {theme}: {count}")


@cli.command("import-puzzles")
@click.argument("csv_path", default=None, required=False)
@click.option("--db-path", default=None, help="Override database path")
def import_puzzles(csv_path: str | None, db_path: str | None) -> None:
    """Bulk import Lichess puzzle CSV."""
    resolved_csv = Path(csv_path) if csv_path else PUZZLE_CSV_PATH
    resolved_db = Path(db_path) if db_path else DB_PATH

    if not resolved_csv.exists():
        click.echo(f"Error: CSV file not found at {resolved_csv}", err=True)
        raise SystemExit(1)

    db = init_db(resolved_db)
    click.echo(f"Importing puzzles from {resolved_csv}...")

    imported = 0
    chunk_size = 100_000

    import csv
    with open(resolved_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        chunk: list[tuple] = []
        for row in reader:
            chunk.append((
                row["PuzzleId"],
                row["FEN"],
                row["Moves"],
                int(row["Rating"]),
                row.get("Themes", ""),
                row.get("GameUrl", ""),
            ))
            if len(chunk) >= 10_000:
                db.executemany(
                    "INSERT OR IGNORE INTO puzzles (puzzle_id, fen, moves, rating, themes, game_url) VALUES (?,?,?,?,?,?)",
                    chunk,
                )
                db.commit()
                imported += len(chunk)
                if imported % chunk_size == 0:
                    click.echo(f"  Imported {imported:,} rows...")
                chunk = []

        if chunk:
            db.executemany(
                "INSERT OR IGNORE INTO puzzles (puzzle_id, fen, moves, rating, themes, game_url) VALUES (?,?,?,?,?,?)",
                chunk,
            )
            db.commit()
            imported += len(chunk)

    click.echo(f"Done. Imported {imported:,} puzzles.")


@cli.command("train")
@click.option("--username", required=True)
@click.option("--count", default=10, show_default=True)
@click.option("--db-path", default=None, help="Override database path")
def train(username: str, count: int, db_path: str | None) -> None:
    """Run a training session with spaced-repetition puzzles."""
    resolved_db = Path(db_path) if db_path else DB_PATH
    db = init_db(resolved_db)

    puzzles = build_training_queue(db, username, n=count)
    if not puzzles:
        click.echo("No puzzles available. Run 'patzer import-puzzles' first.")
        return

    correct_count = 0
    for i, puzzle in enumerate(puzzles, 1):
        click.echo(f"\n--- Puzzle {i}/{len(puzzles)} ---")
        click.echo(f"Rating: {puzzle.rating} | Themes: {puzzle.themes}")
        click.echo()

        board = chess.Board(puzzle.fen)
        solution_moves = puzzle.moves.strip().split()

        # The puzzle always starts with the opponent's move (setup move)
        if solution_moves:
            setup_move = chess.Move.from_uci(solution_moves[0])
            board.push(setup_move)
            solution_moves = solution_moves[1:]

        click.echo(board)
        click.echo()

        if not solution_moves:
            click.echo("No solution available for this puzzle, skipping.")
            continue

        player_to_move = "White" if board.turn == chess.WHITE else "Black"
        click.echo(f"{player_to_move} to move.")

        answer = click.prompt("Your move (UCI, e.g. e2e4, or 'skip')")

        if answer.lower() == "skip":
            click.echo(f"Skipped. Best move was: {solution_moves[0]}")
            theme_name = _primary_theme(puzzle.themes)
            upsert_theme_result(db, username, theme_name, correct=False, quality=0)
            _log_training(db, username, puzzle, theme_name, correct=False, quality=0)
            continue

        correct_move = solution_moves[0]
        is_correct = answer.strip().lower() == correct_move.lower()

        if is_correct:
            click.echo("Correct!")
            correct_count += 1
            quality = 4
        else:
            click.echo(f"Incorrect. Best move was: {correct_move}")
            quality = 1

        theme_name = _primary_theme(puzzle.themes)
        upsert_theme_result(db, username, theme_name, correct=is_correct, quality=quality)
        _log_training(db, username, puzzle, theme_name, correct=is_correct, quality=quality)

    click.echo(f"\nSession complete: {correct_count}/{len(puzzles)} correct.")


@cli.command("status")
@click.option("--username", required=True)
@click.option("--db-path", default=None, help="Override database path")
def status(username: str, db_path: str | None) -> None:
    """Show theme performance table for a player."""
    resolved_db = Path(db_path) if db_path else DB_PATH
    db = init_db(resolved_db)

    perf = get_all_theme_performance(db, username)
    if not perf:
        click.echo(f"No data for {username}. Run 'patzer import' first.")
        return

    click.echo(f"\nTheme performance for {username}:\n")
    header = f"{'Theme':<20} {'Attempts':>8} {'Correct':>8} {'Accuracy':>9} {'Errors':>7} {'Due':>12}"
    click.echo(header)
    click.echo("-" * len(header))

    for t in sorted(perf, key=lambda x: x.accuracy):
        accuracy_pct = f"{t.accuracy * 100:.0f}%"
        due = t.sr_due_date or "-"
        click.echo(
            f"{t.theme_name:<20} {t.attempts:>8} {t.correct:>8} {accuracy_pct:>9} {t.game_errors:>7} {due:>12}"
        )


# --- Helpers ---

def _ensure_player(db: sqlite3.Connection, username: str, source: str) -> None:
    db.execute(
        "INSERT OR IGNORE INTO players (username, source) VALUES (?, ?)",
        (username, source),
    )
    db.commit()


def _store_game(db: sqlite3.Connection, player_id: int, game: Game) -> int | None:
    played_at = game.headers.get("UTCDate", game.headers.get("Date", ""))
    try:
        db.execute(
            """INSERT INTO games (player_id, game_id, source, result, time_control, played_at, pgn_text)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (player_id, game.game_id, game.source, game.result,
             game.time_control, played_at or None, game.pgn_text),
        )
        db.commit()
        row = db.execute(
            "SELECT id FROM games WHERE game_id = ? AND source = ?",
            (game.game_id, game.source),
        ).fetchone()
        return row["id"] if row else None
    except Exception:
        return None


def _primary_theme(themes_str: str) -> str:
    themes = themes_str.strip().split()
    if themes:
        return themes[0]
    return "general"


def _log_training(
    db: sqlite3.Connection,
    username: str,
    puzzle: Puzzle,
    theme_name: str,
    correct: bool,
    quality: int,
) -> None:
    row = db.execute("SELECT id FROM players WHERE username = ?", (username,)).fetchone()
    if row is None:
        return
    player_id = row["id"]
    db.execute(
        """INSERT INTO training_log (player_id, puzzle_id, theme_name, correct, quality)
           VALUES (?, ?, ?, ?, ?)""",
        (player_id, puzzle.puzzle_id, theme_name, 1 if correct else 0, quality),
    )
    db.commit()
