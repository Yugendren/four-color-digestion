"""Canonical labeling for configurations with a marked ring boundary.

Every configuration in this project (RSST/Steinberger .conf format, nl4ct
.conf format, and our own plantri-derived generator) already follows the
same numbering *convention*: ring vertices are 1..r in cyclic order
(condition a_{i,1} = i+1, a_{i,d_i} = i-1), interior vertices are r+1..n.
But that convention leaves two degrees of freedom unconstrained, and
different sources exercise them differently:

  1. which ring vertex is labeled "1" (r choices — a rotation of the ring
     numbering), and
  2. which cyclic direction is "clockwise" (2 choices — a reflection).

Interior-vertex numbering is *not* independently free once (1) and (2) are
fixed: given a starting ring labeling and direction, a deterministic
breadth-first traversal that (a) visits ring vertices 1..r in order and
(b) at each dequeued vertex walks its rotation list in a fixed direction,
discovering new (unlabeled) vertices in the order encountered, assigns
every interior vertex a unique next-available label with no remaining
choices. So the *only* symmetry group acting on a given rotation-system
embedding with a distinguished boundary cycle is the dihedral group of
the ring, order 2r.

`canonical_key` tries all 2r members of that group, relabels the whole
graph under each, serializes each relabeling to a string, and returns the
lexicographically smallest string as the canonical form. Two adjacency
dicts describing the same configuration (same embedding, same ring, up to
this dihedral symmetry) produce identical canonical keys regardless of
which source's numbering convention produced them.

Known limitation (v1, documented honestly): this is a canonical form for
the restricted symmetry group above (ring rotation + reflection), not a
full graph-isomorphism solver. It will *not* identify two configurations
as identical if they differ by, e.g., a non-boundary automorphism that
permutes interior vertices without touching the ring, or by a boundary
walk that isn't a rigid rotation/reflection of the drawn ring (shouldn't
occur for configurations sharing the same abstract map, but is not
independently proven here). For the corpus-assembly use case (deduping
across sources that all use the same ring-boundary convention) this is
the dominant and essentially only source of duplicate numbering, so the
practical false-negative rate (missed duplicates) should be low; it is a
v1 simplification, not a claim of exactness.
"""

from __future__ import annotations

from collections import deque


def canonical_key(adjacency: dict[int, list[int]], r: int, n: int) -> str:
    """Smallest-string canonical form over the ring's dihedral symmetry."""
    best: str | None = None
    for start in range(1, r + 1):
        for direction in (1, -1):
            s = _relabel_and_serialize(adjacency, r, n, start, direction)
            if best is None or s < best:
                best = s
    assert best is not None
    return best


def canonical_labeling(
    adjacency: dict[int, list[int]], r: int, n: int
) -> tuple[dict[int, int], int, int]:
    """Return (old_label -> new_label map, start, direction) achieving the
    lexicographically-smallest serialization (see `canonical_key`)."""
    best_str: str | None = None
    best_label: dict[int, int] | None = None
    best_meta = (1, 1)
    for start in range(1, r + 1):
        for direction in (1, -1):
            label = _relabel(adjacency, r, n, start, direction)
            s = _serialize(adjacency, label, n, direction)
            if best_str is None or s < best_str:
                best_str = s
                best_label = label
                best_meta = (start, direction)
    assert best_label is not None
    return best_label, best_meta[0], best_meta[1]


def _relabel(
    adjacency: dict[int, list[int]], r: int, n: int, start: int, direction: int
) -> dict[int, int]:
    label: dict[int, int] = {}
    for v in range(1, r + 1):
        label[v] = ((direction * (v - start)) % r) + 1

    visited = set(range(1, r + 1))
    dq: deque[int] = deque(sorted(range(1, r + 1), key=lambda v: label[v]))
    next_label = r + 1
    while dq:
        v = dq.popleft()
        nbrs = adjacency[v]
        if direction == -1:
            nbrs = list(reversed(nbrs))
        for u in nbrs:
            if u not in visited:
                visited.add(u)
                label[u] = next_label
                next_label += 1
                dq.append(u)
    if len(visited) != n:
        raise ValueError(
            f"canonical BFS reached {len(visited)}/{n} vertices "
            "(disconnected interior or malformed adjacency)"
        )
    return label


def _serialize(
    adjacency: dict[int, list[int]], label: dict[int, int], n: int, direction: int
) -> str:
    parts = []
    inv = {new: old for old, new in label.items()}
    for new_v in range(1, n + 1):
        old_v = inv[new_v]
        nbrs = adjacency[old_v]
        if direction == -1:
            nbrs = list(reversed(nbrs))
        new_nbrs = [label[u] for u in nbrs]
        # Rotate the cyclic neighbor list to start at its smallest new label
        # (the only remaining per-vertex degree of freedom: where a cyclic
        # rotation list "starts" is not otherwise meaningful).
        if new_nbrs:
            k = new_nbrs.index(min(new_nbrs))
            new_nbrs = new_nbrs[k:] + new_nbrs[:k]
        parts.append(f"{new_v}:{len(new_nbrs)}:" + ",".join(map(str, new_nbrs)))
    return "|".join(parts)


def _relabel_and_serialize(
    adjacency: dict[int, list[int]], r: int, n: int, start: int, direction: int
) -> str:
    label = _relabel(adjacency, r, n, start, direction)
    return _serialize(adjacency, label, n, direction)
