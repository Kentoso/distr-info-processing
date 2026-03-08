import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import networkx as nx

from main import DATA_DIR, visualize_mis
from luby import find_mis_luby


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
    mis = find_mis_luby(G, seed=42)
    assert mis == {0}
    visualize_mis(G, mis, "MIS — Single Node (Luby)", _img("luby_single_node.png"))


def test_complete_graph():
    G = nx.complete_graph(5)
    mis = find_mis_luby(G, seed=42)
    assert len(mis) == 1
    assert is_maximal_independent_set(G, mis)
    visualize_mis(G, mis, "MIS — K5 (Luby)", _img("luby_complete_k5.png"))


def test_path_graph():
    G = nx.path_graph(6)
    mis = find_mis_luby(G, seed=42)
    assert is_maximal_independent_set(G, mis)
    visualize_mis(G, mis, "MIS — Path (n=6) (Luby)", _img("luby_path_6.png"))


def test_cycle_even():
    G = nx.cycle_graph(6)
    mis = find_mis_luby(G, seed=42)
    assert is_maximal_independent_set(G, mis)
    assert len(mis) == 3
    visualize_mis(G, mis, "MIS — Cycle (n=6) (Luby)", _img("luby_cycle_6.png"))


def test_cycle_odd():
    G = nx.cycle_graph(5)
    mis = find_mis_luby(G, seed=42)
    assert is_maximal_independent_set(G, mis)
    visualize_mis(G, mis, "MIS — Cycle (n=5) (Luby)", _img("luby_cycle_5.png"))


def test_petersen():
    G = nx.petersen_graph()
    mis = find_mis_luby(G, seed=42)
    assert is_maximal_independent_set(G, mis)
    visualize_mis(G, mis, "MIS — Petersen Graph (Luby)", _img("luby_petersen.png"))


def test_bipartite():
    G = nx.complete_bipartite_graph(3, 4)
    mis = find_mis_luby(G, seed=42)
    assert is_maximal_independent_set(G, mis)
    visualize_mis(
        G, mis, "MIS — Complete Bipartite K(3,4) (Luby)", _img("luby_bipartite_3_4.png")
    )


def test_random_graph():
    G = nx.gnp_random_graph(15, 0.3, seed=42)
    mis = find_mis_luby(G, seed=42)
    assert is_maximal_independent_set(G, mis)
    visualize_mis(
        G, mis, "MIS — Random Graph G(15,0.3) (Luby)", _img("luby_random_15.png")
    )
