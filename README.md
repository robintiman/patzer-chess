# Patzer

**Your personal chess pattern library — built from your games, organised by theme, designed to fill the exact gaps in your knowledge.**

---

## The Science

Chess skill is fundamentally about pattern recognition, not calculation depth (de Groot 1965, Chase & Simon 1973). Masters have roughly 50,000 stored patterns — chunks and templates that enable near-instant position recognition. Every effective training method (tactics drilling, studying master games, endgame repetition) is pattern library construction in disguise.

The question every chess player should be asking: which patterns am I missing, and what's the fastest way to build them?

---

## The Problem with Current Tools

They don't know which patterns you're missing.

Generic puzzle queues serve everyone the same content regardless of individual gaps. Game analysis tools show blunders but don't identify the missing pattern behind each one. No tool connects your mistakes in games to the specific training you actually need.

---

## What Patzer Does

Patzer analyses all your games to map which themes you handle well and which you don't. It identifies your specific pattern gaps — not "you need tactics", but "you miss deflections and mishandle IQP positions as defender". Every puzzle and position in your training queue addresses a real gap in your pattern library. When AI explains a position, it explains it in terms of the pattern at stake — building understanding, not just move memory.

---

## The Pattern Library Model

Themes are the organising unit — the atomic unit of chess knowledge.

**Tactical themes** — fork, pin, skewer, deflection, decoy, overloading, clearance, back-rank, mating patterns, and more. Sourced from the Lichess puzzle database (3.5M tagged puzzles).

**Strategic themes** — IQP (attack and defence), minority attack, pawn storm, outpost, bishop pair, exchange sacrifice, opposite castling, open file, and more. Detected from your games.

**Endgame themes** — Lucena, Philidor, opposition, triangulation, outside passed pawn, and more.

For each theme, the player model tracks attempts, accuracy, last seen, and spaced repetition due date. Gap detection works by cross-referencing game errors with the theme taxonomy to surface exactly what's missing.

---

## Core Features

- **Game ingestion** — Lichess and Chess.com APIs
- **Automatic theme tagging** — structural detection via python-chess, strategic detection via Claude
- **Personalised training queue** — spaced repetition targeting weakest themes (85% difficulty rule)
- **AI explanations grounded in theme** — "this is a deflection — the idea is to remove the piece doing two jobs at once"
- **Post-game coaching** — Socratic analysis before engine reveal
- **Psychological patterns** — tilt detection, time pressure analysis

---

## Architecture

```
Data sources
├── Your games        → Lichess API / Chess.com API
├── Puzzle database   → Lichess open puzzle DB (3.5M tagged)
└── GM games          → TWIC / public PGN archives

Processing
├── python-chess      → move validation, structural theme detection
├── Stockfish         → position evaluation, error detection
└── Claude            → strategic theme detection, explanations, coaching

Player model
├── Theme performance map (tactics + strategy + endgames)
├── Spaced repetition scheduler
└── Psychological pattern tracker

Interface (TBD — CLI first, web later)
├── Game import + analysis
├── Training queue (daily puzzles by theme)
└── Conversational coach
```

---

## Data Sources

- Lichess API: https://lichess.org/api (free, no auth for public games)
- Chess.com published data API: https://www.chess.com/news/view/published-data-api
- Lichess puzzle DB: https://database.lichess.org/#puzzles (free download, CSV)
- TWIC (This Week in Chess): https://theweekinchess.com/twic

---

## Tech Stack

- Python backend (python-chess, Stockfish wrapper, Anthropic SDK)
- SQLite for player model storage — simple, local, no infrastructure required
- Claude API (`claude-opus-4-6`) for coaching and strategic analysis
- Stockfish for position evaluation

---

## Roadmap

**Phase 1 — MVP** *(complete)*
Game ingestion → theme tagging → player model → basic training queue

**Phase 2 — AI coaching layer**
Post-game analysis → conversational Q&A → explanation quality

**Phase 3 — Polish**
Web UI → full spaced repetition → psychological patterns

Phases 2 and 3 are directional. Phase 1 is the commitment.

---

## Getting Started

### Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Stockfish installed and on your PATH (see below)
- An [Anthropic API key](https://console.anthropic.com/) (for strategic theme detection)

### Installing Stockfish

**macOS:**
```bash
brew install stockfish
```

**Ubuntu/Debian:**
```bash
sudo apt install stockfish
```

**Arch Linux:**
```bash
sudo pacman -S stockfish
```

**Windows:** download the binary from https://stockfishchess.org/download/ and add the folder to your `PATH`.

Verify it works: `stockfish` should open the UCI prompt (Ctrl-C to exit).

If Stockfish is installed at a non-standard path, set the environment variable:
```
STOCKFISH_PATH=/path/to/stockfish
```

### Installation

```bash
git clone <repo>
cd unnamed-chess-project
uv sync
```

Copy `.env.example` to `.env` and add your API key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

### Usage

**Import your games and analyse them:**

```bash
uv run patzer import <username> --source lichess --max-games 50
uv run patzer import <username> --source chesscom --max-games 50
```

This fetches your games, runs Stockfish analysis, detects tactical and strategic themes, and builds your player model.

**Import the Lichess puzzle database:**

Download the CSV from https://database.lichess.org/#puzzles, place it in `data/`, then:

```bash
uv run patzer import-puzzles ./data/lichess_db_puzzle.csv
```

**Check your theme performance:**

```bash
uv run patzer status --username <username>
```

Prints a table of all tracked themes with attempt count, accuracy, game error count, and next spaced repetition due date.

**Run a training session:**

```bash
uv run patzer train --username <username> --count 10
```

Shows puzzles targeting your weakest themes. Enter moves in UCI notation (e.g. `e2e4`). Results update your spaced repetition schedule.

### Development

```bash
uv sync --extra dev
uv run pytest tests/ -v
```
