import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import networkx as nx

from main import DATA_DIR, visualize_mis
from mis import find_mis_tree


def is_independent_set(G: nx.Graph, nodes: set) -> bool:
    for u in nodes:
        for v in G.neighbors(u):
            if v in nodes:
                return False
    return True


def is_maximal_independent_set(G: nx.Graph, nodes: set) -> bool:
    if not is_independent_set(G, nodes):
        return False
    for v in G.nodes():
        if v not in nodes:
            if not any(nb in nodes for nb in G.neighbors(v)):
                return False
    return True


def _img(name: str) -> str:
    return os.path.join(DATA_DIR, name)


def test_single_node():
    G = nx.Graph()
    G.add_node(0)
    mis = find_mis_tree(G, root=0)
    assert mis == {0}
    visualize_mis(G, mis, "MIS — Single Node", _img("test_single_node.png"))


def test_path_2():
    G = nx.path_graph(2)
    mis = find_mis_tree(G, root=0)
    assert len(mis) == 1
    assert is_maximal_independent_set(G, mis)
    visualize_mis(G, mis, "MIS — Path (n=2)", _img("test_path_2.png"))


def test_path_5():
    G = nx.path_graph(5)
    mis = find_mis_tree(G, root=0)
    assert len(mis) == 3
    assert is_maximal_independent_set(G, mis)
    visualize_mis(G, mis, "MIS — Path (n=5)", _img("test_path_5.png"))


def test_path_7():
    G = nx.path_graph(7)
    mis = find_mis_tree(G, root=0)
    assert len(mis) == 4
    assert is_maximal_independent_set(G, mis)
    visualize_mis(G, mis, "MIS — Path (n=7)", _img("test_path_7.png"))


def test_star_5_leaves():
    # star_graph(5) has 1 center + 5 leaves; optimal MIS = all 5 leaves
    G = nx.star_graph(5)
    mis = find_mis_tree(G, root=0)
    assert len(mis) == 5
    assert is_maximal_independent_set(G, mis)
    visualize_mis(G, mis, "MIS — Star (5 leaves)", _img("test_star_5_leaves.png"))


def test_balanced_binary_tree():
    G = nx.balanced_tree(2, 3)
    mis = find_mis_tree(G, root=0)
    assert is_maximal_independent_set(G, mis)
    # balanced_tree(2,3) has 15 nodes; optimal MIS size is 10 (levels 1+3)
    assert len(mis) == 10
    visualize_mis(
        G,
        mis,
        "MIS — Balanced Binary Tree (r=2, h=3)",
        _img("test_balanced_binary_tree.png"),
    )


def test_caterpillar():
    # Path 0-1-2-3 with extra leaves: 4,5 on node 1 and 6,7 on node 2
    G = nx.Graph()
    G.add_edges_from([(0, 1), (1, 2), (2, 3), (1, 4), (1, 5), (2, 6), (2, 7)])
    mis = find_mis_tree(G, root=0)
    assert is_maximal_independent_set(G, mis)
    visualize_mis(G, mis, "MIS - Caterpillar", _img("test_caterpillar.png"))


def test_random_tree():
    G = nx.random_labeled_tree(30, seed=42)
    mis = find_mis_tree(G, root=0)
    assert is_maximal_independent_set(G, mis)
    visualize_mis(G, mis, "MIS — Random Tree (n=30)", _img("test_random_tree.png"))
