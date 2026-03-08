import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

from mis import find_mis_tree

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)


def visualize_mis(tree: nx.Graph, mis: set, title: str, filename: str) -> None:
    try:
        pos = nx.planar_layout(tree)
    except nx.NetworkXException:
        pos = nx.spring_layout(tree, seed=42)

    node_colors = ["red" if n in mis else "lightblue" for n in tree.nodes()]

    plt.figure(figsize=(8, 6))
    nx.draw(
        tree,
        pos,
        node_color=node_colors,
        with_labels=True,
        node_size=600,
        font_size=10,
    )
    plt.title(title)
    plt.savefig(filename, bbox_inches="tight")
    plt.close()
    print(f"Saved {filename}")


def main() -> None:
    # Example 1: balanced binary tree (branching=2, height=3)
    tree1 = nx.balanced_tree(2, 3)
    mis1 = find_mis_tree(tree1, root=0)
    print("=== Balanced Binary Tree (r=2, h=3) ===")
    print(f"MIS size: {len(mis1)}")
    print(f"MIS nodes: {sorted(mis1)}")
    visualize_mis(
        tree1,
        mis1,
        "MIS — Balanced Binary Tree (r=2, h=3)",
        os.path.join(DATA_DIR, "mis_binary_tree.png"),
    )

    # Example 2: path graph with 7 nodes
    tree2 = nx.path_graph(7)
    mis2 = find_mis_tree(tree2, root=0)
    print("\n=== Path Graph (n=7) ===")
    print(f"MIS size: {len(mis2)}")
    print(f"MIS nodes: {sorted(mis2)}")
    visualize_mis(
        tree2,
        mis2,
        "MIS — Path Graph (n=7)",
        os.path.join(DATA_DIR, "mis_path_graph.png"),
    )


if __name__ == "__main__":
    main()
