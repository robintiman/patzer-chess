import re
import time

import httpx

USER_AGENT = "Patzer/0.1 (chess improvement tool; contact via github)"


def fetch_games(username: str, max_games: int = 50) -> list[str]:
    headers = {"User-Agent": USER_AGENT}
    pgn_games: list[str] = []

    with httpx.Client(timeout=30.0, headers=headers) as client:
        archives_resp = client.get(
            f"https://api.chess.com/pub/player/{username}/games/archives"
        )
        archives_resp.raise_for_status()
        archives: list[str] = archives_resp.json().get("archives", [])

        for archive_url in reversed(archives):
            if len(pgn_games) >= max_games:
                break

            while True:
                resp = client.get(archive_url + "/pgn")
                if resp.status_code == 429:
                    time.sleep(int(resp.headers.get("Retry-After", "10")))
                    continue
                resp.raise_for_status()
                break

            raw = resp.text
            chunks = re.split(r"\n\n(?=\[Event)", raw)
            for chunk in chunks:
                chunk = chunk.strip()
                if not chunk:
                    continue

                if _is_skippable(chunk):
                    continue

                pgn_games.append(chunk)
                if len(pgn_games) >= max_games:
                    break

    return pgn_games


def _is_skippable(pgn_text: str) -> bool:
    event_match = re.search(r'\[Event "([^"]+)"\]', pgn_text)
    time_control_match = re.search(r'\[TimeControl "([^"]+)"\]', pgn_text)

    if event_match:
        event = event_match.group(1).lower()
        if "correspondence" in event or "daily" in event:
            return True

    if time_control_match:
        tc = time_control_match.group(1)
        if tc in ("-", "1/86400", "1/172800"):
            return True

    rated_match = re.search(r'\[Rated "([^"]+)"\]', pgn_text)
    if rated_match and rated_match.group(1).lower() == "false":
        return True

    return False
