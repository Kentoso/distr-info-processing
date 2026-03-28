import threading

import networkx as nx

from models import INF, AdjMatrix, DistanceBuffer, DistanceVector


def nx_digraph_to_adj_matrix(G: nx.DiGraph) -> AdjMatrix:
    nodes = sorted(G.nodes())
    n = len(nodes)
    idx = {v: i for i, v in enumerate(nodes)}
    matrix: list[list[float]] = [[INF] * n for _ in range(n)]
    for u, v, data in G.edges(data=True):
        matrix[idx[u]][idx[v]] = float(data.get("weight", 1.0))
    return AdjMatrix(matrix)


def _worker(
    v: int,
    graph: AdjMatrix,
    N: int,
    buf: DistanceBuffer,
    which: list[int],
    barrier: threading.Barrier,
) -> None:
    for _ in range(N):
        old = which[0]
        new = 1 - old
        best = buf[old][v]
        for w in range(N):
            if graph[w][v] < INF and buf[old][w] < INF:
                candidate = buf[old][w] + graph[w][v]
                if candidate < best:
                    best = candidate
        buf[new][v] = best
        barrier.wait()


def run_shortest_path(graph: AdjMatrix, source: int) -> DistanceVector:
    N = len(graph)
    D0: list[float] = [INF] * N
    D1: list[float] = [INF] * N
    D0[source] = 0.0
    D1[source] = 0.0

    buf = DistanceBuffer([D0, D1])
    which = [0]

    def swap() -> None:
        which[0] = 1 - which[0]

    barrier = threading.Barrier(N, action=swap)
    threads = [
        threading.Thread(target=_worker, args=(v, graph, N, buf, which, barrier))
        for v in range(N)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    return DistanceVector(buf[which[0]])
