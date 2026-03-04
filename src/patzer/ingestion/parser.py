import io
from dataclasses import dataclass

import chess.pgn


@dataclass
class Game:
    game_id: str
    source: str           # "lichess" | "chesscom"
    username: str
    player_color: str     # "white" | "black"
    result: str           # "win" | "loss" | "draw"
    time_control: str
    pgn_text: str
    headers: dict[str, str]


def parse_pgn(pgn_text: str, username: str, source: str) -> Game | None:
    if "[" not in pgn_text:
        return None

    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        return None

    headers = dict(game.headers)

    white = headers.get("White", "").lower()
    black = headers.get("Black", "").lower()
    user_lower = username.lower()

    if white == user_lower:
        player_color = "white"
    elif black == user_lower:
        player_color = "black"
    else:
        player_color = "white"

    raw_result = headers.get("Result", "*")
    if raw_result == "1-0":
        result = "win" if player_color == "white" else "loss"
    elif raw_result == "0-1":
        result = "win" if player_color == "black" else "loss"
    elif raw_result == "1/2-1/2":
        result = "draw"
    else:
        result = "draw"

    if source == "lichess":
        game_id = headers.get("Site", "").rstrip("/").split("/")[-1]
    else:
        game_id = headers.get("Link", headers.get("Site", "")).rstrip("/").split("/")[-1]

    time_control = headers.get("TimeControl", "")

    return Game(
        game_id=game_id,
        source=source,
        username=username,
        player_color=player_color,
        result=result,
        time_control=time_control,
        pgn_text=pgn_text,
        headers=headers,
    )
