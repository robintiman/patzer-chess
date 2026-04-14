"""Generate a labeled concept dataset from puzzle and game positions.

Usage:
    python -m gg_chess.probing.dataset [--db PATH] [--out PATH] [--games]

Reads positions from:
  1. puzzles table (always) — uses Lichess theme labels + programmatic detectors
  2. games table PGNs (if --games is set) — programmatic detectors only

Writes one JSON object per line to the output file:
  {"fen": "...", "side_to_move": "white", "source": "lichess_puzzle",
   "source_id": "abc123", "labels": {"Pin": true, "Fork": false, ...}}
"""

import argparse
import io
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import chess
import chess.pgn

from gg_chess.config import DB_PATH
from gg_chess.db import get_db
from gg_chess.probing.labeler import (
    LICHESS_COVERED_CONCEPTS,
    label_from_lichess_themes,
    label_position_programmatic,
)

_DEFAULT_OUT = Path(__file__).parent.parent.parent.parent / "data" / "concept_labels.jsonl"


# ---------------------------------------------------------------------------
# Puzzle positions
# ---------------------------------------------------------------------------

def _puzzle_position(fen: str, moves_str: str) -> chess.Board | None:
    """Return the board state where the solver needs to find the tactic.

    In the Lichess puzzle DB the FEN is the game position right before the
    opponent's last move.  The first move in `moves` is that opponent move;
    subsequent moves are the solution. We apply the first move to reach the
    actual puzzle start position.
    """
    try:
        board = chess.Board(fen)
        first_move = chess.Move.from_uci(moves_str.split()[0])
        board.push(first_move)
        return board
    except Exception:
        return None


def generate_from_puzzles(conn: sqlite3.Connection):
    """Yield labeled records from the puzzles table."""
    rows = conn.execute("SELECT puzzle_id, fen, moves, themes FROM puzzles").fetchall()
    for row in rows:
        board = _puzzle_position(row["fen"], row["moves"])
        if board is None:
            continue

        color = board.turn
        side = "white" if color == chess.WHITE else "black"

        tags = row["themes"]

        yield {
            "fen": board.fen(),
            "side_to_move": side,
            "source": "lichess_puzzle",
            "source_id": row["puzzle_id"],
            "labels": labels,
        }


# ---------------------------------------------------------------------------
# Game positions
# ---------------------------------------------------------------------------

def generate_from_games(conn: sqlite3.Connection, every_n: int = 5):
    """Yield labeled records extracted from stored game PGNs.

    Samples every `every_n`-th half-move from each game to get a diverse
    spread of positions. Uses programmatic detectors only (no theme labels).
    """
    rows = conn.execute("SELECT id, pgn_text FROM games").fetchall()
    for row in rows:
        pgn_game = chess.pgn.read_game(io.StringIO(row["pgn_text"]))
        if pgn_game is None:
            continue
        board = pgn_game.board()
        half_move = 0
        for node in pgn_game.mainline():
            board.push(node.move)
            half_move += 1
            if half_move % every_n != 0:
                continue
            color = board.turn
            side = "white" if color == chess.WHITE else "black"
            labels = label_position_programmatic(board, color)
            yield {
                "fen": board.fen(),
                "side_to_move": side,
                "source": "game",
                "source_id": f"{row['id']}:{half_move}",
                "labels": labels,
            }


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _print_summary(records: list[dict]) -> None:
    total = len(records)
    print(f"\nTotal positions: {total}")
    if total == 0:
        return

    # Collect all concept names present across records
    all_concepts: set[str] = set()
    for r in records:
        all_concepts.update(r["labels"].keys())

    counts: dict[str, int] = defaultdict(int)
    for r in records:
        for concept, val in r["labels"].items():
            if val:
                counts[concept] += 1

    print(f"\n{'Concept':<35} {'True':>7} {'%':>6}")
    print("-" * 52)
    for concept in sorted(all_concepts):
        n = counts[concept]
        pct = 100 * n / total
        flag = " !" if pct > 95 or (n > 0 and pct < 5) else ""
        print(f"{concept:<35} {n:>7}  {pct:>5.1f}%{flag}")

    print()
    sources: dict[str, int] = defaultdict(int)
    for r in records:
        sources[r["source"]] += 1
    for src, n in sorted(sources.items()):
        print(f"  {src}: {n} positions")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate chess concept labels dataset")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="SQLite DB path")
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT, help="Output JSONL path")
    parser.add_argument("--games", action="store_true", help="Also extract positions from games table")
    args = parser.parse_args()

    if not args.db.exists():
        print(f"Error: DB not found at {args.db}", file=sys.stderr)
        sys.exit(1)

    args.out.parent.mkdir(parents=True, exist_ok=True)

    conn = get_db(args.db)
    records: list[dict] = []

    print("Loading puzzle positions...")
    puzzle_count = 0
    for record in generate_from_puzzles(conn):
        records.append(record)
        puzzle_count += 1
        if puzzle_count % 10_000 == 0:
            print(f"  {puzzle_count} puzzles processed...")
    print(f"  {puzzle_count} puzzle positions loaded.")

    if args.games:
        print("Loading game positions...")
        game_count = 0
        for record in generate_from_games(conn):
            records.append(record)
            game_count += 1
        print(f"  {game_count} game positions loaded.")

    print(f"\nWriting {len(records)} records to {args.out} ...")
    with args.out.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, separators=(",", ":")) + "\n")

    _print_summary(records)
    print(f"\nDone. Output: {args.out}")


if __name__ == "__main__":
    main()
