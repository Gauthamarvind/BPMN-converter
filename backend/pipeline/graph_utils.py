"""
Pure graph helpers used by the layout engine and the chunk merger.

Kept free of any model imports so they can be unit-tested and reasoned about in isolation.
All functions work on plain node-id strings and (source, target) tuples.
"""

from __future__ import annotations
from typing import Dict, Iterable, List, Sequence, Set, Tuple

Edge = Tuple[str, str]


def build_adjacency(node_ids: Sequence[str], edges: Iterable[Edge]) -> Dict[str, List[str]]:
    """Out-adjacency restricted to known nodes, preserving edge order and dropping duplicates."""
    out: Dict[str, List[str]] = {n: [] for n in node_ids}
    for src, tgt in edges:
        if src in out and tgt in out and tgt not in out[src]:
            out[src].append(tgt)
    return out


def find_back_edges(
    node_ids: Sequence[str],
    edges: Iterable[Edge],
    roots: Sequence[str],
) -> Set[Edge]:
    """
    Iterative DFS cycle breaking.

    Returns the set of edges whose target is still on the DFS stack when the edge is
    explored (classic "back edges"). Removing exactly these edges turns the graph into a
    DAG while keeping every forward edge, so a loop such as 1 -> 2 -> 3 -> 1 is broken at
    3 -> 1 and node 1 keeps its natural position before 2 and 3.

    The DFS starts from `roots` (the start events) so that the *intended* process direction
    decides which edge of a cycle is the loop-back. Nodes unreachable from any root are
    visited afterwards so the result covers the whole graph.
    """
    out = build_adjacency(node_ids, edges)
    state: Dict[str, int] = {}  # absent = unvisited, 1 = on stack, 2 = finished
    back: Set[Edge] = set()

    def visit(root: str) -> None:
        if state.get(root):
            return
        stack: List[Tuple[str, int]] = [(root, 0)]
        state[root] = 1
        while stack:
            node, idx = stack[-1]
            succ = out.get(node, [])
            if idx < len(succ):
                stack[-1] = (node, idx + 1)
                nxt = succ[idx]
                s = state.get(nxt, 0)
                if s == 1:
                    back.add((node, nxt))
                elif s == 0:
                    state[nxt] = 1
                    stack.append((nxt, 0))
            else:
                state[node] = 2
                stack.pop()

    for r in roots:
        if r in out:
            visit(r)
    for n in node_ids:
        visit(n)
    return back


def longest_path_ranks(node_ids: Sequence[str], dag_edges: Iterable[Edge]) -> Dict[str, int]:
    """
    Longest-path layering (Kahn's algorithm) over an acyclic edge set.

    Every node gets rank = 1 + max(rank of predecessors); sources get rank 0. If the edge
    set still contains a cycle (should not happen after `find_back_edges`), the nodes stuck
    on that cycle are appended after the last resolved rank so nothing is ever lost.
    """
    out = build_adjacency(node_ids, dag_edges)
    indeg: Dict[str, int] = {n: 0 for n in node_ids}
    for src, targets in out.items():
        for tgt in targets:
            indeg[tgt] += 1

    ranks: Dict[str, int] = {n: 0 for n in node_ids if indeg[n] == 0}
    queue: List[str] = [n for n in node_ids if indeg[n] == 0]
    head = 0
    while head < len(queue):
        cur = queue[head]
        head += 1
        for nxt in out.get(cur, []):
            ranks[nxt] = max(ranks.get(nxt, 0), ranks[cur] + 1)
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)

    if len(ranks) < len(node_ids):
        spill = (max(ranks.values()) + 1) if ranks else 0
        for n in node_ids:
            if n not in ranks:
                ranks[n] = spill
    return ranks


def compute_layered_ranks(
    node_ids: Sequence[str],
    edges: Iterable[Edge],
    roots: Sequence[str],
) -> Tuple[Dict[str, int], Set[Edge]]:
    """Convenience wrapper: break cycles from `roots`, then layer the remaining DAG."""
    edge_list = list(edges)
    back = find_back_edges(node_ids, edge_list, roots)
    forward = [e for e in edge_list if e not in back]
    return longest_path_ranks(node_ids, forward), back


def order_within_ranks(
    ranks: Dict[str, int],
    node_order: Sequence[str],
    dag_edges: Iterable[Edge],
    sweeps: int = 4,
) -> Dict[str, int]:
    """
    Barycenter crossing reduction. Returns a position index for every node within its rank.

    Nodes are ordered by the average position of their predecessors (downward sweep) and
    successors (upward sweep), alternating for a few passes. Ties keep the original order,
    which keeps the result deterministic.
    """
    preds: Dict[str, List[str]] = {n: [] for n in node_order}
    succs: Dict[str, List[str]] = {n: [] for n in node_order}
    for src, tgt in dag_edges:
        if src in preds and tgt in preds:
            succs[src].append(tgt)
            preds[tgt].append(src)

    layers: Dict[int, List[str]] = {}
    for n in node_order:
        layers.setdefault(ranks.get(n, 0), []).append(n)
    layer_keys = sorted(layers)

    pos: Dict[str, int] = {}
    for k in layer_keys:
        for i, n in enumerate(layers[k]):
            pos[n] = i

    def sweep(keys: Sequence[int], neighbours: Dict[str, List[str]]) -> None:
        for k in keys:
            layer = layers[k]
            scored = []
            for i, n in enumerate(layer):
                nb = [pos[m] for m in neighbours[n] if m in pos]
                bary = (sum(nb) / len(nb)) if nb else float(i)
                scored.append((bary, i, n))
            scored.sort()
            layers[k] = [n for _, _, n in scored]
            for i, n in enumerate(layers[k]):
                pos[n] = i

    for _ in range(sweeps):
        sweep(layer_keys[1:], preds)
        sweep(list(reversed(layer_keys[:-1])), succs)
    return pos
