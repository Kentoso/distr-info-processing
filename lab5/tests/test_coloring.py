import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import networkx as nx

from models import AdjList, Coloring
from coloring import nx_graph_to_adj_list, make_initial_coloring, run_coloring
from visualize import DATA_DIR, visualize_coloring


def is_valid_coloring(adj: AdjList, coloring: Coloring) -> bool:
    return all(
        coloring[v] != coloring[u]
        for v, neighbors in enumerate(adj)
        for u in neighbors
    )


def _img(name: str) -> str:
    return os.path.join(DATA_DIR, name)


def run_and_check(G: nx.Graph, img_name: str) -> tuple[Coloring, int]:
    adj = nx_graph_to_adj_list(G)
    initial = make_initial_coloring(G)
    coloring, iters = run_coloring(adj, initial)
    assert is_valid_coloring(adj, coloring), (
        f"Invalid coloring: {list(coloring)}"
    )
    print(f"\n  [{img_name}] colors: {max(initial)} → {max(coloring)}, iterations: {iters}")
    visualize_coloring(G, coloring, f"Coloring — {img_name}", _img(f"{img_name}.png"))
    return coloring, iters


def test_petersen_graph():
    # Petersen graph is 3-regular → stable coloring uses at most 4 colors; χ = 3
    G = nx.petersen_graph()
    coloring, _ = run_and_check(G, "col_petersen")
    assert max(coloring) <= 4


def test_complete_k4():
    # K4: initial coloring is [1,2,3,4] shuffled — all distinct → immediately stable at 4
    G = nx.complete_graph(4)
    coloring, _ = run_and_check(G, "col_k4")
    assert max(coloring) == 4


def test_complete_k5():
    # K5: initial coloring is [1,2,3,4,5] shuffled — all distinct → immediately stable at 5
    G = nx.complete_graph(5)
    coloring, _ = run_and_check(G, "col_k5")
    assert max(coloring) == 5


def test_path_graph():
    # Path graph is bipartite (χ = 2); algorithm valid but not guaranteed to reach χ
    G = nx.path_graph(6)
    coloring, _ = run_and_check(G, "col_path_6")
    assert max(coloring) <= 3  # degree 2 → stable coloring uses at most 3 colors


def test_cycle_even():
    # Even cycle is bipartite (χ = 2); degree 2 → stable coloring uses at most 3 colors
    G = nx.cycle_graph(6)
    coloring, _ = run_and_check(G, "col_cycle_6")
    assert max(coloring) <= 3


def test_cycle_odd():
    # Odd cycle: χ = 3 and degree 2 → stable coloring uses exactly 3 colors
    G = nx.cycle_graph(5)
    coloring, _ = run_and_check(G, "col_cycle_5")
    assert max(coloring) == 3


def test_complete_bipartite():
    # K(3,3) is 3-regular → stable coloring uses at most 4 colors; χ = 2
    G = nx.complete_bipartite_graph(3, 3)
    coloring, _ = run_and_check(G, "col_bipartite_3_3")
    assert max(coloring) <= 4


def test_star_graph():
    # Star graph: leaves have degree 1 → always converge to exactly 2 colors
    G = nx.star_graph(5)
    coloring, _ = run_and_check(G, "col_star_5")
    assert max(coloring) == 2


def test_wheel_graph():
    G = nx.wheel_graph(7)  # 1 hub + 6 rim nodes
    coloring, _ = run_and_check(G, "col_wheel_7")


def test_random_graph_validity():
    G = nx.gnp_random_graph(20, 0.4, seed=42)
    coloring, _ = run_and_check(G, "col_random_20")


def test_coloring_improves_on_initial():
    G = nx.petersen_graph()
    adj = nx_graph_to_adj_list(G)
    initial = make_initial_coloring(G)
    coloring, _ = run_coloring(adj, initial)
    assert max(coloring) <= max(initial)
