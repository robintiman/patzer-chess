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

STOCKFISH_NODES: int = 1_500_000      # Full analysis node budget (≈ depth 23-27, adaptive)
STOCKFISH_NODES_SCAN: int = 500_000   # Pass-1 quick scan to find best move
STOCKFISH_NODES_AFTER: int = 300_000  # Post-move eval for blunder confirmation

# Win-probability thresholds (Lichess methodology)
BLUNDER_WIN_PCT_THRESHOLD: float = 30.0
MISTAKE_WIN_PCT_THRESHOLD: float = 20.0
INACCURACY_WIN_PCT_THRESHOLD: float = 10.0

CLAUDE_CONCEPT_MODEL: str = "claude-haiku-4-5-20251001"  # Fast model for structured concept extraction
CLAUDE_CHAT_MODEL: str = "claude-opus-4-6"               # High-quality model for interactive chat
MULTI_PV_COUNT: int = 3
