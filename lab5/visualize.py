import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import networkx as nx

from models import INF, Coloring, DistanceVector

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)


def visualize_shortest_path(
    G: nx.DiGraph,
    distances: DistanceVector,
    source: int,
    title: str,
    filename: str,
) -> None:
    pos = nx.spring_layout(G, seed=42)

    finite_dists = [d for d in distances if d < INF]
    max_dist = max(finite_dists) if finite_dists else 1.0
    if max_dist == 0.0:
        max_dist = 1.0
    node_colors = [
        cm.YlOrRd(distances[n] / max_dist) if distances[n] < INF else (0.5, 0.5, 0.5, 1.0)
        for n in G.nodes()
    ]
    labels = {
        n: f"{n}\n({'∞' if distances[n] >= INF else int(distances[n])})"
        for n in G.nodes()
    }
    edge_labels = {(u, v): d["weight"] for u, v, d in G.edges(data=True)}

    plt.figure(figsize=(10, 7))
    nx.draw(
        G,
        pos,
        node_color=node_colors,
        labels=labels,
        with_labels=True,
        node_size=900,
        font_size=9,
        arrows=True,
        arrowsize=15,
    )
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=8)
    plt.title(title)
    plt.savefig(filename, bbox_inches="tight", dpi=120)
    plt.close()
    print(f"Saved {filename}")


def visualize_coloring(
    G: nx.Graph,
    coloring: Coloring,
    title: str,
    filename: str,
) -> None:
    try:
        pos = nx.planar_layout(G)
    except nx.NetworkXException:
        pos = nx.spring_layout(G, seed=42)

    n_colors = max(coloring) if coloring else 1
    palette = plt.get_cmap("tab10")
    node_colors = [
        palette((coloring[n] - 1) / max(n_colors, 1))
        for n in G.nodes()
    ]

    plt.figure(figsize=(8, 6))
    nx.draw(
        G,
        pos,
        node_color=node_colors,
        with_labels=True,
        node_size=600,
        font_size=10,
    )
    plt.title(f"{title}\n({n_colors} colors used)")
    plt.savefig(filename, bbox_inches="tight", dpi=120)
    plt.close()
    print(f"Saved {filename}")
