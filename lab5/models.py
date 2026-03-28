from typing import NewType

INF = float("inf")

AdjMatrix = NewType(
    "AdjMatrix", list[list[float]]
)  # N×N weighted directed adjacency matrix (INF = no edge)
DistanceBuffer = NewType(
    "DistanceBuffer", list[list[float]]
)  # double buffer [D_old, D_new]
DistanceVector = NewType(
    "DistanceVector", list[float]
)  # shortest distances from source

AdjList = NewType("AdjList", list[set[int]])  # undirected adjacency list
Coloring = NewType("Coloring", list[int])  # 1-indexed color assignment per node
