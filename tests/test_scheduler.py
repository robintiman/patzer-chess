import pytest

from patzer.training.scheduler import SM2State, calculate_next_review


def make_state(interval=1, easiness=2.5, repetitions=0):
    return SM2State(interval=interval, easiness=easiness, repetitions=repetitions)


class TestSM2Reset:
    def test_quality_0_resets(self):
        state = make_state(interval=10, repetitions=5)
        new = calculate_next_review(state, quality=0)
        assert new.interval == 1
        assert new.repetitions == 0

    def test_quality_1_resets(self):
        state = make_state(interval=10, repetitions=5)
        new = calculate_next_review(state, quality=1)
        assert new.interval == 1
        assert new.repetitions == 0

    def test_quality_2_resets(self):
        state = make_state(interval=10, repetitions=5)
        new = calculate_next_review(state, quality=2)
        assert new.interval == 1
        assert new.repetitions == 0


class TestSM2FirstCorrect:
    def test_first_repetition_interval_1(self):
        state = make_state(interval=1, repetitions=0)
        new = calculate_next_review(state, quality=4)
        assert new.interval == 1
        assert new.repetitions == 1

    def test_second_repetition_interval_6(self):
        state = make_state(interval=1, repetitions=1)
        new = calculate_next_review(state, quality=4)
        assert new.interval == 6
        assert new.repetitions == 2


class TestSM2EasinessFactor:
    def test_perfect_score_increases_ef(self):
        state = make_state(easiness=2.5, repetitions=1)
        new = calculate_next_review(state, quality=5)
        assert new.easiness > 2.5

    def test_hard_correct_decreases_ef(self):
        state = make_state(easiness=2.5, repetitions=1)
        new = calculate_next_review(state, quality=3)
        assert new.easiness < 2.5

    def test_ef_never_below_1_3(self):
        state = make_state(easiness=1.31, repetitions=2, interval=6)
        new = calculate_next_review(state, quality=3)
        assert new.easiness >= 1.3

    def test_ef_floor_at_1_3(self):
        state = make_state(easiness=1.3, repetitions=3, interval=6)
        new = calculate_next_review(state, quality=3)
        assert new.easiness == pytest.approx(1.3, abs=0.01)


class TestSM2GrowthAfterReps:
    def test_interval_grows_by_ef(self):
        state = make_state(interval=6, easiness=2.5, repetitions=2)
        new = calculate_next_review(state, quality=4)
        assert new.interval == round(6 * 2.5)

    def test_repetitions_incremented(self):
        state = make_state(repetitions=3)
        new = calculate_next_review(state, quality=4)
        assert new.repetitions == 4


class TestSM2InvalidQuality:
    def test_quality_below_0_raises(self):
        with pytest.raises(ValueError):
            calculate_next_review(make_state(), quality=-1)

    def test_quality_above_5_raises(self):
        with pytest.raises(ValueError):
            calculate_next_review(make_state(), quality=6)
