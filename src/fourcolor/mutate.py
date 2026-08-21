"""Local structure-preserving mutation operators for `Configuration`
adjacency, used by `tools/stress_test_theorem.py` to manufacture "hard
negative" candidates near the theorem candidates mined in
`results/theorem/candidates.md`.

Implements the standard triangulation move -- the diagonal (edge) flip --
directly on the cyclic-order adjacency-list representation that
`fourcolor.reduce._edges_and_triangles` and `fourcolor.canonical` both
already depend on (triangle detection there is "two cyclically consecutive
neighbors of v that are adjacent to each other", so getting the cyclic
order right after a mutation is not optional -- an out-of-order neighbor
list would silently corrupt every downstream feature/label computation).

Geometry (see the module for a from-scratch derivation): a *free
completion* here is a disk triangulated on the inside of an r-cycle ring
boundary (ring vertices 1..r, interior r+1..n). Every edge NOT one of the
r ring-boundary edges borders exactly two triangular faces (u, v, a) and
(u, v, b). Flipping edge (u, v) means: remove edge u-v, add edge a-b,
turning those two triangles into (u, a, b) and (v, a, b). This is a local,
planarity-preserving move that changes neither `n` nor `r` nor any
vertex's ring/interior status, and is invertible.

Two vertices u, a are adjacent in u's cyclic list at a face corner iff no
other neighbor of u lies "between" them on that side; since (u, v, a) is a
triangular face, v is immediately before or after a in u's cyclic list
(same for b on the other side) -- so removing v from u's list makes a, b
adjacent automatically (no reordering needed at u or v). At a, edges a-u
and a-v both already exist and must be CYCLICALLY CONSECUTIVE in a's list
(nothing else can occupy the wedge belonging to face (u,v,a)); the new
edge a-b is inserted into that exact wedge. Symmetric for b.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

Adjacency = dict[int, list[int]]


def ring_edges(r: int) -> set[frozenset[int]]:
    """The r boundary-cycle edges {i, i+1} (1-indexed, wrapping r->1)."""
    return {frozenset((i, i % r + 1)) for i in range(1, r + 1)}


def _consecutive_positions(lst: list[int], x: int, y: int) -> tuple[int, int] | None:
    """If x, y appear CYCLICALLY CONSECUTIVE in lst (in either order),
    returns (idx_of_first, idx_of_second) such that lst[idx_of_first] is
    immediately followed (cyclically) by lst[idx_of_second]. None if x, y
    are not adjacent in the cyclic list (or either is missing)."""
    n = len(lst)
    try:
        ix, iy = lst.index(x), lst.index(y)
    except ValueError:
        return None
    if (ix + 1) % n == iy:
        return ix, iy
    if (iy + 1) % n == ix:
        return iy, ix
    return None


@dataclass(frozen=True)
class FlipResult:
    adjacency: Adjacency
    u: int
    v: int
    a: int
    b: int


def flip_edge(adjacency: Adjacency, r: int, u: int, v: int) -> FlipResult | None:
    """Attempts the diagonal flip of edge (u, v). Returns None (a no-op,
    caller tries a different edge) if: (u, v) is not an edge, is one of the
    r ring-boundary edges (only 1 incident triangle -- not flippable), the
    two apex vertices a, b degenerate (equal, or already adjacent -- flipping
    would create a multi-edge / self-loop), or the local cyclic-order
    assumptions a genuine triangulation guarantees don't hold (defensive;
    would indicate the input wasn't actually a clean triangulation)."""
    if u not in adjacency or v not in adjacency[u]:
        return None
    if frozenset((u, v)) in ring_edges(r):
        return None

    lu = adjacency[u]
    i = lu.index(v)
    a = lu[(i - 1) % len(lu)]
    b = lu[(i + 1) % len(lu)]
    if a == b or a == u or b == u:
        return None
    lv = adjacency[v]
    if a not in lv or b not in lv:
        return None  # not a genuine triangulated edge; defensive bail-out
    if b in adjacency[a]:
        return None  # a-b already an edge -> flip would create a multi-edge

    new_adj: Adjacency = {k: list(nbrs) for k, nbrs in adjacency.items()}
    new_adj[u].remove(v)
    new_adj[v].remove(u)

    pos_a = _consecutive_positions(new_adj[a], u, v)
    pos_b = _consecutive_positions(new_adj[b], u, v)
    if pos_a is None or pos_b is None:
        return None  # defensive: shouldn't happen in a valid triangulation
    ia, _ = pos_a
    new_adj[a].insert(ia + 1, b)
    ib, _ = pos_b
    new_adj[b].insert(ib + 1, a)

    return FlipResult(new_adj, u, v, a, b)


def flippable_edges(adjacency: Adjacency, r: int) -> list[tuple[int, int]]:
    """All (u, v), u < v, edges that are not ring-boundary edges (necessary
    but not sufficient for flip_edge to succeed -- the apex-degeneracy
    checks happen inside flip_edge itself)."""
    redges = ring_edges(r)
    out = []
    seen: set[frozenset[int]] = set()
    for u, nbrs in adjacency.items():
        for v in nbrs:
            e = frozenset((u, v))
            if e in seen or e in redges:
                continue
            seen.add(e)
            out.append((min(u, v), max(u, v)))
    return out


def is_legal_configuration(adjacency: Adjacency, r: int, n: int) -> bool:
    """Faithful port of the RSST reference oracle's own well-formedness
    predicate (`ReadConf`'s conditions (1)-(7) in `third_party/arxiv-1401.
    6481/src/anc/reduce.c`, lines ~974-1030), which is the AUTHORITATIVE
    definition of "legal configuration" the theorem candidates are stated
    over -- not just "passes Configuration.validate() + has the right edge/
    triangle count" (that invariant alone is necessary but NOT sufficient:
    a single edge flip can legally preserve it while dropping a ring
    vertex's degree to 2, which condition (2) below forbids; an earlier
    version of this stress test's gate missed that and had to be corrected
    after the C oracle rejected a "false positive" witness with
    `ReadErr(2, ...)`). Conditions (1) and (3) are already implied by
    `Configuration.validate()` (0 < r < n; every neighbor is a valid
    in-range vertex) and are not re-checked here.

    Conditions ported:
      (2) ring vertices have degree in [3, n); interior vertices have
          degree in [5, n).
      (4) ring vertices' cyclic neighbor lists start/end at their two ring
          neighbors, and every OTHER neighbor is interior (r < v <= n) --
          already guaranteed by construction here (flips never touch ring
          edges), checked anyway as a cheap invariant.
      (5) sum of all degrees == 6(n-1) - 2r (double the edge count E from
          the module docstring's E = 3n - r - 3 derivation).
      (6) each interior vertex touches the ring boundary in a bounded
          number of separate arcs (the reference's own phrasing: at most 2
          "ring contact" transitions around its rotation).
      (7) rotational consistency: for every directed edge i->k with `a`
          the next neighbor after k in i's rotation, the pair (a, i) must
          appear consecutively in k's own rotation list -- the precise
          "is this really one consistent combinatorial embedding" check.
          (Believed redundant with the flip's own correctness argument in
          this module's docstring plus the round-trip test in the test
          suite, but ported anyway as a second independent check -- cheap,
          and this IS the exact condition the historical oracle enforces.)
    """
    for v, nbrs in adjacency.items():
        d = len(nbrs)
        if v <= r:
            if d < 3 or d >= n:
                return False
        else:
            if d < 5 or d >= n:
                return False

    for v in range(1, r + 1):
        nbrs = adjacency[v]
        d = len(nbrs)
        expected_next = 1 if v == r else v + 1
        expected_prev = r if v == 1 else v - 1
        if nbrs[0] != expected_next or nbrs[-1] != expected_prev:
            return False
        for u in nbrs[1:-1]:
            if u <= r:
                return False

    total_degree = sum(len(nbrs) for nbrs in adjacency.values())
    if total_degree != 6 * (n - 1) - 2 * r:
        return False

    for v in range(r + 1, n + 1):
        nbrs = adjacency[v]
        d = len(nbrs)
        k = 0
        for j in range(d):
            cur = nbrs[j]
            nxt = nbrs[(j + 1) % d]
            if cur > r and nxt <= r:
                k += 1
                if nbrs[(j + 2) % d] <= r:
                    k += 1
        if k > 2:
            return False

    for i, nbrs_i in adjacency.items():
        d = len(nbrs_i)
        for j in range(d):
            if j == d - 1:
                if i <= r:
                    continue
                a = nbrs_i[0]
            else:
                a = nbrs_i[j + 1]
            k = nbrs_i[j]
            nbrs_k = adjacency[k]
            dk = len(nbrs_k)
            found = any(nbrs_k[p] == a and nbrs_k[(p + 1) % dk] == i for p in range(dk))
            if not found:
                return False

    return True


def random_flip_mutants(
    adjacency: Adjacency, r: int, n: int, rng: random.Random, max_tries: int
) -> list[Adjacency]:
    """Tries up to `max_tries` random flippable edges (without replacement,
    shuffled once), returns every adjacency dict for which flip_edge
    succeeded. Each mutant differs from the input by exactly one edge
    (u,v) -> (a,b); callers apply their own structural-validity gate and
    rule/novelty filters afterward."""
    edges = flippable_edges(adjacency, r)
    rng.shuffle(edges)
    out = []
    for (u, v) in edges[:max_tries]:
        res = flip_edge(adjacency, r, u, v)
        if res is not None:
            out.append(res.adjacency)
    return out
