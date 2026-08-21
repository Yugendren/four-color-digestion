"""A third, deliberately-independent implementation of |C(K)| (the count of
canonical ring-coloring codes extending to a tri-coloring of the free
completion), used only as a tie-breaker when `fourcolor.reduce.check` and
the compiled RSST oracle (`build/reduce_rsst`) disagree on a configuration's
extendable-coloring count.

Why this exists: `tools/fr_table_crosscheck.py`'s RSST cross-verification of
`tools/fr_table.py`'s exhaustive small-ring sweep found that ~10% of the
exhaustively-generated (not hand-curated) below-threshold configurations
make `build/reduce_rsst` abort with "ERROR: DISCREPANCY IN NUMBER OF
EXTENDING COLOURINGS" -- its own recomputed |C(K)| disagrees with the value
`fourcolor.reduce.check` supplies in the header. `fourcolor.reduce.check`
itself was already validated with ZERO mismatches against all 3455
hand-curated RSST+Steinberger catalog configurations' header `a` values
(`results/differential-unavoidable-r14/report.jsonl`,
`results/differential-U_2822-r16/report.jsonl`) -- so before concluding
"the oracle is wrong, not us" (a strong claim about historical,
peer-reviewed 1995 C code), a completely independent third computation is
warranted. This module deliberately shares NO code path with
`fourcolor.reduce`: different edge indexing (sorted vertex pairs, not
insertion order from adjacency traversal), different triangle enumeration
(brute-force over all vertex triples, not "cyclically consecutive
neighbors"), no gauge-fixing (colors all edges, not just m-1 with the first
fixed to a WLOG value), and plain positional DFS order (not the greedy
most-constrained-edge-first heuristic `reduce.extendable_codes` uses for
speed). Two independently-written implementations of the same
mathematical object agreeing is much stronger evidence of correctness than
either one alone -- see `results/theorem/fr_table/THEOREM.md`'s "RSST
oracle count-mismatch investigation" section for the concrete cases this
resolved (all confirmed `fourcolor.reduce.check` correct; the compiled
`reduce.c`'s `strip()` edge-numbering heuristic is the outlier).

Correctness note: this is a naive O(3^m) worst-case backtracking search
(m = number of edges) with only triangle-rainbow pruning, no gauge-fixing
and no smart variable ordering -- deliberately simple over fast. It is only
run on small configurations (interior size below a ring's catalog
threshold, so m is at most a few dozen), where it finishes in well under a
second.
"""

from __future__ import annotations

from .conf_parser import Configuration
from .reduce import canonical_code


def brute_force_extendable_codes(cfg: Configuration) -> set[int]:
    """Independent recomputation of `fourcolor.reduce.extendable_codes(cfg)`
    (no contract support -- this is a tie-breaker for the D-reducibility
    case only). Returns the same mathematical object: canonical codes of
    ring-edge restrictions of tri-colorings of the free completion where
    every triangular face's three edges get three distinct colors."""
    r, n = cfg.r, cfg.n
    adj = cfg.adjacency

    edges = sorted({frozenset((v, u)) for v, nbrs in adj.items() for u in nbrs},
                    key=lambda e: tuple(sorted(e)))
    eidx = {e: i for i, e in enumerate(edges)}
    verts = list(adj.keys())
    triangles: list[tuple[int, int, int]] = []
    for i in range(len(verts)):
        a = verts[i]
        for j in range(i + 1, len(verts)):
            b = verts[j]
            if b not in adj[a]:
                continue
            for k in range(j + 1, len(verts)):
                c = verts[k]
                if c in adj[a] and c in adj[b]:
                    triangles.append((eidx[frozenset((a, b))],
                                       eidx[frozenset((a, c))],
                                       eidx[frozenset((b, c))]))

    ring_edge_idx = []
    for i in range(1, r + 1):
        u = i
        v = r if i == 1 else i - 1
        ring_edge_idx.append(eidx[frozenset((u, v))])

    m = len(edges)
    tri_of_edge: list[list[tuple[int, int, int]]] = [[] for _ in range(m)]
    for t in triangles:
        for e in t:
            tri_of_edge[e].append(t)

    color = [-1] * m
    found: set[int] = set()

    def backtrack(k: int) -> None:
        if k == m:
            ring_colors = [color[ring_edge_idx[i]] - 1 for i in range(r)]
            found.add(canonical_code(ring_colors))
            return
        e = k
        for v in (0, 1, 2):
            ok = True
            for t in tri_of_edge[e]:
                others = [o for o in t if o != e and color[o] != -1]
                if any(color[o] == v for o in others):
                    ok = False
                    break
            if ok:
                color[e] = v
                backtrack(k + 1)
                color[e] = -1

    backtrack(0)
    return found
