import json
import time

import anthropic
import chess
import chess.engine
import ollama

from gg_chess.config import (
    ANTHROPIC_API_KEY,
    CLAUDE_CONCEPT_MODEL,
    LOCAL_MODEL_NAME,
    STOCKFISH_HASH,
    STOCKFISH_PATH,
    STOCKFISH_THREADS,
    USE_LOCAL_MODEL,
)
from gg_chess.analysis import tools as chess_tools
from gg_chess.analysis.structure import describe_position

_TERMINAL_TOOLS = {"respond_with_text", "create_board_demo"}

_SYSTEM = """\
You are an interactive chess coach. Given a chess position and a player's question, decide the best response:

RESPOND WITH TEXT when the question is conceptual ("what is a pin?"), asks for an explanation of a past move, or can be fully answered in words.

CREATE A BOARD DEMO when the question asks to SEE or SHOW something on the board — attacks, plans, tactics, improvements, "what should I do here?", "show me the idea", etc.

STRICT RULES for create_board_demo:
- You MUST call query_stockfish BEFORE create_board_demo. Never skip this step.
- Use ONLY moves that appear in Stockfish's pv_lines output. NEVER invent or guess moves.
- Copy UCI moves exactly from the pv_lines (e.g. "e2e4", "g1f3"). Do not paraphrase.
- Build 2-4 steps: "animate" steps (with narration) and EXACTLY ONE "question" step.
- The question step: ask the player to find the next move in the Stockfish line.
- Choices for the question step: correct move + 2 other legal SAN moves from the same position.
- Use participation_mode "choice" if rating < 1400, "freeplay" if rating >= 1400.
- Narrations: 1 sentence, specific and vivid.

If the FEN is empty or the position has no legal moves, call respond_with_text."""


def _validate_demo_moves(starting_fen: str, plan: dict) -> str | None:
    """Returns an error message string if any step contains an illegal move, else None."""
    try:
        board = chess.Board(starting_fen)
    except Exception:
        return "Invalid starting FEN."

    for i, step in enumerate(plan.get("steps", [])):
        uci = step.get("uci") or step.get("correct_uci")
        if not uci:
            continue
        try:
            move = chess.Move.from_uci(uci)
        except Exception:
            return f"Step {i} has invalid UCI notation '{uci}'. UCI must be like 'e2e4' or 'g1f3'."
        if move not in board.legal_moves:
            legal_sample = ", ".join(board.san(m) for m in list(board.legal_moves)[:8])
            return (
                f"Step {i}: move {uci} (SAN: {step.get('san') or step.get('correct_san', '?')}) "
                f"is ILLEGAL in this position. "
                f"Some legal moves are: {legal_sample}. "
                f"Use only moves from Stockfish's pv_lines."
            )
        board.push(move)
    return None


def teach_position(fen: str, question: str, player_color: str, rating: int) -> dict:
    """
    Returns {"action": "text", "text": "..."} or {"action": "demo", "plan": {...}}.
    """
    if not fen.strip():
        return {"action": "text", "text": "No position is loaded — navigate to a move first, then ask me."}

    try:
        board = chess.Board(fen)
    except Exception:
        return {"action": "text", "text": "I couldn't read this position. Try navigating to a different move."}

    if board.is_game_over():
        return {"action": "text", "text": "The game is already over in this position — there are no legal moves to demonstrate."}

    desc = describe_position(fen)
    system = (
        _SYSTEM
        + f"\n\nPlayer color: {player_color}. Player rating: {rating}."
        + f"\n\nCurrent position ({desc['to_move']} to move):\n{desc['ascii']}"
    )
    prompt = f"Position (FEN): {fen}\n\nPlayer's question: {question}"

    with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
        engine.configure({"Threads": STOCKFISH_THREADS, "Hash": STOCKFISH_HASH})
        chess_tools.set_engine(engine)
        try:
            if USE_LOCAL_MODEL:
                result = _loop_ollama(fen, system, prompt)
            else:
                result = _loop_anthropic(fen, system, prompt)
        finally:
            chess_tools.set_engine(None)

    if result is None:
        return {"action": "text", "text": "I wasn't sure how to respond to that. Could you rephrase?"}
    return result


def _loop_anthropic(starting_fen: str, system: str, prompt: str) -> dict | None:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    system_content = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
    messages = [{"role": "user", "content": prompt}]

    for iteration in range(20):
        while True:
            try:
                response = client.messages.create(
                    model=CLAUDE_CONCEPT_MODEL,
                    max_tokens=8192,
                    temperature=0,
                    system=system_content,
                    tools=chess_tools.ANTHROPIC_TEACH_TOOLS,
                    tool_choice={"type": "any"},
                    messages=messages,
                )
                break
            except anthropic.RateLimitError as e:
                retry_after = int(e.response.headers.get("retry-after", 60))
                print(f"[teach] rate limited, retrying in {retry_after}s")
                time.sleep(retry_after)

        print(f"[teach] iter={iteration} stop_reason={response.stop_reason}")

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            break

        terminal = next((b for b in tool_uses if b.name in _TERMINAL_TOOLS), None)
        if terminal:
            if terminal.name == "create_board_demo":
                error = _validate_demo_moves(starting_fen, terminal.input)
                if error:
                    print(f"[teach] demo validation failed: {error}")
                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({"role": "user", "content": [
                        {"type": "tool_result", "tool_use_id": terminal.id,
                         "content": f"VALIDATION ERROR: {error}", "is_error": True}
                    ]})
                    continue
            return _unpack_terminal(terminal.name, terminal.input)

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for tu in tool_uses:
            result = chess_tools.execute_tool(tu.name, tu.input)
            tool_results.append({"type": "tool_result", "tool_use_id": tu.id, "content": json.dumps(result)})
        messages.append({"role": "user", "content": tool_results})

    return None


def _loop_ollama(starting_fen: str, system: str, prompt: str) -> dict | None:
    messages: list = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]

    for iteration in range(20):
        stream = ollama.chat(
            model=LOCAL_MODEL_NAME,
            messages=messages,
            tools=chess_tools.OLLAMA_TEACH_TOOLS,
            stream=True,
            think=True,
        )

        thinking = ""
        content = ""
        tool_calls = []
        done_reason = None

        for chunk in stream:
            if chunk.message.thinking:
                thinking += chunk.message.thinking
                print(chunk.message.thinking, end="", flush=True)
            if chunk.message.content:
                content += chunk.message.content
            if chunk.message.tool_calls:
                tool_calls.extend(chunk.message.tool_calls)
            if chunk.done_reason:
                done_reason = chunk.done_reason

        print(f"[teach] iter={iteration} done_reason={done_reason}")

        if done_reason == "length":
            print("[teach] hit token limit mid-response, aborting")
            break

        if not tool_calls:
            break

        terminal = next((tc for tc in tool_calls if tc.function.name in _TERMINAL_TOOLS), None)
        if terminal:
            data = terminal.function.arguments
            if terminal.function.name == "create_board_demo":
                error = _validate_demo_moves(starting_fen, data)
                if error:
                    print(f"[teach] demo validation failed: {error}")
                    messages.append({"role": "assistant", "thinking": thinking, "content": content, "tool_calls": tool_calls})
                    messages.append({"role": "tool", "tool_name": terminal.function.name,
                                     "content": f"VALIDATION ERROR: {error}"})
                    continue
            return _unpack_terminal(terminal.function.name, data)

        messages.append({"role": "assistant", "thinking": thinking, "content": content, "tool_calls": tool_calls})
        for tc in tool_calls:
            result = chess_tools.execute_tool(tc.function.name, tc.function.arguments)
            messages.append({"role": "tool", "tool_name": tc.function.name, "content": json.dumps(result)})

    return None


def _unpack_terminal(name: str, data: dict) -> dict:
    if name == "respond_with_text":
        return {"action": "text", "text": data.get("text", "")}
    if name == "create_board_demo":
        return {"action": "demo", "plan": data}
    return {"action": "text", "text": ""}