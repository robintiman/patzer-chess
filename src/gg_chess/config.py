import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

STOCKFISH_PATH: str = os.getenv("STOCKFISH_PATH", "stockfish")

DB_PATH: Path = Path(
    os.getenv("GG_CHESS_DB_PATH", Path.home() / ".local" / "share" / "gg-chess" / "gg-chess.db")
)

PUZZLE_CSV_PATH: Path = Path(
    os.getenv("PUZZLE_CSV_PATH", "./data/lichess_db_puzzle.csv")
)

STOCKFISH_THREADS: int = int(os.getenv("STOCKFISH_THREADS", os.cpu_count() or 1))
STOCKFISH_HASH: int = int(os.getenv("STOCKFISH_HASH", 256))  # MB

STOCKFISH_NODES: int = 1_500_000      # Full analysis node budget (≈ depth 23-27, adaptive)
STOCKFISH_NODES_SCAN: int = 500_000   # Pass-1 quick scan to find best move
STOCKFISH_NODES_AFTER: int = 300_000  # Post-move eval for blunder confirmation

# Win-probability thresholds (Lichess methodology)
BLUNDER_WIN_PCT_THRESHOLD: float = 30.0
MISTAKE_WIN_PCT_THRESHOLD: float = 20.0
INACCURACY_WIN_PCT_THRESHOLD: float = 10.0

CLAUDE_CONCEPT_MODEL: str = "claude-haiku-4-5-20251001"  # Fast model for structured concept extraction
CLAUDE_CHAT_MODEL: str = "claude-opus-4-6"               # High-quality model for interactive chat

USE_LOCAL_MODEL: bool = os.getenv("USE_LOCAL_MODEL", "false").lower() == "true"
LOCAL_MODEL_NAME: str = os.getenv("LOCAL_MODEL_NAME", "qwen3:30b")
MULTI_PV_COUNT: int = 3

# ── Coach / retrieval assets ──────────────────────────────────────────────────

# Polyglot opening book (.bin). See retrieval/openings.py.
OPENING_BOOK_PATH: Path = Path(
    os.getenv("OPENING_BOOK_PATH", "./data/book.bin")
)

# Syzygy tablebase directory (contains .rtbw / .rtbz files). Empty = disabled.
TABLEBASE_PATH: str = os.getenv("TABLEBASE_PATH", "")

# Lessons + endgame-drill JSON.
LESSONS_DIR: Path = Path(os.getenv("LESSONS_DIR", "./data/lessons"))
ENDGAME_DRILLS_DIR: Path = Path(os.getenv("ENDGAME_DRILLS_DIR", "./data/endgames"))

# ── Vocabulary thresholds (cp) ────────────────────────────────────────────────
# Used by move_judge.classify_move and by the coach system prompt to ground
# adjectives like "winning", "decisive", "blunder" in concrete numbers.
EVAL_DECISIVE_CP: int = 500
EVAL_WINNING_CP:  int = 200
EVAL_EQUAL_CP:    int = 50

CP_LOSS_BLUNDER:    int = 200
CP_LOSS_MISTAKE:    int = 100
CP_LOSS_INACCURACY: int = 50
CP_LOSS_GOOD:       int = 20
