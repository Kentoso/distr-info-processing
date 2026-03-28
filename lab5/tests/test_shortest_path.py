import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import networkx as nx
import pytest

from models import INF
from shortest_path import nx_digraph_to_adj_matrix, run_shortest_path
from visualize import DATA_DIR, visualize_shortest_path


def oracle(G: nx.DiGraph, source: int) -> list[float]:
    lengths = nx.single_source_dijkstra_path_length(G, source, weight="weight")
    n = G.number_of_nodes()
    return [float(lengths.get(v, INF)) for v in range(n)]


def _img(name: str) -> str:
    return os.path.join(DATA_DIR, name)


def run_and_check(G: nx.DiGraph, source: int, img_name: str) -> list[float]:
    matrix = nx_digraph_to_adj_matrix(G)
    distances = run_shortest_path(matrix, source)
    expected = oracle(G, source)
    for v in range(G.number_of_nodes()):
        assert distances[v] == pytest.approx(expected[v], abs=1e-9), (
            f"D[{v}]: got {distances[v]}, expected {expected[v]}"
        )
    visualize_shortest_path(
        G, distances, source, f"SP — {img_name}", _img(f"{img_name}.png")
    )
    return distances


def test_classic_6node():
    G = nx.DiGraph()
    G.add_weighted_edges_from([
        (0, 1, 7), (0, 2, 9), (0, 5, 14),
        (1, 2, 10), (1, 3, 15),
        (2, 3, 11), (2, 5, 2),
        (3, 4, 6),
        (4, 5, 9), (5, 4, 9),
    ])
    distances = run_and_check(G, 0, "sp_classic_6node")
    for v, exp in enumerate([0, 7, 9, 20, 20, 11]):
        assert distances[v] == pytest.approx(exp, abs=1e-9)


def test_single_node():
    G = nx.DiGraph()
    G.add_node(0)
    distances = run_and_check(G, 0, "sp_single_node")
    assert distances[0] == pytest.approx(0.0)


def test_two_nodes_direct():
    G = nx.DiGraph()
    G.add_weighted_edges_from([(0, 1, 5)])
    distances = run_and_check(G, 0, "sp_two_nodes")
    assert distances[0] == pytest.approx(0.0)
    assert distances[1] == pytest.approx(5.0)


def test_unreachable_node():
    G = nx.DiGraph()
    G.add_weighted_edges_from([(0, 1, 3)])
    G.add_node(2)
    distances = run_and_check(G, 0, "sp_unreachable")
    assert distances[2] == INF


def test_path_graph():
    # 0 -> 1 -> 2 -> 3 -> 4 -> 5, all weight 1
    G = nx.DiGraph()
    for i in range(5):
        G.add_edge(i, i + 1, weight=1)
    distances = run_and_check(G, 0, "sp_path_5")
    for v in range(6):
        assert distances[v] == pytest.approx(float(v))


def test_two_paths_picks_shorter():
    # 0->1->3 (cost 3) vs 0->2->3 (cost 6)
    G = nx.DiGraph()
    G.add_weighted_edges_from([(0, 1, 2), (1, 3, 1), (0, 2, 1), (2, 3, 5)])
    distances = run_and_check(G, 0, "sp_two_paths")
    assert distances[3] == pytest.approx(3.0)


def test_shortcut_beats_direct():
    # direct 0->1 costs 10, shortcut 0->2->1 costs 3
    G = nx.DiGraph()
    G.add_weighted_edges_from([(0, 1, 10), (0, 2, 1), (2, 1, 2)])
    distances = run_and_check(G, 0, "sp_shortcut")
    assert distances[1] == pytest.approx(3.0)


def test_grid_graph():
    # 3×3 grid as directed graph (right + down edges only)
    G = nx.DiGraph()
    for r in range(3):
        for c in range(3):
            v = r * 3 + c
            if c + 1 < 3:
                G.add_edge(v, v + 1, weight=1)
            if r + 1 < 3:
                G.add_edge(v, v + 3, weight=1)
    run_and_check(G, 0, "sp_grid_3x3")


def test_balanced_tree_dijkstra():
    # Convert undirected balanced tree to directed (both ways) with unit weights
    T = nx.balanced_tree(2, 3)
    G = nx.DiGraph()
    for u, v in T.edges():
        G.add_edge(u, v, weight=1)
        G.add_edge(v, u, weight=1)
    run_and_check(G, 0, "sp_balanced_tree")
