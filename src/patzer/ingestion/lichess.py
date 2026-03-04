import time

import httpx


def fetch_games(username: str, max_games: int = 50) -> list[str]:
    url = f"https://lichess.org/api/games/user/{username}"
    params = {
        "max": max_games,
        "pgnInJson": "false",
        "clocks": "false",
        "evals": "false",
        "opening": "false",
        "perfType": "bullet,blitz,rapid,classical",
    }
    headers = {"Accept": "application/x-ndjson"}

    pgn_games: list[str] = []

    with httpx.Client(timeout=60.0) as client:
        while True:
            response = client.get(url, params=params, headers=headers)

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "60"))
                time.sleep(retry_after)
                continue

            response.raise_for_status()
            break

    # Parse ndjson — each line is a game JSON, but we want PGN text
    # Re-request as PGN
    pgn_params = dict(params)
    pgn_params.pop("pgnInJson", None)

    with httpx.Client(timeout=60.0) as client:
        while True:
            response = client.get(
                url,
                params={**pgn_params, "max": max_games},
                headers={"Accept": "application/x-chess-pgn"},
            )

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "60"))
                time.sleep(retry_after)
                continue

            response.raise_for_status()
            break

    raw = response.text
    # Split individual PGN games — separated by double blank lines before [Event
    current: list[str] = []
    games_raw: list[str] = []

    for line in raw.splitlines(keepends=True):
        current.append(line)
        if line.strip() == "" and current:
            # Check if next game starts: we'll collect and split by Event tag
            pass

    # Simpler split: split on double newline before [Event
    import re
    chunks = re.split(r"\n\n(?=\[Event)", raw)
    for chunk in chunks:
        chunk = chunk.strip()
        if chunk:
            pgn_games.append(chunk)

    return pgn_games[:max_games]
