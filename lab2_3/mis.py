import networkx as nx
from models import NodeId


def find_mis_tree(tree: nx.Graph, root: int = 0) -> set[NodeId]:
    rooted = nx.bfs_tree(tree, root)
    order = list(reversed(list(rooted.nodes())))

    dp0: dict[int, int] = {}  # max MIS size in subtree if node is NOT taken
    dp1: dict[int, int] = {}  # max MIS size in subtree if node IS taken

    for v in order:
        children = list(rooted.successors(v))
        dp1[v] = 1 + sum(dp0[c] for c in children)
        dp0[v] = sum(max(dp0[c], dp1[c]) for c in children)

    mis: set[NodeId] = set()
    stack = [(root, False)]
    while stack:
        v, parent_taken = stack.pop()
        take = (not parent_taken) and (dp1[v] >= dp0[v])
        if take:
            mis.add(NodeId(v))
        for c in rooted.successors(v):
            stack.append((c, take))

    return mis
