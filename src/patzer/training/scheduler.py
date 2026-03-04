from dataclasses import dataclass


@dataclass
class SM2State:
    interval: int       # days until next review
    easiness: float     # EF (easiness factor), default 2.5, min 1.3
    repetitions: int    # consecutive correct reviews


def calculate_next_review(state: SM2State, quality: int) -> SM2State:
    """Apply SM-2 algorithm given a quality rating 0-5.

    quality: 0-2 = incorrect/difficult, 3-5 = correct (3=hard, 4=good, 5=easy)
    """
    if quality < 0 or quality > 5:
        raise ValueError(f"quality must be 0-5, got {quality}")

    if quality < 3:
        # Reset
        return SM2State(interval=1, easiness=state.easiness, repetitions=0)

    new_easiness = state.easiness + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_easiness = max(1.3, new_easiness)

    if state.repetitions == 0:
        new_interval = 1
    elif state.repetitions == 1:
        new_interval = 6
    else:
        new_interval = round(state.interval * new_easiness)

    return SM2State(
        interval=new_interval,
        easiness=new_easiness,
        repetitions=state.repetitions + 1,
    )
