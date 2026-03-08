import random
from dataclasses import dataclass, field

import networkx as nx

from models import NodeId


def find_mis_luby(G: nx.Graph, seed: int | None = None) -> set[NodeId]:
    rng = random.Random(seed)
    remaining = set(G.nodes())
    mis: set[NodeId] = set()

    while remaining:
        priority = {v: rng.random() for v in remaining}
        candidates = {
            v
            for v in remaining
            if all(priority[v] > priority[u] for u in G.neighbors(v) if u in remaining)
        }
        mis.update(NodeId(v) for v in candidates)
        neighbors_of_candidates = {u for v in candidates for u in G.neighbors(v)}
        remaining -= candidates | neighbors_of_candidates

    return mis
