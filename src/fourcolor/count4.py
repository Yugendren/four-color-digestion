"""Exact counting of proper 4-colourings of small planar graphs.

Used by the sharp-cap program (results/mass-law/PROOF-SHARP-CAP.md) to turn
the Bridge Lemma (a = |Phi(K)| <= P(S,4)/24) into a measurable quantity: we
need P(S,4) itself for corpus configurations and for synthetic min-degree-5
lattice disks.

Method: frontier dynamic programming over a vertex ordering chosen to keep
the frontier (already-coloured vertices that still have uncoloured
neighbours) small.  Two exactness-preserving reductions:

  * states are canonicalised up to the S_4 action on colours (the
    constraints on the *uncoloured* part are colour-blind, so two partial
    colourings whose frontier restrictions differ by a colour permutation
    have the same number of completions);
  * weights carry the true number of partial colourings in the class, so
    the final sum is the exact P(G,4).

`count_proper_4colorings` is validated in `tests/test_count4.py` against
closed forms for wheels (P(W_r,4) = 4(2^r + 2(-1)^r)), cycles
(3^r + 3(-1)^r) and complete graphs.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

Graph = Mapping[int, Sequence[int]]


def _undirected(adj: Graph) -> Dict[int, set]:
    g: Dict[int, set] = {int(v): set() for v in adj}
    for v, nbrs in adj.items():
        v = int(v)
        for u in nbrs:
            u = int(u)
            g.setdefault(u, set()).add(v)
            g[v].add(u)
    for v in g:
        g[v].discard(v)
    return g


def frontier_ordering(g: Dict[int, set]) -> List[int]:
    """Greedy ordering that keeps the frontier small.

    At each step choose the uncoloured vertex minimising
    (resulting frontier size, -#already-coloured neighbours, vertex id).
    """
    remaining = set(g)
    order: List[int] = []
    coloured: set = set()
    frontier: set = set()
    while remaining:
        best = None
        best_key = None
        for v in remaining:
            nb = g[v]
            placed = nb & coloured
            # frontier after placing v
            new_frontier = set(frontier)
            for u in placed:
                if not (g[u] - coloured - {v}):
                    new_frontier.discard(u)
            if nb - coloured - {v}:
                new_frontier.add(v)
            key = (len(new_frontier), -len(placed), v)
            if best_key is None or key < best_key:
                best_key, best = key, v
        v = best
        order.append(v)
        remaining.discard(v)
        coloured.add(v)
        for u in g[v] & coloured:
            if not (g[u] - coloured):
                frontier.discard(u)
        if g[v] - coloured:
            frontier.add(v)
    return order


def _canon(colors: Tuple[int, ...]) -> Tuple[int, ...]:
    """Relabel colours by order of first appearance."""
    m: Dict[int, int] = {}
    out = []
    for c in colors:
        j = m.get(c)
        if j is None:
            j = len(m)
            m[c] = j
        out.append(j)
    return tuple(out)


def count_proper_4colorings(adj: Graph, q: int = 4, order: Sequence[int] | None = None) -> int:
    """Exact number of proper q-colourings (default q=4) of the graph."""
    g = _undirected(adj)
    if not g:
        return 1
    order = list(order) if order is not None else frontier_ordering(g)
    pos = {v: i for i, v in enumerate(order)}

    # frontier_after[i] = tuple of vertices in the frontier after placing order[:i+1]
    coloured: set = set()
    frontier_seq: List[Tuple[int, ...]] = []
    frontier: List[int] = []
    for v in order:
        coloured.add(v)
        frontier = [u for u in frontier if (g[u] - coloured)]
        if g[v] - coloured:
            frontier.append(v)
        frontier_seq.append(tuple(frontier))

    # DP.  states: canonical colour tuple over frontier_seq[i] -> count
    states: Dict[Tuple[int, ...], int] = {(): 1}
    prev_frontier: Tuple[int, ...] = ()
    for i, v in enumerate(order):
        cur_frontier = frontier_seq[i]
        prev_index = {u: j for j, u in enumerate(prev_frontier)}
        # neighbours of v already coloured must all be in prev_frontier
        nb_prev = [prev_index[u] for u in g[v] if u in prev_index]
        assert all(pos[u] > i or u in prev_index for u in g[v] if pos[u] < i), "frontier bug"
        keep = [prev_index[u] for u in cur_frontier if u != v]
        v_in_cur = cur_frontier and cur_frontier[-1] == v
        new_states: Dict[Tuple[int, ...], int] = {}
        for st, w in states.items():
            used = set(st)
            forbidden = {st[j] for j in nb_prev}
            for c in range(q):
                if c in forbidden:
                    continue
                if c not in used and c > len(used):
                    # canonical-form symmetry: a fresh colour is
                    # interchangeable, only take the smallest fresh label
                    continue
                mult = 1
                if c not in used:
                    mult = q - len(used)
                base = [st[j] for j in keep]
                if v_in_cur:
                    base.append(c)
                key = _canon(tuple(base))
                new_states[key] = new_states.get(key, 0) + w * mult
        states = new_states
        prev_frontier = cur_frontier
    return sum(states.values())


def max_frontier(adj: Graph) -> int:
    g = _undirected(adj)
    order = frontier_ordering(g)
    coloured: set = set()
    frontier: List[int] = []
    w = 0
    for v in order:
        coloured.add(v)
        frontier = [u for u in frontier if (g[u] - coloured)]
        if g[v] - coloured:
            frontier.append(v)
        w = max(w, len(frontier))
    return w
