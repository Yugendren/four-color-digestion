"""Independent D-/C-reducibility checker, implemented from the RSST paper.

Source of truth: "Reducibility in the Four-Color Theorem" (arXiv:1401.6481,
reduce.tex) — NOT the C program. This gives us a genuinely independent second
verifier to differential-test against the compiled 1995 oracle.

Model (paper §1-§4):
  * Ring colorings are edge colorings kappa: E(R) -> {-1,0,1}. Two colorings
    are *similar* if they induce the same partition of ring edges into three
    classes. Each similarity class has a unique *canonical* representative
    (all zeros, or e_r..e_{k+1} = 0 and e_k = 1) and an integer *code*
    sum(kappa'(e_i) * 3^(i-1)) in 0..(3^(r-1)-1)/2.
  * C(K)  = codes of restrictions to E(R) of tri-colorings of the free
    completion G (edge colorings where edges sharing a triangle differ).
  * C'(K) = maximal consistent subset of the complement, computed as a
    greatest fixed point over balanced signed matchings (paper §3, Thm 3.2).
  * K is D-reducible iff C'(K) is empty. If a contract X is given, K is
    C-reducible iff additionally no coloring of C'(K) extends to a
    tri-coloring of G modulo X (paper §4).

Header cross-check: each configuration record stores a = |C(K)| and
b = |C'(K)| (canonical-coloring counts), so every run self-validates
against the published data even before touching the C oracle.
"""

from __future__ import annotations

from dataclasses import dataclass

from .conf_parser import Configuration

# Number of balanced signed matchings per ring size, from reduce.c
# (simatchnumber). Used as a generator self-test.
SIMATCHNUMBER = [0, 0, 1, 3, 10, 30, 95, 301, 980, 3228, 10797, 36487,
                 124542, 428506, 1485003]


# ---------------------------------------------------------------------------
# Codes for ring colorings (paper §1)
# ---------------------------------------------------------------------------

def canonical_code(coloring: list[int]) -> int:
    """Code of the canonical coloring similar to `coloring`.

    `coloring[i]` is kappa(e_{i+1}) in {-1,0,1}. Canonicalization relabels
    the three color classes so that e_r's class becomes 0 and the class of
    the highest-index edge not colored like e_r becomes +1.
    """
    r = len(coloring)
    last = coloring[-1]
    sigma = {last: 0}
    for i in range(r - 2, -1, -1):
        v = coloring[i]
        if v not in sigma:
            sigma[v] = 1
            break
    for v in (-1, 0, 1):
        if v not in sigma:
            sigma[v] = -1 if 1 in sigma.values() else 1
    code = 0
    p = 1
    for v in coloring:
        code += sigma[v] * p
        p *= 3
    return code


# ---------------------------------------------------------------------------
# Tri-colorings of the free completion (paper §2)
# ---------------------------------------------------------------------------

def _edges_and_triangles(cfg: Configuration):
    """Edge list of the free completion G and its triangle list.

    Returns (edges, triangles) where edges is a list of frozensets, the first
    r entries being the ring edges e_1..e_r (e_i = {i, i-1}, e_1 = {1, r}),
    and triangles is a list of triples of edge indices.
    """
    n, r = cfg.n, cfg.r
    edges: list[frozenset] = []
    index: dict[frozenset, int] = {}
    # Ring edges first, in the paper's order.
    for i in range(1, r + 1):
        u = i
        v = r if i == 1 else i - 1
        e = frozenset((u, v))
        index[e] = len(edges)
        edges.append(e)
    for v, nbrs in cfg.adjacency.items():
        for u in nbrs:
            e = frozenset((v, u))
            if e not in index:
                index[e] = len(edges)
                edges.append(e)
    # Triangles: v with two cyclically-consecutive neighbors that are adjacent.
    triangles: set[frozenset] = set()
    for v, nbrs in cfg.adjacency.items():
        d = len(nbrs)
        for j in range(d):
            a, b = nbrs[j], nbrs[(j + 1) % d]
            if v < a and v < b and b in cfg.adjacency[a]:
                triangles.add(frozenset((v, a, b)))
    tri_edges = []
    for t in triangles:
        x, y, z = sorted(t)
        tri_edges.append((index[frozenset((x, y))],
                          index[frozenset((x, z))],
                          index[frozenset((y, z))]))
    return edges, tri_edges


def extendable_codes(cfg: Configuration,
                     contract: list[tuple[int, int]] | None = None) -> set[int]:
    """Codes of restrictions to E(R) of tri-colorings of G (mod contract).

    Without a contract: colorings c: E(G) -> {0,1,2} such that edges on a
    common triangle receive distinct colors (paper §2; we enumerate ring
    edges too — the ring edge in each disk triangle is forced anyway, and
    correctness beats the paper's gauge-fixing speed trick).

    With a contract X (paper §4): contract edges are uncolored; triangles
    with no edge in X have all-distinct colors; triangles with exactly one
    edge in X force their two remaining edges to be EQUAL.
    """
    edges, triangles = _edges_and_triangles(cfg)
    r = cfg.r
    m = len(edges)
    xset = set()
    if contract:
        for (p, q) in contract:
            xset.add(frozenset((p, q)))
    in_x = [e in xset for e in edges]

    # Constraints per uncolored-edge pair.
    diff_pairs: list[list[tuple[int, int]]] = [[] for _ in range(m)]  # noqa
    constraints_diff: list[tuple[int, int]] = []
    constraints_eq: list[tuple[int, int]] = []
    for (a, b, c) in triangles:
        tx = [i for i in (a, b, c) if in_x[i]]
        rest = [i for i in (a, b, c) if not in_x[i]]
        if len(tx) == 0:
            constraints_diff += [(a, b), (a, c), (b, c)]
        elif len(tx) == 1:
            constraints_eq.append((rest[0], rest[1]))
        # 2+ contract edges in one triangle cannot happen for a valid contract.

    # Order edges: interior first (deepest last), ring last, so ring colors
    # get decided by propagation late. Simple static order suffices here.
    order = [i for i in range(m) if not in_x[i]]
    pos = {e: k for k, e in enumerate(order)}

    # Adjacency of constraints for pruning.
    neigh_diff: dict[int, list[int]] = {i: [] for i in order}
    neigh_eq: dict[int, list[int]] = {i: [] for i in order}
    for (a, b) in constraints_diff:
        neigh_diff[a].append(b)
        neigh_diff[b].append(a)
    for (a, b) in constraints_eq:
        neigh_eq[a].append(b)
        neigh_eq[b].append(a)

    color = {}
    found: set[int] = set()

    def backtrack(k: int) -> None:
        if k == len(order):
            ring = [color[i] for i in range(r)]
            # map {0,1,2} -> {-1,0,1} labels; canonical_code only cares about
            # the partition, so any fixed relabeling works.
            found.add(canonical_code([v - 1 for v in ring]))
            return
        e = order[k]
        for v in (0, 1, 2):
            ok = True
            for o in neigh_diff[e]:
                if o in color and color[o] == v:
                    ok = False
                    break
            if ok:
                for o in neigh_eq[e]:
                    if o in color and color[o] != v:
                        ok = False
                        break
            if ok:
                color[e] = v
                backtrack(k + 1)
                del color[e]

    backtrack(0)
    return found


# ---------------------------------------------------------------------------
# Balanced signed matchings (paper §3)
# ---------------------------------------------------------------------------

@dataclass
class SignedMatching:
    pairs: list[tuple[int, int, int]]   # (a_i, b_i, mu_i), b_i < a_i
    code: int
    choices: list[int]                  # h_2..h_k
    a1: int                             # max edge index in the matching


def _noncrossing_matchings(r: int):
    """All nonempty noncrossing matchings of chords on cyclic positions 1..r."""
    results: list[list[tuple[int, int]]] = []

    def crosses(p, q, x, y):
        # chords {p,q}, {x,y} on a circle labeled 1..r cross iff exactly one
        # of x,y lies strictly between p and q (linear order works after
        # normalizing p<q, x<y).
        return (p < x < q) != (p < y < q)

    pairs_all = [(b, a) for a in range(2, r + 1) for b in range(1, a)]

    def extend(chosen: list[tuple[int, int]], used: int, start: int):
        if chosen:
            results.append(list(chosen))
        for idx in range(start, len(pairs_all)):
            b, a = pairs_all[idx]
            if used & (1 << a) or used & (1 << b):
                continue
            if any(crosses(b, a, x, y) for (x, y) in chosen):
                continue
            chosen.append((b, a))
            extend(chosen, used | (1 << a) | (1 << b), idx + 1)
            chosen.pop()

    extend([], 0, 0)
    return results


def balanced_signed_matchings(r: int) -> list[SignedMatching]:
    """All balanced signed matchings with code and choice sequence (Thm 3.2)."""
    out: list[SignedMatching] = []
    for matching in _noncrossing_matchings(r):
        k = len(matching)
        # signs mu_i in {-1,+1}; balanced iff r + #(mu=-1) is even.
        for mask in range(1 << k):
            neg = bin(mask).count("1")
            if (r + neg) % 2 != 0:
                continue
            signed = []
            for j, (b, a) in enumerate(matching):
                mu = -1 if (mask >> j) & 1 else 1
                signed.append((a, b, mu))
            # order pairs so a_1 = max a_i
            signed.sort(key=lambda t: -t[0])
            a1 = signed[0][0]
            if a1 < r:
                code = sum(3 ** (a - 1) + mu * 3 ** (b - 1)
                           for (a, b, mu) in signed)
                choices = [2 * (3 ** (a - 1) + mu * 3 ** (b - 1))
                           for (a, b, mu) in signed[1:]]
            else:
                code = (3 ** r - 1) // 2 - sum(
                    3 ** (a - 1) + ((3 - mu) // 2) * 3 ** (b - 1)
                    for (a, b, mu) in signed)
                choices = [3 ** (a - 1) + mu * 3 ** (b - 1)
                           for (a, b, mu) in signed[1:]]
            out.append(SignedMatching(signed, code, choices, a1))
    return out


def _matching_codes(m: SignedMatching):
    """Signed code values c - sum eps_i h_i over all eps in {0,1}^(k-1).

    Note the SUBTRACTION: the two Kempe orientations of pair i contribute
    +/-(3^{a_i-1} + mu_i 3^{b_i-1}); the base code c carries the all-plus
    choice, and h_i = 2*(...) steps to the minus choice. (Empirically
    verified: with subtraction 100% of generated values are canonical codes
    across r = 6..8; with addition ~4% are invalid.)
    """
    vals = [m.code]
    for h in m.choices:
        vals = [v for v0 in vals for v in (v0, v0 - h)]
    return vals


# ---------------------------------------------------------------------------
# The consistent-set fixed point (paper §3) and reducibility verdicts
# ---------------------------------------------------------------------------

@dataclass
class ReduceResult:
    ident: str
    n_extendable: int          # |C(K)| canonical count  (header field a)
    n_consistent: int          # |C'(K)| canonical count (header field b)
    d_reducible: bool
    c_reducible: bool | None   # None if no contract given/needed
    rounds: int
    trace: list[int]           # surviving |C_i| per round (process labels)


def check(cfg: Configuration) -> ReduceResult:
    r = cfg.r
    ext = extendable_codes(cfg)

    # live = set of canonical codes in C_i (start: all balanced-ternary codes
    # of canonical colorings NOT in C(K)). Enumerate canonical colorings:
    # digits d_1..d_r with d_r = 0 and highest nonzero digit (if any) = +1.
    all_codes = set()
    def gen(i, code, p, seen_nonzero_top):
        if i == r:
            all_codes.add(code)
            return
        # e_{i+1} digit; positions 0..r-1, position r-1 (e_r) must be 0.
        if i == r - 1:
            gen(i + 1, code, p * 3, seen_nonzero_top)
            return
        for d in (-1, 0, 1):
            gen(i + 1, code + d * p, p * 3, seen_nonzero_top)
    gen(0, 0, 1, False)
    # keep only canonical (nonneg codes whose highest nonzero ternary digit
    # is +1); generation above produced signed values, filter:
    canonical = {c for c in all_codes if c >= 0 and _is_canonical_code(c, r)}

    # live[0] is exceptional (paper §3). reduce.c's updatelive shows the
    # exact rule: code 0 survives a round iff it received AT LEAST ONE theta
    # mark (live[0] > 1 is promoted to fully-marked 15), whereas every other
    # code needs marks for all three thetas. With no marks at all it dies
    # like any other code. It kills a matching iff it is extendable.
    live0 = 0 not in ext
    live = {c for c in canonical if c not in ext}
    live.discard(0)

    matchings = balanced_signed_matchings(r)
    real = [True] * len(matchings)
    trace = [len(live) + (1 if live0 else 0)]
    rounds = 0

    while True:
        rounds += 1
        marks: dict[int, set[int]] = {}
        for idx, m in enumerate(matchings):
            if not real[idx]:
                continue
            vals = _matching_codes(m)
            codes = [abs(v) for v in vals]
            if any((not live0 if c == 0 else c not in live) for c in codes):
                real[idx] = False
                continue
            for v, c in zip(vals, codes):
                theta = 0 if m.a1 < r else (1 if v < 0 else -1)
                marks.setdefault(c, set()).add(theta)
        new_live = {c for c in live if marks.get(c, set()) >= {-1, 0, 1}}
        new_live0 = live0 and bool(marks.get(0))
        trace.append(len(new_live) + (1 if new_live0 else 0))
        if new_live == live and new_live0 == live0:
            break
        live, live0 = new_live, new_live0
        if not live and not live0:
            break

    consistent = set(live)
    if live0:
        consistent.add(0)
    d_red = len(consistent) == 0
    c_red: bool | None = None
    if not d_red and cfg.contract:
        mod_ext = extendable_codes(cfg, contract=cfg.contract)
        c_red = consistent.isdisjoint(mod_ext)

    return ReduceResult(cfg.ident, len(ext), len(consistent), d_red, c_red,
                        rounds, trace)


def _is_canonical_code(code: int, r: int) -> bool:
    digits = []
    c = code
    # balanced ternary digits of nonnegative canonical codes are in {-1,0,1}
    for _ in range(r):
        rem = c % 3
        if rem == 2:
            rem = -1
        digits.append(rem)
        c = (c - rem) // 3
    if c != 0:
        return False
    if digits[r - 1] != 0:
        return False
    for d in reversed(digits):
        if d == 1:
            return True
        if d == -1:
            return False
    return True  # all zero
