"""Chess analysis tools for LLM tool-use loops.

Ollama auto-generates schemas from function signatures and docstrings.
Anthropic schemas are defined manually as dicts in ANTHROPIC_TEACH_TOOLS / ANTHROPIC_TACTICS_TOOLS.
Call set_engine() before running any tool loop that needs Stockfish.
"""
from __future__ import annotations

import chess
import chess.engine

# New tool modules — see COACH_IMPLEMENTATION.md for the design.
from . import move_judge, structure, tactics
from ..retrieval import openings as openings_retrieval
from ..retrieval import puzzles as puzzles_retrieval
from ..retrieval import tablebase as tablebase_retrieval

_engine: chess.engine.SimpleEngine | None = None


def set_engine(engine: chess.engine.SimpleEngine | None) -> None:
    global _engine
    _engine = engine


# ── Analysis tools ─────────────────────────────────────────────────────────────

def query_stockfish(fen: str, depth: int = 14, multipv: int = 3) -> dict:
    """Evaluate a chess position with Stockfish. Returns eval in centipawns, best moves, and PV lines.

    Args:
        fen: FEN string of the position
        depth: Search depth (default 14, max 18)
        multipv: Lines to return (default 3, max 5)
    """
    depth = min(int(depth), 18)
    multipv = min(int(multipv), 5)
    try:
        board = chess.Board(fen)
    except Exception as e:
        return {"error": f"Invalid FEN: {e}"}

    results = _engine.analyse(board, chess.engine.Limit(depth=depth), multipv=multipv)
    if not isinstance(results, list):
        results = [results]

    pv_lines = []
    best_moves = []
    eval_cp = None

    for i, info in enumerate(results):
        score = info["score"].white().score(mate_score=10000)
        if i == 0:
            eval_cp = score
        pv_moves = []
        temp_board = board.copy()
        for mv in info.get("pv", [])[:8]:
            try:
                pv_moves.append(temp_board.san(mv))
                temp_board.push(mv)
            except Exception:
                break
        pv_lines.append(pv_moves)
        if pv_moves:
            best_moves.append(pv_moves[0])

    return {"eval_cp": eval_cp, "best_moves": best_moves, "pv_lines": pv_lines}


def apply_move(fen: str, move: str) -> dict:
    """Apply a move (UCI or SAN) and return the new FEN plus metadata (check, capture, checkmate).

    Args:
        fen: FEN string before the move
        move: Move in UCI (e.g. e2e4) or SAN (e.g. Nf3) notation
    """
    try:
        board = chess.Board(fen)
    except Exception as e:
        return {"error": f"Invalid FEN: {e}"}

    chess_move = None
    try:
        chess_move = chess.Move.from_uci(move)
        if chess_move not in board.legal_moves:
            chess_move = None
    except Exception:
        pass

    if chess_move is None:
        try:
            chess_move = board.parse_san(move)
        except Exception as e:
            return {"error": f"Cannot parse move '{move}': {e}"}

    is_capture = board.is_capture(chess_move)
    gives_check = board.gives_check(chess_move)
    san_before_push = board.san(chess_move)

    captured_piece = None
    if is_capture:
        cap_sq = chess_move.to_square
        if board.is_en_passant(chess_move):
            cap_sq = chess.square(
                chess.square_file(chess_move.to_square),
                chess.square_rank(chess_move.from_square),
            )
        cp = board.piece_at(cap_sq)
        if cp:
            captured_piece = {
                "piece": cp.symbol().upper(),
                "color": "white" if cp.color == chess.WHITE else "black",
                "square": chess.square_name(cap_sq),
            }

    board.push(chess_move)

    return {
        "fen_after": board.fen(),
        "move_san": san_before_push,
        "is_capture": is_capture,
        "captured_piece": captured_piece,
        "gives_check": gives_check,
        "is_checkmate": board.is_checkmate(),
        "is_stalemate": board.is_stalemate(),
    }


def get_hanging_pieces(fen: str) -> dict:
    """Find pieces that are attacked and undefended in the position.

    Args:
        fen: FEN string of the position
    """
    try:
        board = chess.Board(fen)
    except Exception as e:
        return {"error": str(e)}
    hanging = []
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece is None:
            continue
        attackers = board.attackers(not piece.color, sq)
        defenders = board.attackers(piece.color, sq)
        if attackers and not defenders:
            hanging.append({
                "piece": piece.symbol().upper(),
                "color": "white" if piece.color == chess.WHITE else "black",
                "square": chess.square_name(sq),
            })
    return {"hanging": hanging}


def get_pinned_pieces(fen: str, color: str) -> dict:
    """Find pieces of the given color that are pinned to their king.

    Args:
        fen: FEN string of the position
        color: 'white' or 'black'
    """
    try:
        board = chess.Board(fen)
    except Exception as e:
        return {"error": str(e)}
    pin_color = chess.WHITE if color.lower() == "white" else chess.BLACK
    king_sq = board.king(pin_color)
    if king_sq is None:
        return {"pinned": []}
    pinned = []
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece is None or piece.color != pin_color or sq == king_sq:
            continue
        if board.is_pinned(pin_color, sq):
            pin_mask = board.pin(pin_color, sq)
            pinner_sq = None
            pinner_piece = None
            for psq in chess.SQUARES:
                if psq == sq:
                    continue
                if chess.BB_SQUARES[psq] & pin_mask:
                    pp = board.piece_at(psq)
                    if pp and pp.color != pin_color:
                        pinner_sq = psq
                        pinner_piece = pp
                        break
            pinned.append({
                "piece": piece.symbol().upper(),
                "square": chess.square_name(sq),
                "pinned_by": pinner_piece.symbol().upper() if pinner_piece else None,
                "pinner_square": chess.square_name(pinner_sq) if pinner_sq is not None else None,
            })
    return {"pinned": pinned}


def get_square_info(fen: str, square: str) -> dict:
    """Get piece, attackers, and defenders for a square.

    Args:
        fen: FEN string of the position
        square: Square name e.g. e4
    """
    try:
        board = chess.Board(fen)
        sq = chess.parse_square(square)
    except Exception as e:
        return {"error": str(e)}
    piece = board.piece_at(sq)
    if piece is None:
        return {"piece": None, "color": None, "attackers": [], "defenders": [], "is_hanging": False}

    attackers = []
    for asq in board.attackers(not piece.color, sq):
        ap = board.piece_at(asq)
        if ap:
            attackers.append({"piece": ap.symbol().upper(), "color": "white" if ap.color == chess.WHITE else "black", "square": chess.square_name(asq)})
    defenders = []
    for dsq in board.attackers(piece.color, sq):
        dp = board.piece_at(dsq)
        if dp:
            defenders.append({"piece": dp.symbol().upper(), "color": "white" if dp.color == chess.WHITE else "black", "square": chess.square_name(dsq)})
    return {
        "piece": piece.symbol().upper(),
        "color": "white" if piece.color == chess.WHITE else "black",
        "attackers": attackers,
        "defenders": defenders,
        "is_hanging": bool(attackers) and not bool(defenders),
    }


def get_piece_attacks(fen: str, square: str) -> dict:
    """Get all squares a piece attacks and enemy pieces on those squares.

    Args:
        fen: FEN string of the position
        square: Square of the piece to query e.g. d5
    """
    try:
        board = chess.Board(fen)
        sq = chess.parse_square(square)
    except Exception as e:
        return {"error": str(e)}
    piece = board.piece_at(sq)
    if piece is None:
        return {"error": f"No piece on {square}"}
    attacked_squares = list(board.attacks(sq))
    attacked_enemy = []
    for asq in attacked_squares:
        target = board.piece_at(asq)
        if target and target.color != piece.color:
            attacked_enemy.append({"piece": target.symbol().upper(), "square": chess.square_name(asq)})
    return {
        "piece": piece.symbol().upper(),
        "color": "white" if piece.color == chess.WHITE else "black",
        "attacks": [chess.square_name(asq) for asq in attacked_squares],
        "attacked_enemy_pieces": attacked_enemy,
    }


# ── Terminal tools ─────────────────────────────────────────────────────────────

def respond_with_text(text: str) -> dict:
    """Reply to the player with a plain text explanation. Use when no board demonstration is needed — e.g. factual questions, concept explanations, or when the position has nothing instructive to show.

    Args:
        text: Complete response text, 1-4 sentences
    """
    return {"text": text}


def create_board_demo(theme: str, steps: list, summary: str) -> dict:
    """Take over the board and demonstrate a chess idea through animated moves and player participation. Use when the question asks to see, show, demonstrate, or explore something visually (attacks, plans, tactics, improvements, continuations).

    Args:
        theme: Short phrase naming the idea, e.g. 'Attacking the castled king on the h-file'
        steps: 2-5 steps alternating animate and question types. Each step is a dict with: type ('animate' or 'question'), uci (UCI move), san (SAN move), narration (animate steps only), prompt/participation_mode/choices/correct_uci/correct_san/hint (question steps only). participation_mode is 'choice' or 'freeplay'
        summary: 1-2 sentence takeaway lesson the player should remember
    """
    return {"theme": theme, "steps": steps, "summary": summary}


def report_tactic(reasoning: str, name: str, explanation: str, missing_info: str) -> dict:
    """Report the tactical pattern identified in the position.

    Args:
        reasoning: Step-by-step analysis of the position
        name: Name of the tactical pattern, or empty string if none
        explanation: 1-2 sentence coach explanation mentioning specific moves, or empty string if no tactic
        missing_info: If no tactic could be identified, describe what information is missing. Empty string if a tactic was found.
    """
    return {"reasoning": reasoning, "name": name, "explanation": explanation, "missing_info": missing_info}


# ── Tool dispatch ──────────────────────────────────────────────────────────────

_TOOL_MAP = {
    # Existing low-level position tools
    "query_stockfish": query_stockfish,
    "apply_move": apply_move,
    "get_hanging_pieces": get_hanging_pieces,
    "get_pinned_pieces": get_pinned_pieces,
    "get_square_info": get_square_info,
    "get_piece_attacks": get_piece_attacks,

    # Structure (engine-free)
    "pawn_structure":     structure.pawn_structure,
    "king_safety":        structure.king_safety,
    "piece_activity":     structure.piece_activity,
    "material_imbalance": structure.material_imbalance,
    "describe_position":  structure.describe_position,

    # Move judgment (engine-grounded)
    "classify_move":      move_judge.classify_move,
    "compare_candidates": move_judge.compare_candidates,
    "refute":             move_judge.refute,
    "find_threats":       move_judge.find_threats,
    "mate_search":        move_judge.mate_search,

    # Tactics
    "find_tactics":       tactics.find_tactics,

    # Retrieval
    "puzzle_search":      puzzles_retrieval.puzzle_search,
    "opening_lookup":     openings_retrieval.opening_lookup,
    "tablebase_lookup":   tablebase_retrieval.tablebase_lookup,

    # Terminal tools
    "respond_with_text": respond_with_text,
    "create_board_demo": create_board_demo,
    "report_tactic": report_tactic,
}


def execute_tool(name: str, args: dict) -> dict:
    """Dispatch a tool call by name."""
    fn = _TOOL_MAP.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    return fn(**args)


# ── Ollama tool lists (functions → auto-schema) ────────────────────────────────

# Base analysis tools available to every coach mode.
_OLLAMA_ANALYSIS_TOOLS = [
    query_stockfish, apply_move, get_hanging_pieces, get_pinned_pieces,
    get_square_info, get_piece_attacks,
    structure.pawn_structure, structure.king_safety, structure.piece_activity,
    structure.material_imbalance, structure.describe_position,
    move_judge.classify_move, move_judge.compare_candidates, move_judge.refute,
    move_judge.find_threats, move_judge.mate_search,
    tactics.find_tactics,
    puzzles_retrieval.puzzle_search,
    openings_retrieval.opening_lookup,
    tablebase_retrieval.tablebase_lookup,
]

OLLAMA_TEACH_TOOLS = _OLLAMA_ANALYSIS_TOOLS + [respond_with_text, create_board_demo]

OLLAMA_TACTICS_TOOLS = _OLLAMA_ANALYSIS_TOOLS + [report_tactic]

# ── Anthropic tool schemas (manually defined dicts) ────────────────────────────

_ANTHROPIC_ANALYSIS_TOOLS = [
    {
        "name": "query_stockfish",
        "description": "Evaluate a chess position with Stockfish. Returns eval in centipawns (from White's perspective), best moves, and principal variation lines.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fen": {"type": "string", "description": "FEN string of the position to evaluate"},
                "depth": {"type": "integer", "description": "Search depth (default 14, max 18)"},
                "multipv": {"type": "integer", "description": "Number of best lines to return (default 3, max 5)"},
            },
            "required": ["fen"],
        },
    },
    {
        "name": "apply_move",
        "description": "Apply a single move to a position and return the resulting FEN. Accepts UCI (e.g. 'e2e4') or SAN (e.g. 'Nf3', 'O-O'). Returns new FEN, whether the move gives check, is a capture, or is checkmate.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fen": {"type": "string", "description": "FEN string before the move"},
                "move": {"type": "string", "description": "Move in UCI or SAN notation"},
            },
            "required": ["fen", "move"],
        },
    },
    {
        "name": "get_hanging_pieces",
        "description": "Find all pieces that are attacked and undefended (hanging/en-prise) in the position.",
        "input_schema": {
            "type": "object",
            "properties": {"fen": {"type": "string", "description": "FEN string of the position"}},
            "required": ["fen"],
        },
    },
    {
        "name": "get_pinned_pieces",
        "description": "Find all pieces of the given color that are pinned to their king.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fen": {"type": "string", "description": "FEN string of the position"},
                "color": {"type": "string", "description": "'white' or 'black'"},
            },
            "required": ["fen", "color"],
        },
    },
    {
        "name": "get_square_info",
        "description": "Get information about a square: what piece is on it, who attacks it, and who defends it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fen": {"type": "string", "description": "FEN string of the position"},
                "square": {"type": "string", "description": "Square name (e.g. 'e4')"},
            },
            "required": ["fen", "square"],
        },
    },
    {
        "name": "get_piece_attacks",
        "description": "Get all squares a piece attacks and any enemy pieces on those squares.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fen": {"type": "string", "description": "FEN string of the position"},
                "square": {"type": "string", "description": "Square of the piece to query (e.g. 'd5')"},
            },
            "required": ["fen", "square"],
        },
    },
    # ── Structure ─────────────────────────────────────────────────────────
    {
        "name": "pawn_structure",
        "description": "Classify pawn structure features for both colours: isolated, doubled, backward, passed pawns, pawn chains, islands, and IQP detection.",
        "input_schema": {
            "type": "object",
            "properties": {"fen": {"type": "string"}},
            "required": ["fen"],
        },
    },
    {
        "name": "king_safety",
        "description": "Quantify king safety for one colour: shield holes, open files near king, attackers/defenders, and weak ring squares.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fen":   {"type": "string"},
                "color": {"type": "string", "description": "'white' or 'black'"},
            },
            "required": ["fen", "color"],
        },
    },
    {
        "name": "piece_activity",
        "description": "Per-piece mobility, outposts, open/half-open files for rooks, bad-bishop flag.",
        "input_schema": {
            "type": "object",
            "properties": {"fen": {"type": "string"}},
            "required": ["fen"],
        },
    },
    {
        "name": "material_imbalance",
        "description": "Material count, centipawn diff, bishop pair, and named imbalance tags (e.g. minor_for_rook).",
        "input_schema": {
            "type": "object",
            "properties": {"fen": {"type": "string"}},
            "required": ["fen"],
        },
    },
    {
        "name": "describe_position",
        "description": "Render the position as a flat text block (occupied squares, side to move, castling, legal moves). Use to ground reasoning when FEN is hard to parse.",
        "input_schema": {
            "type": "object",
            "properties": {"fen": {"type": "string"}},
            "required": ["fen"],
        },
    },
    # ── Move judgment ─────────────────────────────────────────────────────
    {
        "name": "classify_move",
        "description": "Grade a single move: cp_loss, classification (best/excellent/good/inaccuracy/mistake/blunder), engine's preferred move and PV, and is_only_move flag.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fen":   {"type": "string"},
                "move":  {"type": "string", "description": "UCI or SAN"},
                "depth": {"type": "integer", "description": "default 14, max 18"},
            },
            "required": ["fen", "move"],
        },
    },
    {
        "name": "compare_candidates",
        "description": "Rank multiple candidate moves by Stockfish; returns each with cp_loss, classification, and rank.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fen":   {"type": "string"},
                "moves": {"type": "array", "items": {"type": "string"}, "description": "UCI or SAN moves"},
                "depth": {"type": "integer"},
            },
            "required": ["fen", "moves"],
        },
    },
    {
        "name": "refute",
        "description": "Find the engine's punishing reply to a (presumably bad) move. Returns the refutation move + PV + tactical motif tag if any.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fen":   {"type": "string"},
                "move":  {"type": "string"},
                "depth": {"type": "integer"},
            },
            "required": ["fen", "move"],
        },
    },
    {
        "name": "find_threats",
        "description": "What would the opponent play if it were their move? Surfaces tactical threats the side-to-move is currently ignoring.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fen":   {"type": "string"},
                "depth": {"type": "integer"},
            },
            "required": ["fen"],
        },
    },
    {
        "name": "mate_search",
        "description": "Search for a forced mate up to max_n moves. Returns mate_in (in moves) and the principal variation if found.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fen":   {"type": "string"},
                "max_n": {"type": "integer", "description": "max mate length in full moves (default 5)"},
            },
            "required": ["fen"],
        },
    },
    # ── Tactics ───────────────────────────────────────────────────────────
    {
        "name": "find_tactics",
        "description": "Detect a sharp tactical line in the position via eval-swing + motif tagging (fork, pin, skewer, discovered attack, etc).",
        "input_schema": {
            "type": "object",
            "properties": {
                "fen":   {"type": "string"},
                "depth": {"type": "integer"},
                "eval_swing_threshold_cp": {"type": "integer", "description": "default 150"},
            },
            "required": ["fen"],
        },
    },
    # ── Retrieval ─────────────────────────────────────────────────────────
    {
        "name": "puzzle_search",
        "description": "Sample puzzles from the Lichess puzzle DB by theme + rating window.",
        "input_schema": {
            "type": "object",
            "properties": {
                "themes":        {"type": "array", "items": {"type": "string"}},
                "rating_min":    {"type": "integer"},
                "rating_max":    {"type": "integer"},
                "color_to_move": {"type": "string", "description": "'white' | 'black' (filters who is solving)"},
                "count":         {"type": "integer", "description": "default 1"},
            },
        },
    },
    {
        "name": "opening_lookup",
        "description": "Identify the opening at this FEN: ECO code, name, and common book continuations with weights.",
        "input_schema": {
            "type": "object",
            "properties": {"fen": {"type": "string"}},
            "required": ["fen"],
        },
    },
    {
        "name": "tablebase_lookup",
        "description": "Exact endgame result + DTZ for ≤7-piece positions via Syzygy. Returns {available:false} if no tablebase or too many pieces.",
        "input_schema": {
            "type": "object",
            "properties": {"fen": {"type": "string"}},
            "required": ["fen"],
        },
    },
]

ANTHROPIC_TEACH_TOOLS = _ANTHROPIC_ANALYSIS_TOOLS + [
    {
        "name": "respond_with_text",
        "description": "Reply to the player's question with a plain text explanation. Use when no board demonstration is needed — e.g. factual questions, concept explanations, or when the position has nothing instructive to show.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Complete response text, 1-4 sentences."},
            },
            "required": ["text"],
        },
    },
    {
        "name": "create_board_demo",
        "description": "Take over the board and demonstrate a chess idea through animated moves and a player participation step. Use when the question asks to see, show, demonstrate, or explore something visually.",
        "input_schema": {
            "type": "object",
            "properties": {
                "theme": {
                    "type": "string",
                    "description": "Short phrase naming the idea being demonstrated, e.g. 'Attacking the castled king on the h-file'",
                },
                "steps": {
                    "type": "array",
                    "description": "2-5 steps alternating animate and question types. Include exactly ONE question step.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["animate", "question"]},
                            "uci": {"type": "string", "description": "Move in UCI notation"},
                            "san": {"type": "string", "description": "Move in SAN notation"},
                            "narration": {"type": "string", "description": "One punchy sentence explaining why this move (animate steps only)"},
                            "prompt": {"type": "string", "description": "Question to the player (question steps only)"},
                            "participation_mode": {"type": "string", "enum": ["choice", "freeplay"]},
                            "choices": {"type": "array", "items": {"type": "string"}, "description": "3 SAN moves: correct one plus 2 plausible alternatives (choice mode only)"},
                            "correct_uci": {"type": "string", "description": "The correct move in UCI (question steps only)"},
                            "correct_san": {"type": "string", "description": "The correct move in SAN (question steps only)"},
                            "hint": {"type": "string", "description": "One-sentence hint if the player is wrong (question steps only)"},
                        },
                        "required": ["type"],
                    },
                },
                "summary": {"type": "string", "description": "1-2 sentence takeaway lesson the player should remember."},
            },
            "required": ["theme", "steps", "summary"],
        },
    },
]

ANTHROPIC_TACTICS_TOOLS = _ANTHROPIC_ANALYSIS_TOOLS + [
    {
        "name": "report_tactic",
        "description": "Report the tactical pattern identified in the position.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reasoning": {"type": "string", "description": "Step-by-step analysis of the position"},
                "name": {"type": "string", "description": "Name of the tactical pattern, or empty string if none"},
                "explanation": {"type": "string", "description": "1-2 sentence coach explanation mentioning specific moves, or empty string if no tactic"},
                "missing_info": {"type": "string", "description": "If no tactic could be identified, describe what information is missing. Empty string if a tactic was found."},
            },
            "required": ["reasoning", "name", "explanation", "missing_info"],
        },
    },
]
