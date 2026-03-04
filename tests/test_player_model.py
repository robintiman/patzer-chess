import sqlite3
import pytest

from patzer.db import init_db
from patzer.player_model import (
    ThemePerformance,
    get_all_theme_performance,
    get_weakest_themes,
    upsert_theme_error,
    upsert_theme_result,
)


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test.db"
    conn = init_db(db_path)
    yield conn
    conn.close()


class TestUpsertThemeError:
    def test_creates_entry_on_first_error(self, db):
        upsert_theme_error(db, "alice", "fork")
        perf = get_all_theme_performance(db, "alice")
        assert len(perf) == 1
        assert perf[0].theme_name == "fork"
        assert perf[0].game_errors == 1

    def test_increments_on_repeated_error(self, db):
        upsert_theme_error(db, "alice", "fork")
        upsert_theme_error(db, "alice", "fork")
        upsert_theme_error(db, "alice", "fork")
        perf = get_all_theme_performance(db, "alice")
        assert perf[0].game_errors == 3

    def test_different_themes_tracked_separately(self, db):
        upsert_theme_error(db, "alice", "fork")
        upsert_theme_error(db, "alice", "pin")
        perf = get_all_theme_performance(db, "alice")
        theme_names = {p.theme_name for p in perf}
        assert "fork" in theme_names
        assert "pin" in theme_names

    def test_different_players_tracked_separately(self, db):
        upsert_theme_error(db, "alice", "fork")
        upsert_theme_error(db, "bob", "fork")
        alice_perf = get_all_theme_performance(db, "alice")
        bob_perf = get_all_theme_performance(db, "bob")
        assert alice_perf[0].game_errors == 1
        assert bob_perf[0].game_errors == 1


class TestUpsertThemeResult:
    def test_correct_answer_recorded(self, db):
        upsert_theme_result(db, "alice", "fork", correct=True, quality=4)
        perf = get_all_theme_performance(db, "alice")
        assert len(perf) == 1
        assert perf[0].attempts == 1
        assert perf[0].correct == 1
        assert perf[0].accuracy == 1.0

    def test_incorrect_answer_recorded(self, db):
        upsert_theme_result(db, "alice", "fork", correct=False, quality=1)
        perf = get_all_theme_performance(db, "alice")
        assert perf[0].attempts == 1
        assert perf[0].correct == 0
        assert perf[0].accuracy == 0.0

    def test_accuracy_calculation(self, db):
        upsert_theme_result(db, "alice", "fork", correct=True, quality=4)
        upsert_theme_result(db, "alice", "fork", correct=True, quality=5)
        upsert_theme_result(db, "alice", "fork", correct=False, quality=1)
        perf = get_all_theme_performance(db, "alice")
        assert abs(perf[0].accuracy - 2/3) < 0.01

    def test_sm2_state_updated(self, db):
        upsert_theme_result(db, "alice", "fork", correct=True, quality=4)
        perf = get_all_theme_performance(db, "alice")
        # After first correct review, interval should be 1 (first repetition)
        assert perf[0].sr_interval == 1
        assert perf[0].sr_repetitions == 1

    def test_sm2_interval_grows_with_repetitions(self, db):
        upsert_theme_result(db, "alice", "fork", correct=True, quality=4)
        upsert_theme_result(db, "alice", "fork", correct=True, quality=4)
        perf = get_all_theme_performance(db, "alice")
        # After 2nd correct review, interval should be 6
        assert perf[0].sr_interval == 6
        assert perf[0].sr_repetitions == 2

    def test_due_date_set(self, db):
        upsert_theme_result(db, "alice", "fork", correct=True, quality=4)
        perf = get_all_theme_performance(db, "alice")
        assert perf[0].sr_due_date is not None


class TestGetWeakestThemes:
    def test_returns_n_worst_themes(self, db):
        # Create themes with different accuracy
        upsert_theme_result(db, "alice", "fork", correct=False, quality=1)
        upsert_theme_result(db, "alice", "pin", correct=True, quality=4)
        upsert_theme_result(db, "alice", "skewer", correct=True, quality=5)

        weakest = get_weakest_themes(db, "alice", n=2)
        assert len(weakest) == 2
        assert weakest[0].theme_name == "fork"

    def test_empty_when_no_data(self, db):
        weakest = get_weakest_themes(db, "nobody", n=5)
        assert weakest == []

    def test_game_errors_influence_ranking(self, db):
        upsert_theme_error(db, "alice", "fork")
        upsert_theme_error(db, "alice", "fork")
        upsert_theme_error(db, "alice", "pin")

        weakest = get_weakest_themes(db, "alice", n=1)
        # fork has 2 errors vs pin's 1 — both have 0 accuracy, fork should rank first
        assert weakest[0].theme_name == "fork"
