"""Arrangement feature library for degree-5 interior vertex clusters --
the extraction-test candidate invariant for the ring-10 boundary result.

Context (see results/d1v2/digestion/cases.md and results/d1v2/replication/
report.md): `control_encoder_summary` (the frozen learned encoder's
mean-pool summary, linear-probed) beats `shallow_plus_structural` (hand-
computed COUNT features -- n_deg5_interior, n_deg5_total, n_triangles_deg5,
n_diamonds_deg5, ring-run lengths, extendable-coloring ratio; see
`fourcolor.d1_interp.structural_candidates`) on exactly 4 boundary
configs (`encoder_right_struct_wrong` in cases.md), even though those 4
configs' COUNT features are not dramatically different from the rest of
the boundary population's means. Hypothesis under test: the encoder's
edge lies in the ARRANGEMENT of degree-5 vertices (how they cluster
together, how close to the ring, how they chain into paths/diamonds) --
information the count features discard by summing over the whole graph.

H5 := the subgraph induced on INTERIOR (v > r) vertices of degree exactly
5, with an edge (u, v) iff u and v are adjacent in the full graph G. Every
feature below is a cheap (O(n) to O(n^2) on graphs with ~10-20 vertices)
deterministic function of one record's (adjacency, r, n) -- rotation/
reflection invariant by construction, exactly like
`fourcolor.d1_interp.structural_candidates` (no canonicalization needed:
these are set/graph-theoretic quantities, not token-position-dependent).

Kept as a separate module (rather than folded into `fourcolor.d1_interp`,
which already owns SHALLOW_FEATURE_NAMES/STRUCTURAL_FEATURE_NAMES and is
exercised by tests/test_d1_interp.py + tools/d1v2_interrogate.py) so this
extraction test's new feature set is additive: callers that want the
augmented probe just concatenate `arrangement_feature_vector` onto
`d1v2_interrogate.shallow_plus_structural_vector`'s output, and nothing
in d1_interp.py or d1v2_interrogate.py needs to change (their existing
tests keep passing unmodified).
"""

from __future__ import annotations

from collections import deque

ARRANGEMENT_FEATURE_NAMES: list[str] = [
    "h5_n_components",
    "h5_largest_component_size",
    "h5_n_isolated_vertices",
    "h5_edge_count",
    "h5_density",
    "h5_max_degree",
    "h5_has_path_len3",
    "h5_n_adjacent_to_ring",
    "h5_component_ring_dist_min",
    "h5_component_ring_dist_mean",
    "h5_intercomponent_dist_min",
    "h5_intercomponent_dist_mean",
    "n_deg5_ge3_deg5_neighbors",
    "h5_has_diamond",
]


# ---------------------------------------------------------------------------
# Small graph-theoretic helpers, all operating on plain adjacency dicts
# (no networkx dependency, matching fourcolor.d1_interp's from-scratch
# style for structural_candidates).
# ---------------------------------------------------------------------------


def _degree_map(adjacency: dict[int, list[int]]) -> dict[int, int]:
    return {v: len(nbrs) for v, nbrs in adjacency.items()}


def _deg5_interior(adjacency: dict[int, list[int]], r: int, n: int) -> set[int]:
    degrees = _degree_map(adjacency)
    return {v for v in range(r + 1, n + 1) if degrees.get(v) == 5}


def _components(h5_adj: dict[int, list[int]]) -> list[list[int]]:
    """Connected components of the graph given by h5_adj (a dict mapping
    every H5 vertex to its H5-neighbors -- i.e. already restricted to
    edges within the degree-5-interior vertex set)."""
    seen: set[int] = set()
    comps: list[list[int]] = []
    for start in h5_adj:
        if start in seen:
            continue
        comp: list[int] = []
        stack = [start]
        seen.add(start)
        while stack:
            u = stack.pop()
            comp.append(u)
            for w in h5_adj[u]:
                if w not in seen:
                    seen.add(w)
                    stack.append(w)
        comps.append(comp)
    return comps


def _bfs_from(adjacency: dict[int, list[int]], source: int) -> dict[int, int]:
    """Single-source BFS distances over the FULL graph (not H5)."""
    dist = {source: 0}
    dq = deque([source])
    while dq:
        u = dq.popleft()
        for w in adjacency[u]:
            if w not in dist:
                dist[w] = dist[u] + 1
                dq.append(w)
    return dist


def _has_path_of_length(adj: dict[int, list[int]], min_edges: int) -> bool:
    """True iff `adj` (a small graph, restricted to one H5 component)
    contains a simple path with >= min_edges edges (i.e. >= min_edges + 1
    distinct vertices). Exhaustive DFS with backtracking -- fine at the
    scale of one H5 component (a handful of degree-5 interior vertices)."""

    def dfs(current: int, visited: set[int], depth: int) -> bool:
        if depth >= min_edges:
            return True
        for nxt in adj[current]:
            if nxt not in visited:
                visited.add(nxt)
                if dfs(nxt, visited, depth + 1):
                    return True
                visited.discard(nxt)
        return False

    for start in adj:
        if dfs(start, {start}, 0):
            return True
    return False


def _has_k4_minus_edge(adj: dict[int, list[int]]) -> bool:
    """True iff `adj` (restricted to one H5 component) contains a diamond
    (K4 minus one edge): two triangles sharing an edge, i.e. some edge
    (u, v) with >= 2 common neighbors within the component."""
    for u, nbrs in adj.items():
        for v in nbrs:
            if v <= u:
                continue
            common = [w for w in adj[u] if w in adj[v]]
            if len(common) >= 2:
                return True
    return False


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------


def arrangement_features(adjacency: dict[int, list[int]], r: int, n: int) -> dict[str, float]:
    """The arrangement feature library, per ARRANGEMENT_FEATURE_NAMES.

    All H5-component features are 0.0 sentinels when there are too few
    components/vertices for the quantity to be defined (e.g. an empty H5,
    or a single component -> no inter-component distances) -- documented
    here rather than silently NaN, since bootstrap-CI probe pipelines need
    finite floats.
    """
    degrees = _degree_map(adjacency)
    deg5_interior = _deg5_interior(adjacency, r, n)
    deg5_all = {v for v, d in degrees.items() if d == 5}

    h5_adj = {v: [u for u in adjacency[v] if u in deg5_interior] for v in deg5_interior}
    components = _components(h5_adj)

    n_components = len(components)
    comp_sizes = [len(c) for c in components]
    largest_component_size = max(comp_sizes) if comp_sizes else 0
    n_isolated = sum(1 for c in components if len(c) == 1)
    edge_count = sum(len(nbrs) for nbrs in h5_adj.values()) // 2
    n_h5 = len(deg5_interior)
    max_pairs = n_h5 * (n_h5 - 1) // 2
    density = edge_count / max_pairs if max_pairs > 0 else 0.0
    max_degree = max((len(nbrs) for nbrs in h5_adj.values()), default=0)

    has_path_len3 = any(
        _has_path_of_length({v: h5_adj[v] for v in c}, 3) for c in components if len(c) >= 4
    )

    n_adjacent_to_ring = sum(1 for v in deg5_interior if any(u <= r for u in adjacency[v]))

    # Full-graph BFS from every H5 vertex, reused for both the
    # ring-distance and inter-component-distance features.
    pairwise = {v: _bfs_from(adjacency, v) for v in deg5_interior}
    ring_vertices = range(1, r + 1)

    def ring_dist(v: int) -> int | None:
        dists = [pairwise[v][rv] for rv in ring_vertices if rv in pairwise[v]]
        return min(dists) if dists else None

    comp_ring_dists = []
    for c in components:
        vals = [d for d in (ring_dist(v) for v in c) if d is not None]
        if vals:
            comp_ring_dists.append(min(vals))
    comp_ring_dist_min = float(min(comp_ring_dists)) if comp_ring_dists else 0.0
    comp_ring_dist_mean = float(sum(comp_ring_dists) / len(comp_ring_dists)) if comp_ring_dists else 0.0

    intercomp_dists = []
    for i in range(len(components)):
        for j in range(i + 1, len(components)):
            best = None
            for u in components[i]:
                for v in components[j]:
                    d = pairwise[u].get(v)
                    if d is not None and (best is None or d < best):
                        best = d
            if best is not None:
                intercomp_dists.append(best)
    intercomp_dist_min = float(min(intercomp_dists)) if intercomp_dists else 0.0
    intercomp_dist_mean = float(sum(intercomp_dists) / len(intercomp_dists)) if intercomp_dists else 0.0

    n_deg5_ge3_deg5_neighbors = sum(
        1 for v in deg5_all if sum(1 for u in adjacency[v] if u in deg5_all) >= 3
    )

    has_diamond = any(_has_k4_minus_edge({v: h5_adj[v] for v in c}) for c in components if len(c) >= 4)

    return {
        "h5_n_components": float(n_components),
        "h5_largest_component_size": float(largest_component_size),
        "h5_n_isolated_vertices": float(n_isolated),
        "h5_edge_count": float(edge_count),
        "h5_density": float(density),
        "h5_max_degree": float(max_degree),
        "h5_has_path_len3": float(has_path_len3),
        "h5_n_adjacent_to_ring": float(n_adjacent_to_ring),
        "h5_component_ring_dist_min": comp_ring_dist_min,
        "h5_component_ring_dist_mean": comp_ring_dist_mean,
        "h5_intercomponent_dist_min": intercomp_dist_min,
        "h5_intercomponent_dist_mean": intercomp_dist_mean,
        "n_deg5_ge3_deg5_neighbors": float(n_deg5_ge3_deg5_neighbors),
        "h5_has_diamond": float(has_diamond),
    }


def arrangement_feature_vector(adjacency: dict[int, list[int]], r: int, n: int) -> list[float]:
    feats = arrangement_features(adjacency, r, n)
    return [feats[name] for name in ARRANGEMENT_FEATURE_NAMES]
