import random
import threading

import networkx as nx

from models import AdjList, Coloring


def nx_graph_to_adj_list(G: nx.Graph) -> AdjList:
    nodes = sorted(G.nodes())
    idx = {v: i for i, v in enumerate(nodes)}
    adj: list[set[int]] = [set() for _ in range(len(nodes))]
    for u, v in G.edges():
        adj[idx[u]].add(idx[v])
        adj[idx[v]].add(idx[u])
    return AdjList(adj)


def make_initial_coloring(G: nx.Graph, seed: int | None = None) -> Coloring:
    """Return a valid coloring: colors 1..N shuffled. Always valid since all colors are distinct."""
    n = G.number_of_nodes()
    colors = list(range(1, n + 1))
    random.Random(seed).shuffle(colors)
    return Coloring(colors)


def _minimize(
    v: int,
    colors: Coloring,
    locks: list[threading.Lock],
    adj: AdjList,
) -> bool:
    to_lock = sorted({v} | adj[v])
    for u in to_lock:
        locks[u].acquire()
    try:
        neighbor_colors = {colors[u] for u in adj[v]}
        new_color = 1
        while new_color in neighbor_colors:
            new_color += 1
        changed = colors[v] != new_color
        colors[v] = new_color
        return changed
    finally:
        for u in reversed(to_lock):
            locks[u].release()


def _worker(
    tid: int,
    colors: Coloring,
    locks: list[threading.Lock],
    adj: AdjList,
    N: int,
    stop_event: threading.Event,
    dirty: list[bool],
    dirty_lock: threading.Lock,
    barrier: threading.Barrier,
) -> None:
    rng = random.Random(tid * 9973 + id(colors))

    while not stop_event.is_set():
        v = rng.randrange(N)
        if _minimize(v, colors, locks, adj):
            with dirty_lock:
                dirty[0] = True

        barrier.wait()


def run_coloring(
    adj: AdjList,
    initial_colors: Coloring,
    n_threads: int | None = None,
) -> tuple[Coloring, int]:
    N = len(adj)
    T = n_threads if n_threads is not None else N
    colors = Coloring(list(initial_colors))
    locks = [threading.Lock() for _ in range(N)]
    dirty: list[bool] = [False]
    dirty_lock = threading.Lock()
    stop_event = threading.Event()
    iterations: list[int] = [0]
    quiet: list[int] = [0]

    def barrier_action() -> None:
        iterations[0] += 1
        if not dirty[0]:
            quiet[0] += 1
            if quiet[0] >= N:
                stop_event.set()
        else:
            quiet[0] = 0
        dirty[0] = False

    barrier = threading.Barrier(T, action=barrier_action)
    threads = [
        threading.Thread(
            target=_worker,
            args=(i, colors, locks, adj, N, stop_event, dirty, dirty_lock, barrier),
        )
        for i in range(T)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    return colors, iterations[0]
