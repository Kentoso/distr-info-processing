import time
import random
from typing import Callable
from models import PhilosopherState, PhilosopherStats


class Philosopher:
    def __init__(self, id: int, acquire_forks: Callable[[int], None], release_forks: Callable[[int], None], meals: int = 5):
        self.id = id
        self.acquire_forks = acquire_forks
        self.release_forks = release_forks
        self.meals = meals
        self.state = PhilosopherState.THINKING
        self.stats = PhilosopherStats(philosopher_id=id)

    def _log(self, msg: str):
        print(f"[Philosopher {self.id}]: {msg}")

    def think(self):
        self.state = PhilosopherState.THINKING
        self._log("thinking")
        duration = random.uniform(0.1, 0.5)
        time.sleep(duration)
        self.stats.total_thinking_time += duration

    def eat(self):
        self.state = PhilosopherState.EATING
        self._log("eating")
        duration = random.uniform(0.1, 0.3)
        time.sleep(duration)
        self.stats.total_eating_time += duration
        self.stats.times_eaten += 1

    def run(self):
        for _ in range(self.meals):
            self.think()
            self.state = PhilosopherState.HUNGRY
            self._log("hungry, waiting for forks")
            self.acquire_forks(self.id)
            self.eat()
            self.release_forks(self.id)
            self._log("released forks")

        self._print_final_report()

    def _print_final_report(self):
        s = self.stats
        print(f"\n=== Final Report for Philosopher {self.id} ===")
        print(f"Times eaten: {s.times_eaten}")
        print(f"Total thinking time: {s.total_thinking_time:.3f}s")
        print(f"Total eating time: {s.total_eating_time:.3f}s")
        print("=" * 40)
