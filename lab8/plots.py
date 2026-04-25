import os
import tempfile

os.environ.setdefault(
    "MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "lab8-matplotlib")
)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from experiments import ExperimentPoint


def ensure_output_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def plot_false_positive_vs_k(
    points: list[ExperimentPoint],
    output_path: str,
    highlighted_k: int,
    empirical_k: int,
) -> None:
    ks = [point.k for point in points]
    theoretical = [point.theoretical_epsilon for point in points]
    empirical = [point.empirical_epsilon for point in points]

    plt.figure(figsize=(10, 6))
    plt.plot(ks, theoretical, marker="o", label="Theoretical epsilon")
    plt.plot(ks, empirical, marker="s", label="Empirical epsilon")
    plt.axvline(
        highlighted_k, color="red", linestyle="--", label=f"k_opt = {highlighted_k}"
    )
    plt.axvline(
        empirical_k,
        color="green",
        linestyle=":",
        label=f"k_emp = {empirical_k}",
    )
    plt.xlabel("Number of hash functions k")
    plt.ylabel("False-positive rate epsilon")
    plt.title("Bloom Filter: false-positive rate vs k")
    plt.xticks(ks)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, bbox_inches="tight")
    plt.close()
