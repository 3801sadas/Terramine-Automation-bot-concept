"""Gold Rush round state machine (Phase 4)."""

from enum import Enum
import time


class RoundState(Enum):
    FRESH = "fresh"
    TAPPING = "tapping"
    WALKING = "walking"
    SUCCESS = "success"
    PLAY_AGAIN = "play_again"
    FAILED_OUT_OF_MOVES = "failed_out_of_moves"
    FAILED_TIME_UP = "failed_time_up"
    AD = "ad"
    DONE = "done"


def new_round() -> RoundState:
    return RoundState.FRESH
