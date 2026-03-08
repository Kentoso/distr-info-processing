import multiprocessing as mp
from philosopher import Philosopher

N = 5
MEALS = 5


class CountingSemaphoreStrategy:
    def __init__(self, room, forks, n):
        self.room = room
        self.forks = forks
        self.n = n

    def acquire(self, pid):
        self.room.acquire()
        self.forks[pid].acquire()
        self.forks[(pid + 1) % self.n].acquire()

    def release(self, pid):
        self.forks[pid].release()
        self.forks[(pid + 1) % self.n].release()
        self.room.release()


class MutexForkStrategy:
    def __init__(self, mutex, forks, n):
        self.mutex = mutex
        self.forks = forks
        self.n = n

    def acquire(self, pid):
        with self.mutex:
            self.forks[pid].acquire()
            self.forks[(pid + 1) % self.n].acquire()

    def release(self, pid):
        self.forks[pid].release()
        self.forks[(pid + 1) % self.n].release()


def _run_philosopher(philosopher_id, strategy, meals):
    node = Philosopher(philosopher_id, strategy.acquire, strategy.release, meals)
    node.run()


def run_with_counting_semaphore():
    """Solution 1: Counting semaphore (N-1) as admission control."""
    room = mp.Semaphore(N - 1)
    forks = [mp.Lock() for _ in range(N)]
    strategy = CountingSemaphoreStrategy(room, forks, N)

    procs = [
        mp.Process(target=_run_philosopher, args=(i, strategy, MEALS)) for i in range(N)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join()


def run_with_mutex_and_fork_semaphores():
    """Solution 2: Mutex for atomic fork pickup + 5 binary fork semaphores."""
    mutex = mp.Lock()
    forks = [mp.Semaphore(1) for _ in range(N)]
    strategy = MutexForkStrategy(mutex, forks, N)

    procs = [
        mp.Process(target=_run_philosopher, args=(i, strategy, MEALS)) for i in range(N)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join()


if __name__ == "__main__":
    print("=== Solution 1: Counting Semaphore ===")
    run_with_counting_semaphore()
    print("\n=== Solution 2: Mutex + Fork Semaphores ===")
    run_with_mutex_and_fork_semaphores()
