import math
import random
from dataclasses import dataclass

from bloom_filter import BloomFilter


@dataclass(slots=True)
class ExperimentPoint:
    k: int
    theoretical_epsilon: float
    empirical_epsilon: float


@dataclass(slots=True)
class EpsilonScenario:
    target_epsilon: float
    m: int
    k_optimal_real: float
    k_optimal_int: int
    theoretical_epsilon_at_k: float
    empirical_epsilon_at_k: float


def compute_filter_size(n: int, epsilon: float) -> int:
    if n <= 0:
        raise ValueError("n must be positive")
    if not 0 < epsilon < 1:
        raise ValueError("epsilon must be in the interval (0, 1)")
    return max(1, math.ceil(-(n * math.log(epsilon)) / (math.log(2) ** 2)))


def optimal_k_real(m: int, n: int) -> float:
    return (m / n) * math.log(2)


def optimal_k_int(m: int, n: int) -> int:
    return max(1, round(optimal_k_real(m, n)))


def theoretical_false_positive_rate(m: int, n: int, k: int) -> float:
    return (1 - math.exp(-(k * n) / m)) ** k


def generate_random_values(count: int, seed: int, prefix: str) -> list[str]:
    rng = random.Random(seed)
    values: list[str] = []
    seen: set[str] = set()

    while len(values) < count:
        value = f"{prefix}-{rng.getrandbits(64):016x}"
        if value not in seen:
            seen.add(value)
            values.append(value)

    return values


def run_single_experiment(
    n: int,
    m: int,
    k: int,
    inserted_values: list[str],
    test_values: list[str],
) -> ExperimentPoint:
    bloom = BloomFilter(m=m, k=k)
    for value in inserted_values:
        bloom.add(value)

    false_positives = sum(1 for value in test_values if bloom.probably_contains(value))
    empirical = false_positives / len(test_values)
    theoretical = theoretical_false_positive_rate(m=m, n=n, k=k)
    return ExperimentPoint(
        k=k,
        theoretical_epsilon=theoretical,
        empirical_epsilon=empirical,
    )


def sweep_k_values(
    n: int,
    m: int,
    inserted_values: list[str],
    test_values: list[str],
    max_k: int,
) -> list[ExperimentPoint]:
    return [
        run_single_experiment(
            n=n,
            m=m,
            k=k,
            inserted_values=inserted_values,
            test_values=test_values,
        )
        for k in range(1, max_k + 1)
    ]


def build_epsilon_scenarios(
    n: int,
    epsilons: list[float],
    inserted_values: list[str],
    test_values: list[str],
) -> list[EpsilonScenario]:
    scenarios: list[EpsilonScenario] = []

    for epsilon in epsilons:
        m = compute_filter_size(n=n, epsilon=epsilon)
        k_real = optimal_k_real(m=m, n=n)
        k_int = optimal_k_int(m=m, n=n)
        point = run_single_experiment(
            n=n,
            m=m,
            k=k_int,
            inserted_values=inserted_values,
            test_values=test_values,
        )
        scenarios.append(
            EpsilonScenario(
                target_epsilon=epsilon,
                m=m,
                k_optimal_real=k_real,
                k_optimal_int=k_int,
                theoretical_epsilon_at_k=point.theoretical_epsilon,
                empirical_epsilon_at_k=point.empirical_epsilon,
            )
        )

    return scenarios
