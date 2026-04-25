import argparse
import os

from experiments import (
    build_epsilon_scenarios,
    compute_filter_size,
    generate_random_values,
    optimal_k_int,
    optimal_k_real,
    sweep_k_values,
)
from plots import (
    ensure_output_dir,
    plot_false_positive_vs_k,
)


DEFAULT_N = 5_000
DEFAULT_TARGET_EPSILON = 0.01
DEFAULT_QUERY_COUNT = 20_000
DEFAULT_SEED = 42


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lab 8: Bloom filter")
    parser.add_argument(
        "--n", type=int, default=DEFAULT_N, help="Number of inserted elements"
    )
    parser.add_argument(
        "--epsilon",
        type=float,
        default=DEFAULT_TARGET_EPSILON,
        help="Target false-positive rate used to compute m",
    )
    parser.add_argument(
        "--queries",
        type=int,
        default=DEFAULT_QUERY_COUNT,
        help="Number of negative queries for empirical measurement",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Random seed")
    parser.add_argument(
        "--max-k",
        type=int,
        default=None,
        help="Maximum k to sweep; default is based on the theoretical optimum",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join(os.path.dirname(__file__), "data"),
        help="Directory for generated plots",
    )
    return parser.parse_args()


def print_primary_summary(
    n: int, epsilon: float, m: int, k_real: float, k_int: int
) -> None:
    print("=== Lab 8: Bloom Filter ===")
    print(f"Inserted elements n: {n}")
    print(f"Target epsilon: {epsilon:.6f}")
    print(f"Computed filter size m: {m} bits")
    print(f"Theoretical optimal k: {k_real:.4f}")
    print(f"Rounded optimal k: {k_int}")


def print_k_table(points: list) -> None:
    print("\n=== Sweep over k ===")
    print(f"{'k':>3} | {'theoretical epsilon':>20} | {'empirical epsilon':>18}")
    print("-" * 50)
    for point in points:
        print(
            f"{point.k:>3} | {point.theoretical_epsilon:>20.6f} | {point.empirical_epsilon:>18.6f}"
        )


def print_epsilon_scenarios(scenarios: list) -> None:
    print("\n=== Fixed n: varying m and epsilon scenarios ===")
    print(
        f"{'target epsilon':>14} | {'m bits':>8} | {'k real':>8} | {'k int':>5} | {'theor. eps':>10} | {'emp. eps':>9}"
    )
    print("-" * 72)
    for scenario in scenarios:
        print(
            f"{scenario.target_epsilon:>14.6f} | "
            f"{scenario.m:>8} | "
            f"{scenario.k_optimal_real:>8.4f} | "
            f"{scenario.k_optimal_int:>5} | "
            f"{scenario.theoretical_epsilon_at_k:>10.6f} | "
            f"{scenario.empirical_epsilon_at_k:>9.6f}"
        )


def main() -> None:
    args = parse_args()
    ensure_output_dir(args.output_dir)

    m = compute_filter_size(n=args.n, epsilon=args.epsilon)
    k_real = optimal_k_real(m=m, n=args.n)
    k_int = optimal_k_int(m=m, n=args.n)
    max_k = args.max_k if args.max_k is not None else max(10, k_int * 3)

    inserted_values = generate_random_values(args.n, seed=args.seed, prefix="inserted")
    test_values = generate_random_values(
        args.queries, seed=args.seed + 1, prefix="query"
    )

    points = sweep_k_values(
        n=args.n,
        m=m,
        inserted_values=inserted_values,
        test_values=test_values,
        max_k=max_k,
    )

    epsilon_scenarios = build_epsilon_scenarios(
        n=args.n,
        epsilons=[0.1, 0.05, 0.02, 0.01, 0.005, 0.001],
        inserted_values=inserted_values,
        test_values=test_values,
    )

    best_theoretical = min(points, key=lambda point: point.theoretical_epsilon)
    best_empirical = min(points, key=lambda point: point.empirical_epsilon)

    false_positive_plot = os.path.join(args.output_dir, "false_positive_vs_k.png")
    plot_false_positive_vs_k(
        points,
        false_positive_plot,
        highlighted_k=best_theoretical.k,
        empirical_k=best_empirical.k,
    )

    print_primary_summary(args.n, args.epsilon, m, k_real, k_int)
    print_k_table(points)
    print_epsilon_scenarios(epsilon_scenarios)

    print("\n=== Minima ===")
    print(
        f"Theoretical minimum at k={best_theoretical.k} "
        f"with epsilon={best_theoretical.theoretical_epsilon:.6f}"
    )
    print(
        f"Empirical minimum at k={best_empirical.k} "
        f"with epsilon={best_empirical.empirical_epsilon:.6f}"
    )
    print("\nSaved plots:")
    print(false_positive_plot)


if __name__ == "__main__":
    main()
