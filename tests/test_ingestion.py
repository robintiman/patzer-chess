import pytest

from patzer.ingestion.parser import Game, parse_pgn

SAMPLE_PGN_LICHESS = """[Event "Rated Blitz game"]
[Site "https://lichess.org/abc123"]
[Date "2024.01.15"]
[White "testuser"]
[Black "opponent"]
[Result "1-0"]
[WhiteElo "1500"]
[BlackElo "1480"]
[TimeControl "300+3"]
[UTCDate "2024.01.15"]
[UTCTime "12:00:00"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 1-0"""

SAMPLE_PGN_LICHESS_BLACK = """[Event "Rated Blitz game"]
[Site "https://lichess.org/def456"]
[Date "2024.01.16"]
[White "opponent"]
[Black "testuser"]
[Result "0-1"]
[WhiteElo "1520"]
[BlackElo "1505"]
[TimeControl "300+3"]

1. d4 d5 2. c4 e6 3. Nc3 0-1"""

SAMPLE_PGN_DRAW = """[Event "Rated Rapid game"]
[Site "https://lichess.org/ghi789"]
[Date "2024.01.17"]
[White "testuser"]
[Black "opponent"]
[Result "1/2-1/2"]
[TimeControl "600+0"]

1. e4 e5 1/2-1/2"""


class TestParsePGN:
    def test_basic_parse_white_win(self):
        game = parse_pgn(SAMPLE_PGN_LICHESS, "testuser", "lichess")
        assert game is not None
        assert game.username == "testuser"
        assert game.source == "lichess"
        assert game.player_color == "white"
        assert game.result == "win"

    def test_game_id_extracted_from_site(self):
        game = parse_pgn(SAMPLE_PGN_LICHESS, "testuser", "lichess")
        assert game is not None
        assert game.game_id == "abc123"

    def test_black_player_loss_when_white_wins(self):
        game = parse_pgn(SAMPLE_PGN_LICHESS, "opponent", "lichess")
        assert game is not None
        assert game.player_color == "black"
        assert game.result == "loss"

    def test_black_player_win(self):
        game = parse_pgn(SAMPLE_PGN_LICHESS_BLACK, "testuser", "lichess")
        assert game is not None
        assert game.player_color == "black"
        assert game.result == "win"

    def test_draw_result(self):
        game = parse_pgn(SAMPLE_PGN_DRAW, "testuser", "lichess")
        assert game is not None
        assert game.result == "draw"

    def test_time_control_extracted(self):
        game = parse_pgn(SAMPLE_PGN_LICHESS, "testuser", "lichess")
        assert game is not None
        assert game.time_control == "300+3"

    def test_headers_present(self):
        game = parse_pgn(SAMPLE_PGN_LICHESS, "testuser", "lichess")
        assert game is not None
        assert "WhiteElo" in game.headers
        assert game.headers["WhiteElo"] == "1500"

    def test_pgn_text_preserved(self):
        game = parse_pgn(SAMPLE_PGN_LICHESS, "testuser", "lichess")
        assert game is not None
        assert "[Event" in game.pgn_text

    def test_invalid_pgn_returns_none(self):
        game = parse_pgn("this is not a pgn", "testuser", "lichess")
        assert game is None

    def test_case_insensitive_username_match(self):
        game = parse_pgn(SAMPLE_PGN_LICHESS, "TESTUSER", "lichess")
        assert game is not None
        assert game.player_color == "white"
