import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

STOCKFISH_PATH: str = os.getenv("STOCKFISH_PATH", "stockfish")

DB_PATH: Path = Path(
    os.getenv("PATZER_DB_PATH", Path.home() / ".local" / "share" / "patzer" / "patzer.db")
)

PUZZLE_CSV_PATH: Path = Path(
    os.getenv("PUZZLE_CSV_PATH", "./data/lichess_db_puzzle.csv")
)

STOCKFISH_DEPTH: int = 18
BLUNDER_THRESHOLD_CP: int = 150
CLAUDE_MODEL: str = "claude-opus-4-6"
