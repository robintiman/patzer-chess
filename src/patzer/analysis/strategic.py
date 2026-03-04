import json

import anthropic

from ..config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from ..ingestion.parser import Game
from ..themes import STRATEGIC_THEMES, THEME_DESCRIPTIONS
from .engine import ErrorPosition


def detect_strategic_themes(error_pos: ErrorPosition, game: Game) -> list[str]:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    theme_desc_text = "\n".join(
        f"- {name}: {desc}"
        for name, desc in THEME_DESCRIPTIONS.items()
        if name in STRATEGIC_THEMES
    )

    prompt = f"""You are a chess coach analysing a position where a player made a strategic error.

Position (FEN): {error_pos.fen_before}
Player's move (UCI): {error_pos.player_move}
Best move (UCI): {error_pos.best_move}
Evaluation drop: {error_pos.eval_drop_cp} centipawns

Strategic themes to consider:
{theme_desc_text}

Which of the following strategic themes does the best move exemplify or exploit? Only include themes that clearly apply.

Respond with valid JSON only, in this exact format:
{{"themes": ["theme1", "theme2"], "explanation": "Brief explanation of the strategic idea."}}

Theme names must be exactly one of: {sorted(STRATEGIC_THEMES)}"""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=256,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            return []

    themes = data.get("themes", [])
    return [t for t in themes if t in STRATEGIC_THEMES]
