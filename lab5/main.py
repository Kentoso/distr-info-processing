import os

import networkx as nx

from models import INF
from shortest_path import nx_digraph_to_adj_matrix, run_shortest_path
from coloring import nx_graph_to_adj_list, make_initial_coloring, run_coloring
from visualize import DATA_DIR, visualize_shortest_path, visualize_coloring


def build_sp_graph() -> nx.DiGraph:
    """Classic 6-node weighted directed graph. Source=0, expected D=[0,7,9,20,20,11]."""
    G = nx.DiGraph()
    G.add_weighted_edges_from(
        [
            (0, 1, 7),
            (0, 2, 9),
            (0, 5, 14),
            (1, 2, 10),
            (1, 3, 15),
            (2, 3, 11),
            (2, 5, 2),
            (3, 4, 6),
            (4, 5, 9),
            (5, 4, 9),
        ]
    )
    return G


def main() -> None:
    # --- Task 1: Parallel Shortest Path ---
    print("=== Task 1: Parallel Shortest Path ===")
    G_sp = build_sp_graph()
    source = 0
    adj_matrix = nx_digraph_to_adj_matrix(G_sp)
    distances = run_shortest_path(adj_matrix, source)

    for v, d in enumerate(distances):
        print(f"  D[{v}] = {'INF' if d >= INF else int(d)}")

    visualize_shortest_path(
        G_sp,
        distances,
        source,
        "Parallel Shortest Path — 6-node graph (source=0)",
        os.path.join(DATA_DIR, "sp_result.png"),
    )

    # --- Task 2: Parallel Graph Coloring ---
    print("\n=== Task 2: Parallel Graph Coloring ===")
    G_col = nx.petersen_graph()
    adj_list = nx_graph_to_adj_list(G_col)
    initial_colors = make_initial_coloring(G_col)
    print(f"  Initial coloring uses {max(initial_colors)} colors")

    coloring, total_iters = run_coloring(adj_list, initial_colors)
    valid = all(
        coloring[v] != coloring[u]
        for v, neighbors in enumerate(adj_list)
        for u in neighbors
    )
    print(f"  Final coloring: {list(coloring)}")
    print(f"  Colors used: {max(coloring)}")
    print(f"  Coloring valid: {valid}")
    print(f"  Total minimization iterations: {total_iters}")

    visualize_coloring(
        G_col,
        coloring,
        "Parallel Graph Coloring — Petersen Graph",
        os.path.join(DATA_DIR, "col_petersen.png"),
    )


if __name__ == "__main__":
    main()
