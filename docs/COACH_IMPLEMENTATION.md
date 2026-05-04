# Coach Implementation Plan

This document is the build context for the general AI chess coach. It assumes
you have read `src/gg_chess/analysis/teach.py` (the existing tool-use loop)
and `src/gg_chess/analysis/tools.py` (the existing tool registry).

## Mental model

> **The LLM never knows chess.** It is an orchestrator and explainer; a
> deterministic chess oracle (python-chess + Stockfish + Syzygy + curated
> data) holds all truth. Every concrete claim — a move, an evaluation, a
> piece relationship, an adjective like "winning" — must trace back to a
> tool call.

Three layers, top-down:

```
┌──────────────────────────────────────────────────────────────────┐
│  Web routes  (Flask)                                             │
│    /api/coach/{qa,review,puzzle,lesson,spar,opening,endgame}     │
└──────────────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────────────────────────────────────────┐
│  Coach orchestration  (src/gg_chess/coach/)                      │
│    router → mode handler → tool-use loop → sanitizer → auditor   │
│    + student model (per-user persistent record)                  │
└──────────────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────────────────────────────────────────┐
│  Ground-truth tools  (src/gg_chess/analysis/, retrieval/)        │
│    structure / move_judge / tactics / puzzles / openings / TB    │
│    Stockfish handle managed by analysis/tools.set_engine()       │
└──────────────────────────────────────────────────────────────────┘
```

The LLM sees only the tool layer. The coach layer wraps a tool-use loop
with state and validation. Routes are thin.

## File map

### Already implemented (do not rewrite)

| File | Purpose |
|---|---|
| `src/gg_chess/analysis/engine.py` | Game-wide error finder + eval sweep. Powers `/api/analyse-game/<id>`. |
| `src/gg_chess/analysis/llm.py` | Generic `run_tool_use_loop` + `chat_stream` for Anthropic + Ollama. |
| `src/gg_chess/analysis/teach.py` | Q&A tool-use loop with `_validate_demo_moves`. The new `coach.modes.qa` is a refactor of this. |
| `src/gg_chess/analysis/tools.py` | Tool registry. Now imports the new modules. |
| `src/gg_chess/analysis/interest.py` | Game interest scoring. |

### New stubs (implement these)

| File | Status | Notes |
|---|---|---|
| `analysis/structure.py` | stub | Pure python-chess. No engine. |
| `analysis/move_judge.py` | stub | Calls Stockfish via `tools._engine`. |
| `analysis/tactics.py` | stub (restored) | Engine + motif tagger. |
| `retrieval/puzzles.py` | stub | One-time CSV → SQLite indexer + search. |
| `retrieval/openings.py` | stub | Polyglot book + ECO names. |
| `retrieval/tablebase.py` | stub | Syzygy via python-chess. |
| `coach/student.py` | stub | Persistent per-user record. |
| `coach/sanitizer.py` | stub | Move-token verifier. |
| `coach/auditor.py` | stub | LLM-based claim verifier. |
| `coach/router.py` | stub | Mode dispatch. |
| `coach/modes/qa.py` | stub | Refactor of `teach.teach_position`. |
| `coach/modes/review.py` | stub | Game-review narration pass. |
| `coach/modes/puzzle.py` | stub | Puzzle session state machine. |
| `coach/modes/lesson.py` | stub | Scripted themed lessons. |
| `coach/modes/spar.py` | stub | Practice vs Stockfish at target Elo. |
| `coach/modes/opening.py` | stub | Repertoire trainer. |
| `coach/modes/endgame.py` | stub | Tablebase-judged drills. |

### Modified existing files

- `db.py`: added `puzzles`, `student_state`, `student_attempts`,
  `lesson_progress`, `opening_repertoire` tables.
- `config.py`: added `OPENING_BOOK_PATH`, `TABLEBASE_PATH`, `LESSONS_DIR`,
  `ENDGAME_DRILLS_DIR`, vocabulary thresholds (`EVAL_*_CP`, `CP_LOSS_*`).
- `web/routes.py`: appended `/api/coach/*` stubs that delegate to
  `coach.router.handle_turn`.

## Build order (dependencies first)

The work falls into seven waves. Each wave ends in a green test.

1. **Structure tools** (`analysis/structure.py`)
   - No external deps. Pure python-chess.
   - Quickest win; unlocks `describe_position` for system-prompt prefixing.
   - **Test**: feed each function a small set of hand-checked FENs.

2. **Move judgment** (`analysis/move_judge.py`)
   - Depends on Stockfish handle from `tools.set_engine`.
   - `classify_move` is the highest-leverage tool — it powers the
     candidate-move flow on its own.
   - **Test**: for a known blunder FEN, assert `classification == "blunder"`
     and `cp_loss >= CP_LOSS_BLUNDER`.

3. **Sanitizer + describe_position prefixing** (`coach/sanitizer.py`,
   small edit to `analysis/teach.py`)
   - Generalise the `_validate_demo_moves` pattern from `teach.py`.
   - Inject `structure.describe_position(fen).ascii` into the system prompt.
   - **Test**: hand-craft a draft mentioning an illegal move; assert
     sanitizer flags it.

4. **Tactics + retrieval** (`analysis/tactics.py`, `retrieval/`)
   - Tactics first (motif tagging is finicky; ship a small motif set first
     and grow it).
   - Puzzle indexer is a one-shot CLI: `python -m gg_chess.retrieval.puzzles
     index $PUZZLE_CSV_PATH`. Add to `pyproject.toml` scripts.
   - Openings: ship Polyglot first (no network); the ECO-name JSON can
     come later.
   - Tablebase: optional — gate on `TABLEBASE_PATH != ""`.

5. **Student model** (`coach/student.py`)
   - Mostly straight SQL. Use `init_db` to ensure tables exist.
   - Pick a fixed-K Elo (K=32) for `update_rating_estimate`; revisit later.

6. **Coach router + qa/puzzle modes** (`coach/router.py`,
   `coach/modes/{qa,puzzle}.py`)
   - These two modes are the MVP. Lesson/spar/opening/endgame can ship
     iteratively after.
   - QA is a port of `teach.py`; puzzle is the new state machine.

7. **Auditor + review/lesson/spar/opening/endgame** (the rest)
   - Auditor is a quality multiplier — wire it in last, only for modes
     that emit long-form narration (review, lesson summary).
   - Modes can be implemented in any order after the MVP.

## Per-module guidance

### `analysis/structure.py`

- `pawn_structure`: a square is *isolated* if no friendly pawns on adjacent
  files. *Backward* if the pawn cannot advance safely and friendly pawns
  on adjacent files are on higher ranks. *Passed* if no enemy pawns on the
  same or adjacent files between this pawn and promotion. *Pawn islands*
  is the count of contiguous file groups with friendly pawns. *IQP* = a
  central pawn (d/e file) with no friendly pawns on adjacent files.

- `king_safety`: the "ring" is `chess.SquareSet(chess.BB_KING_ATTACKS[king_sq])`.
  *Shield holes* on the kingside (white) = `[g2, h2, f2]` minus pawns. Define
  it precisely; don't ad-lib.

- `piece_activity.is_outpost`: square is defended by own pawn AND no enemy
  pawn on adjacent files at or beyond the outpost rank. Limit to ranks 4-6
  for white, 3-5 for black.

- `describe_position.ascii`: use `board.unicode(borders=True)` — much
  more readable than `str(board)`.

### `analysis/move_judge.py`

- All functions assume `tools._engine` is set. They should read it via
  `from gg_chess.analysis import tools as _tools; engine = _tools._engine`.
  (Or expose a getter.) Don't open new engines per call.

- `classify_move`: run multipv=3 once at `depth`, get `eval_before` from
  the top line, then `apply_move(fen, move)` → run engine again on the
  child position to get `eval_after` (negated, since side to move flips).

- `is_only_move`: top PV eval ≥ second PV eval + 150cp.

- `refute`: child position's best move IS the refutation. Add a 1-2 ply
  follow-up to make the punishment vivid. Run `tactics.find_tactics` on
  the child to attach a motif tag.

- `find_threats`: build the mirror FEN by toggling field 1 (active colour)
  and resetting castling/en-passant/halfmove if needed. python-chess won't
  accept arbitrary side-flips, so manipulate the FEN string directly.

### `analysis/tactics.py`

- Ship motif detection in waves: start with `fork`, `pin`, `skewer`,
  `discovered_check`, `back_rank_mate`. The rest can be `null` initially.

- `tag_motif` is a series of `if`-guards over the first 1-2 plies of the
  PV. Don't try to be clever — return on first match.

- Evidence dicts let the LLM narrate concretely: "the knight on f5 forks
  the king on g7 and the queen on d6" comes straight from the evidence.

### `retrieval/puzzles.py`

- The Lichess CSV is huge (~20M rows). Stream it; don't `pd.read_csv`.
  Use the stdlib `csv` module + `executemany` with batches.
- Add an FTS5 virtual table on `themes` if you want fast multi-theme
  search; otherwise `themes LIKE '%fork%'` works for the MVP.
- In Lichess puzzles the FEN is the position BEFORE the opponent's setup
  move. The first UCI in `Moves` is the opponent's move; the user solves
  starting from move index 1. Encode this carefully in `puzzle_search`.

### `retrieval/openings.py`

- Polyglot has no opening *names*. Maintain a small JSON `data/eco.json`
  mapping (truncated FEN → {eco, name}) for the ~500 most common openings;
  source from python-chess's `chess.svg` ECO data or the public ECO
  repository. Look up name by truncated FEN (drop halfmove + fullmove + ep).

### `retrieval/tablebase.py`

- 5-piece Syzygy is ~1GB and free; document the download URL in the
  README. 6-piece is ~150GB; skip unless the user opts in.
- python-chess: `tb = chess.syzygy.open_tablebase(path); tb.probe_wdl(board)`.
  Returns `None` if the position is too large for the loaded tables.

### `coach/sanitizer.py`

- Implementation: extract tokens from text, then for each token:
  1. Try `chess.Move.from_uci(t)` and `board.parse_san(t)`. If neither
     parses against `starting_fen` (or any FEN reachable in the transcript),
     it's an unsupported move shape.
  2. Walk `tool_transcript` and gather all SAN/UCI strings in the result
     payloads — see the docstring's source list.
  3. A token is OK if it appears (in either notation) in that set.
- Be lenient on punctuation: strip trailing `?!`, `!?`, `?`, `!` before
  comparing.
- The teach.py `_validate_demo_moves` flow is the integration template:
  on failure, append a tool_result with `is_error=True` and let the LLM retry.

### `coach/auditor.py`

- Use `CLAUDE_CONCEPT_MODEL` (the cheap Haiku model already in config) for
  the audit pass. Keep it under 1k tokens of context.
- Skip auditor on streaming responses (latency); run it only on the final
  text and re-emit a redacted version if needed.
- Strict mode is for `review` summaries; lenient mode is everything else.

### `coach/router.py`

The dispatch contract is: load student → call mode handler → run
sanitizer → return envelope. Pseudocode:

```python
def handle_turn(db, user_id, mode, payload):
    snapshot = student.load_snapshot(db, user_id)
    handler = _MODE_MAP[mode]                   # qa.handle, puzzle.handle, ...
    response = handler(payload, snapshot, db)
    if "data" in response and "text" in response["data"]:
        result = sanitizer.verify(
            response["data"]["text"],
            response.get("_tool_transcript", []),
            response.get("_starting_fen", ""),
        )
        if not result["ok"]:
            # Redact or re-prompt — mode-dependent
            response["data"]["text"] = _strip_unsupported(
                response["data"]["text"], result["violations"]
            )
            response["sanitizer"] = result
    student.flush(db, user_id, response.get("student_diff", {}))
    return response
```

The `_tool_transcript` and `_starting_fen` are bookkeeping fields the
mode handlers add for the sanitizer; strip them before returning.

### Coach system prompt template

Every mode's system prompt should start with this preamble (build it
programmatically in `coach/router.py`):

```
You are a chess coach.

GROUND-TRUTH RULE: You may not state any chess fact (move, evaluation,
piece relationship, weakness, plan) unless it came from a tool result this
turn. If unsure, call a tool. If you cannot verify, say you don't know.

VOCABULARY (use these exact thresholds when characterising evals):
  - "decisive"   ≥ +500cp
  - "winning"    ≥ +200cp
  - "small edge" ≥ +50cp
  - "equal"      |cp| < 50

  - "blunder"    cp_loss ≥ 200
  - "mistake"    cp_loss ≥ 100
  - "inaccuracy" cp_loss ≥ 50

MOVES: only mention moves that appear verbatim in a tool result this turn.
Copy SAN/UCI exactly; do not paraphrase.

POSITION (auto-injected each turn):
{describe_position(fen).ascii}

PLAYER: rating ≈ {rating_estimate}; weak themes: {weak_themes_csv}.
```

## External assets to download

| Asset | Source | Size | Required for |
|---|---|---|---|
| Lichess puzzle DB CSV | https://database.lichess.org/lichess_db_puzzle.csv.zst | ~300MB compressed | puzzle mode, weak-theme detection |
| Polyglot opening book | e.g. "Cerebellum" or "Perfect2023" | ~200MB | opening mode, opening_lookup tool |
| Syzygy 5-piece tablebase | https://syzygy-tables.info/ | ~1GB | endgame mode, tablebase_lookup |
| ECO name JSON | derive from any ECO repo | <1MB | opening_lookup names |

Document download/install steps in the README at impl time. The puzzle
indexer should be a CLI subcommand:

```
python -m gg_chess.retrieval.puzzles index ./data/lichess_db_puzzle.csv
```

## Testing strategy

- **Unit**: every tool has a `tests/test_<tool>.py` with 3-5 hand-crafted
  FENs and expected outputs. The tools are deterministic — these are
  golden-file tests.
- **Sanitizer**: feed it adversarial drafts ("Kg5 wins" when Kg5 isn't
  legal; "the queen on h7 is hanging" when there's no queen on h7) and
  assert the violations.
- **Mode integration**: per mode, one happy-path test that walks 3-4
  turns through the router with a mocked LLM that returns canned
  tool calls.
- **Engine fixtures**: most tests can run without Stockfish using a
  stub engine. Mark engine-dependent tests with `@pytest.mark.engine`
  and skip in CI without Stockfish installed.

## Migration plan (don't break what works)

The current `/api/ask` and `teach_position` are the demoed Q&A flow.
Don't remove them. Instead:

1. Land all new modules as stubs (this PR — done).
2. Implement structure + move_judge + sanitizer.
3. Implement `coach/modes/qa.py` as a parallel implementation; A/B test
   it behind a `?coach=v2` query param on `/api/ask`.
4. When v2 is at parity, switch the route over and delete `teach.py`.
5. New modes (puzzle, lesson, etc.) ship at their own `/api/coach/*` URL
   and don't touch `/api/ask`.

## Frontend (out of scope here, but flagged)

The router envelope is designed so each mode's `data` block can drive a
typed UI component. The frontend will need:

- A coach mode picker (top-level chooser).
- Per-mode panels: puzzle viewer, lesson reader, spar board, drill board.
- A shared "demo" renderer (already exists for `teach`'s board demos).

These can be built incrementally as backend modes ship. The existing
`CoachPanel` is the natural integration point.

## Open questions to resolve at impl time

- **Where to source ECO names**: ship a JSON, or call Lichess masters API?
  The JSON is more robust (offline-friendly) but stale.
- **Auditor cost vs. value**: measure on real review narrations before
  enabling by default. May only be worth it on summary text.
- **Spar mode skill targeting**: Stockfish `Skill Level 0-20` is coarse;
  `UCI_LimitStrength` + `UCI_Elo` is fine-grained but only available on
  Stockfish 16+. Detect at runtime.
- **Puzzle dedup**: should "seen" puzzles never reappear, or come back
  after N days? Default to 30-day cooldown; revisit with user data.
