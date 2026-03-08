from dataclasses import dataclass
from enum import StrEnum


class PhilosopherState(StrEnum):
    THINKING = "thinking"
    HUNGRY = "hungry"
    EATING = "eating"


@dataclass
class PhilosopherStats:
    philosopher_id: int
    times_eaten: int = 0
    total_thinking_time: float = 0.0
    total_eating_time: float = 0.0
