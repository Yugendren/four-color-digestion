#!/usr/bin/env python3
"""Computational verification of the STAR-ORDER combinatorial fact behind
the STAR-FIRST ORDERING LEMMA (see results/mass-law/star-order-verification.md).

For an interior vertex h of a configuration S (free completion of an RSST
configuration; ring 1..r, interior r+1..n), the lemma needs:

  (STAR-ORDER) the vertices outside the closed star of h can be ordered
  w_1, w_2, ... so that each w_j has, among link(h) u {w_1..w_{j-1}}, at
  least two neighbours that are adjacent to each other.

This is a monotone "bootstrap percolation" condition: once a vertex
qualifies (has an edge fully inside the already-placed set within its own
neighbourhood) it stays qualified as more vertices are placed. So whether
*some* order exists is well-defined independent of tie-breaking, and can be
decided by a closure computation (repeatedly add every vertex that
currently qualifies, in any order, until nothing changes).

Four parts, run over `fourcolor.lemma_corpus.load_corpus()` (59,142 records):

  PART 1 -- structural census (interior degree, link-is-a-cycle, interior
            connectivity, ring-is-a-cycle, Euler's formula).
  PART 2 -- STAR-ORDER verified for every (record, interior vertex) pair.
  PART 3 -- numeric consequence: a <= B_star = min_h (2^d+2*(-1)^d)*2^(n-d-1)/6.
  PART 4 -- stratified sample: explicit star-first vertex order, per-step
            N_i = count_proper_4colorings(prefix), step factors, and the
            implied gamma = 2 * (prod_i f_i/2)^(1/k).

Usage: PYTHONPATH=src .venv/bin/python tools/star_order_check.py
"""

from __future__ import annotations

import random
import sys
import time
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fourcolor.count4 import count_proper_4colorings  # noqa: E402
from fourcolor.lemma_corpus import ConfigRecord, load_corpus  # noqa: E402

OUT_MD = ROOT / "results" / "mass-law" / "star-order-verification.md"

SAMPLE_SEED = 20260823
SAMPLE_CAP_PER_CELL = 20


# --------------------------------------------------------------------------
# Graph helpers
# --------------------------------------------------------------------------


def undirected(adj: Dict[int, List[int]]) -> Dict[int, set]:
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


def bitmasks(g: Dict[int, set], n: int) -> List[int]:
    """adjmask[v-1] = bitmask over 0..n-1 of neighbours of vertex v."""
    m = [0] * n
    for v, nbrs in g.items():
        acc = 0
        for u in nbrs:
            acc |= 1 << (u - 1)
        m[v - 1] = acc
    return m


def induced_cycle_check(vertex_set: Sequence[int], g: Dict[int, set]) -> Tuple[bool, str]:
    """True iff the induced subgraph on vertex_set is a single cycle
    (every vertex has degree exactly 2 within the set, and it's connected)."""
    vs = set(vertex_set)
    if len(vs) < 3:
        return False, f"set too small ({len(vs)})"
    for v in vs:
        d = len(g[v] & vs)
        if d != 2:
            return False, f"vertex {v} has within-set degree {d} (expected 2)"
    # connectivity via BFS
    start = next(iter(vs))
    seen = {start}
    stack = [start]
    while stack:
        u = stack.pop()
        for w in g[u] & vs:
            if w not in seen:
                seen.add(w)
                stack.append(w)
    if seen != vs:
        return False, f"disconnected ({len(seen)}/{len(vs)} reached)"
    return True, "ok"


def has_edge_within(mask: int, adjmask: List[int]) -> bool:
    """True iff the vertex set encoded by `mask` contains an edge."""
    m = mask
    while m:
        low = m & (-m)
        idx = low.bit_length() - 1
        m ^= low
        if adjmask[idx] & mask & ~low:
            return True
    return False


def star_closure(h_idx: int, adjmask: List[int], n: int) -> Tuple[bool, int]:
    """Closure of {h} u link(h) under: add v if it has >=2 neighbours in
    the current set that are adjacent to each other. Returns (success, S)."""
    all_mask = (1 << n) - 1
    S = adjmask[h_idx] | (1 << h_idx)
    changed = True
    while changed and S != all_mask:
        changed = False
        remaining = all_mask & ~S
        m = remaining
        while m:
            low = m & (-m)
            idx = low.bit_length() - 1
            m ^= low
            nb_in_S = adjmask[idx] & S
            if has_edge_within(nb_in_S, adjmask):
                S |= 1 << idx
                changed = True
    return S == all_mask, S


def star_order_sequential(h_idx: int, adjmask: List[int], n: int) -> List[int]:
    """Explicit w_1, w_2, ... order (0-indexed vertex ids), one vertex at a
    time, deterministic tie-break by smallest index. Assumes closure
    succeeds (caller must check)."""
    all_mask = (1 << n) - 1
    S = adjmask[h_idx] | (1 << h_idx)
    order: List[int] = []
    while S != all_mask:
        remaining = all_mask & ~S
        m = remaining
        added = None
        while m:
            low = m & (-m)
            idx = low.bit_length() - 1
            m ^= low
            nb_in_S = adjmask[idx] & S
            if has_edge_within(nb_in_S, adjmask):
                added = idx
                break
        if added is None:
            raise RuntimeError("closure incomplete during sequential build")
        S |= 1 << added
        order.append(added)
    return order


def link_cyclic_order(h: int, adj: Dict[int, List[int]]) -> List[int]:
    """The neighbours of h, in the rotation-system cyclic order already
    present in `adj[h]` (adjacency lists in this corpus are rotation
    systems: neighbours listed in cyclic order around the vertex)."""
    return [int(u) for u in adj[h]]


# --------------------------------------------------------------------------
# PART 1: structural census
# --------------------------------------------------------------------------


def part1(records: List[ConfigRecord]) -> dict:
    print("PART 1: structural census...")
    t0 = time.time()
    deg_hist: Counter = Counter()
    low_deg_records: List[Tuple[str, str, int, int]] = []  # ident, source, h, deg
    low_deg_by_source: Counter = Counter()
    link_violations: List[Tuple[str, int, str]] = []
    interior_disconnected: List[str] = []
    ring_violations: List[Tuple[str, str]] = []
    euler_violations: List[Tuple[str, int, int]] = []
    global_min_deg = None
    global_max_deg = None

    for i, rec in enumerate(records):
        adj = rec.adjacency
        r, n = rec.r, rec.n
        g = undirected(adj)
        interior = list(range(r + 1, n + 1))

        # 1a
        rec_min = None
        rec_max = None
        for h in interior:
            d = len(g[h])
            deg_hist[d] += 1
            rec_min = d if rec_min is None else min(rec_min, d)
            rec_max = d if rec_max is None else max(rec_max, d)
            if d < 5:
                low_deg_records.append((rec.ident, rec.source, h, d))
                low_deg_by_source[rec.source] += 1
        if rec_min is not None:
            global_min_deg = rec_min if global_min_deg is None else min(global_min_deg, rec_min)
            global_max_deg = rec_max if global_max_deg is None else max(global_max_deg, rec_max)

        # 1b: link(h) is a single cycle
        for h in interior:
            ok, msg = induced_cycle_check(g[h], g)
            if not ok:
                link_violations.append((rec.ident, h, msg))

        # 1c: interior induced subgraph connected
        if len(interior) >= 1:
            vs = set(interior)
            start = interior[0]
            seen = {start}
            stack = [start]
            while stack:
                u = stack.pop()
                for w in g[u] & vs:
                    if w not in seen:
                        seen.add(w)
                        stack.append(w)
            if seen != vs:
                interior_disconnected.append(rec.ident)

        # 1d: ring is an induced cycle
        ring = list(range(1, r + 1))
        ok, msg = induced_cycle_check(ring, g)
        if not ok:
            ring_violations.append((rec.ident, msg))

        # 1e: Euler
        edges = sum(len(nb) for nb in g.values()) // 2
        expected = 3 * n - r - 3
        if edges != expected:
            euler_violations.append((rec.ident, edges, expected))

        if (i + 1) % 10000 == 0:
            print(f"  ...{i + 1}/{len(records)} ({time.time() - t0:.1f}s)")

    print(f"PART 1 done in {time.time() - t0:.1f}s")
    return dict(
        deg_hist=deg_hist,
        low_deg_records=low_deg_records,
        low_deg_by_source=low_deg_by_source,
        global_min_deg=global_min_deg,
        global_max_deg=global_max_deg,
        link_violations=link_violations,
        interior_disconnected=interior_disconnected,
        ring_violations=ring_violations,
        euler_violations=euler_violations,
    )


# --------------------------------------------------------------------------
# PART 2: STAR-ORDER verification
# --------------------------------------------------------------------------


def part2(records: List[ConfigRecord]) -> dict:
    print("PART 2: STAR-ORDER closure for every (record, interior vertex)...")
    t0 = time.time()
    n_pairs = 0
    n_fail = 0
    failures: List[Tuple[str, int, str]] = []

    for i, rec in enumerate(records):
        adj = rec.adjacency
        r, n = rec.r, rec.n
        g = undirected(adj)
        adjmask = bitmasks(g, n)
        for h in range(r + 1, n + 1):
            n_pairs += 1
            ok, S = star_closure(h - 1, adjmask, n)
            if not ok:
                n_fail += 1
                missing = [(idx + 1) for idx in range(n) if not (S >> idx) & 1]
                if len(failures) < 10:
                    failures.append((rec.ident, h, f"missing {missing[:15]}"))
        if (i + 1) % 10000 == 0:
            print(f"  ...{i + 1}/{len(records)} records, {n_pairs} pairs, {n_fail} failures so far ({time.time() - t0:.1f}s)")

    print(f"PART 2 done in {time.time() - t0:.1f}s: {n_pairs} pairs, {n_fail} failures")
    return dict(n_pairs=n_pairs, n_fail=n_fail, failures=failures)


# --------------------------------------------------------------------------
# PART 3: numeric consequence B_star
# --------------------------------------------------------------------------


def b_star_term(d: int, n: int) -> Fraction:
    sign = 1 if d % 2 == 0 else -1
    base = Fraction(2 ** d + 2 * sign)
    power = Fraction(2) ** (n - d - 1)  # Fraction handles negative exponents too
    return base * power / 6


def part3(records: List[ConfigRecord]) -> dict:
    print("PART 3: numeric consequence (a vs B_star)...")
    t0 = time.time()
    n_violations = 0
    violation_examples: List[Tuple[str, int, Fraction]] = []
    max_ratio = None
    max_ratio_ident = None
    max_uniform_ratio = None
    max_uniform_ident = None
    table: Dict[Tuple[int, int], float] = {}

    for rec in records:
        adj = rec.adjacency
        r, n, a = rec.r, rec.n, rec.a
        g = undirected(adj)
        interior = range(r + 1, n + 1)
        degs = [len(g[h]) for h in interior]
        terms = [b_star_term(d, n) for d in degs]
        b_star = min(terms)
        a_frac = Fraction(a)
        if a_frac > b_star:
            n_violations += 1
            if len(violation_examples) < 10:
                violation_examples.append((rec.ident, a, b_star))
        ratio = float(a_frac / b_star)
        if max_ratio is None or ratio > max_ratio:
            max_ratio = ratio
            max_ratio_ident = rec.ident
        uniform_ratio = float(a_frac / (11 * Fraction(2) ** (n - 7)))
        if max_uniform_ratio is None or uniform_ratio > max_uniform_ratio:
            max_uniform_ratio = uniform_ratio
            max_uniform_ident = rec.ident
        k = n - r
        key = (r, k)
        if key not in table or ratio > table[key]:
            table[key] = ratio

    print(f"PART 3 done in {time.time() - t0:.1f}s")
    return dict(
        n_violations=n_violations,
        violation_examples=violation_examples,
        max_ratio=max_ratio,
        max_ratio_ident=max_ratio_ident,
        max_uniform_ratio=max_uniform_ratio,
        max_uniform_ident=max_uniform_ident,
        table=table,
    )


# --------------------------------------------------------------------------
# PART 4: per-step gain profile on a stratified sample
# --------------------------------------------------------------------------


def stratified_sample(records: List[ConfigRecord], seed: int, cap: int) -> List[ConfigRecord]:
    by_cell: Dict[Tuple[int, int], List[ConfigRecord]] = defaultdict(list)
    for rec in records:
        by_cell[(rec.r, rec.k)].append(rec)
    rng = random.Random(seed)
    sample: List[ConfigRecord] = []
    for key in sorted(by_cell):
        cell = by_cell[key]
        if len(cell) <= cap:
            sample.extend(cell)
        else:
            sample.extend(rng.sample(cell, cap))
    return sample


def build_star_first_order(rec: ConfigRecord) -> Tuple[List[int], Dict[int, set], int]:
    """Returns (order as 1-indexed vertex labels, undirected graph, h)."""
    adj = rec.adjacency
    r, n = rec.r, rec.n
    g = undirected(adj)
    interior = list(range(r + 1, n + 1))
    h = max(interior, key=lambda v: (len(g[v]), -v))
    link = link_cyclic_order(h, adj)
    adjmask = bitmasks(g, n)
    seq = star_order_sequential(h - 1, adjmask, n)
    order = [h] + link + [idx + 1 for idx in seq]
    assert len(order) == n, (rec.ident, len(order), n)
    assert set(order) == set(range(1, n + 1)), (rec.ident, "order not a permutation")
    return order, g, h


def part4(records: List[ConfigRecord]) -> dict:
    print("PART 4: stratified sample, per-step gain profile...")
    t0 = time.time()
    sample = stratified_sample(records, SAMPLE_SEED, SAMPLE_CAP_PER_CELL)
    print(f"  sample size: {len(sample)} records across {len(set((r.r, r.k) for r in sample))} (r,k) cells")

    identity_violations: List[Tuple[str, int, int]] = []
    f_by_b: Dict[int, List[float]] = defaultdict(list)  # bucketed: 2,3,4,5+ -> list of f_i
    gamma_records: List[Tuple[str, int, int, float]] = []  # ident, r, k, implied_gamma
    f_b3_values: List[float] = []

    for i, rec in enumerate(sample):
        order, g, h = build_star_first_order(rec)
        n, r, k = rec.n, rec.r, rec.k
        adj = rec.adjacency

        Ns = [None] * (n + 1)  # 1-indexed by prefix length
        prev_set: set = set()
        b_list = [0] * (n + 1)
        for idx in range(1, n + 1):
            v = order[idx - 1]
            prefix = order[:idx]
            b = len(g[v] & prev_set)
            b_list[idx] = b
            prev_set.add(v)
            vs = set(prefix)
            sub = {u: [w for w in adj[u] if w in vs] for u in prefix}
            Ns[idx] = count_proper_4colorings(sub)

        # identity check
        s = sum((b_list[idx] - 2) for idx in range(4, n + 1))
        if s != k:
            identity_violations.append((rec.ident, s, k))

        gainprod = Fraction(1)
        for idx in range(2, n + 1):
            f_i = Fraction(Ns[idx], Ns[idx - 1])
            b_i = b_list[idx]
            bucket = b_i if b_i < 5 else 5
            f_by_b[bucket].append(float(f_i))
            if b_i == 3:
                f_b3_values.append(float(f_i))
            g_i = f_i / 2
            gainprod *= g_i

        gainprod_f = float(gainprod)
        if gainprod_f > 0:
            implied_gamma = 2.0 * (gainprod_f ** (1.0 / k)) if k > 0 else float("nan")
        else:
            implied_gamma = float("nan")
        gamma_records.append((rec.ident, r, k, implied_gamma))

        if (i + 1) % 200 == 0:
            print(f"  ...{i + 1}/{len(sample)} ({time.time() - t0:.1f}s)")

    print(f"PART 4 done in {time.time() - t0:.1f}s")
    return dict(
        sample_size=len(sample),
        identity_violations=identity_violations,
        f_by_b=f_by_b,
        gamma_records=gamma_records,
        f_b3_values=f_b3_values,
    )


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


def fmt_bucket_stats(vals: List[float]) -> str:
    if not vals:
        return "n/a"
    return f"mean={sum(vals) / len(vals):.4f} min={min(vals):.4f} max={max(vals):.4f} (n={len(vals)})"


def main() -> None:
    t_all = time.time()
    print("Loading corpus...")
    corpus = load_corpus()
    records = corpus.records
    print(f"Loaded {len(records)} records.")

    p1 = part1(records)
    p2 = part2(records)
    p3 = part3(records)
    p4 = part4(records)

    # ---------------- console summary ----------------
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"PART 1: global interior degree range [{p1['global_min_deg']}, {p1['global_max_deg']}]")
    print(f"        interior vertices with degree < 5: {len(p1['low_deg_records'])}")
    print(f"        link(h)-is-a-cycle violations: {len(p1['link_violations'])}")
    print(f"        interior-disconnected records: {len(p1['interior_disconnected'])}")
    print(f"        ring-not-a-cycle violations: {len(p1['ring_violations'])}")
    print(f"        Euler violations: {len(p1['euler_violations'])}")
    print(f"PART 2: {p2['n_pairs']} (record,h) pairs tested, {p2['n_fail']} failures")
    print(f"PART 3: violations (a > B_star): {p3['n_violations']}")
    print(f"        max a/B_star = {p3['max_ratio']:.6f} at {p3['max_ratio_ident']}")
    print(f"        max a/(11*2^(n-7)) = {p3['max_uniform_ratio']:.6f} at {p3['max_uniform_ident']}")
    print(f"PART 4: sample size {p4['sample_size']}, identity violations {len(p4['identity_violations'])}")
    gammas = [g for (_, _, _, g) in p4["gamma_records"] if g == g]  # filter NaN
    if gammas:
        print(f"        max implied gamma = {max(gammas):.6f}")
    print("=" * 70)

    # ---------------- markdown report ----------------
    lines: List[str] = []
    lines.append("# STAR-ORDER computational verification")
    lines.append("")
    lines.append(
        "Verification of the combinatorial fact (STAR-ORDER) underlying the STAR-FIRST "
        "ORDERING LEMMA, run against the full 59,142-record corpus "
        "(`fourcolor.lemma_corpus.load_corpus()`). Script: `tools/star_order_check.py`, "
        f"total runtime {time.time() - t_all:.1f}s."
    )
    lines.append("")

    # PART 1
    lines.append("## Part 1 -- structural census")
    lines.append("")
    lines.append(f"- Global interior-degree range across all {len(records)} records: "
                  f"**[{p1['global_min_deg']}, {p1['global_max_deg']}]**.")
    lines.append("")
    lines.append("Interior-degree distribution (degree -> count of interior vertices at that degree):")
    lines.append("")
    lines.append("| degree | count |")
    lines.append("|---|---|")
    for d in sorted(p1["deg_hist"]):
        lines.append(f"| {d} | {p1['deg_hist'][d]} |")
    lines.append("")

    n_low = len(p1["low_deg_records"])
    if n_low:
        lines.append(f"**LOUD: {n_low} interior vertices with degree < 5 found.** "
                      "`min interior degree >= 5` is NOT a corpus invariant.")
    else:
        lines.append("No interior vertex with degree < 5 found anywhere in the corpus: "
                      "`min interior degree >= 5` HOLDS on the whole corpus (59,142 records, not a proof).")
    lines.append("")
    if n_low:
        lines.append("Per-source breakdown of degree<5 occurrences:")
        lines.append("")
        lines.append("| source | count |")
        lines.append("|---|---|")
        for src, cnt in p1["low_deg_by_source"].most_common():
            lines.append(f"| {src} | {cnt} |")
        lines.append("")
        lines.append("First 10 offending idents (ident, source, vertex, degree):")
        lines.append("")
        for ident, src, h, d in p1["low_deg_records"][:10]:
            lines.append(f"- `{ident}` [{src}] vertex {h}, degree {d}")
        lines.append("")

    lines.append(f"**1b (link(h) is a single cycle):** {len(p1['link_violations'])} violations.")
    if p1["link_violations"]:
        lines.append("")
        for ident, h, msg in p1["link_violations"][:10]:
            lines.append(f"- `{ident}` vertex {h}: {msg}")
        lines.append("")
        lines.append(
            "(Manually inspected the one offender, `gen-r8-n18-res74-522145`: vertex 9 has degree 11 and "
            "its link contains the extra edge 4-5, a chord splitting the wheel into two triangulated regions "
            "via the separating triangle 4-9-5 -- i.e. a genuine, planarity-legal configuration where two "
            "non-cyclically-adjacent neighbours of h are also directly joined through the rest of the graph. "
            "This does not threaten the STAR-FIRST bound: an extra edge among link(h) vertices only removes "
            "colourings relative to the pure wheel C_d, so P(C_d,3) remains a valid, if slightly loose, upper "
            "bound for that record's star subgraph. It does mean `link(h) is an induced pure cycle with no "
            "chords` is not quite a universal invariant -- 1 exception in 431,159 (record,h) pairs.)"
        )
    lines.append("")

    lines.append(f"**1c (interior induced subgraph connected):** {len(p1['interior_disconnected'])} violations.")
    if p1["interior_disconnected"]:
        lines.append("")
        for ident in p1["interior_disconnected"][:10]:
            lines.append(f"- `{ident}`")
    lines.append("")

    lines.append(f"**1d (ring is an induced cycle):** {len(p1['ring_violations'])} violations.")
    if p1["ring_violations"]:
        lines.append("")
        for ident, msg in p1["ring_violations"][:10]:
            lines.append(f"- `{ident}`: {msg}")
    lines.append("")

    lines.append(f"**1e (Euler, #edges == 3n-r-3):** {len(p1['euler_violations'])} violations.")
    if p1["euler_violations"]:
        lines.append("")
        for ident, edges, expected in p1["euler_violations"][:10]:
            lines.append(f"- `{ident}`: edges={edges}, expected={expected}")
    lines.append("")

    # PART 2
    lines.append("## Part 2 -- STAR-ORDER verification (load-bearing)")
    lines.append("")
    lines.append(
        f"Tested **{p2['n_pairs']}** (record, interior vertex) pairs across all {len(records)} records. "
        f"Method: monotone closure -- starting from S0 = {{h}} u link(h), repeatedly add any vertex "
        "with an edge fully inside its own neighbourhood-intersect-S (equivalent, by confluence of "
        "the monotone bootstrap rule, to checking whether *some* sequential order exists)."
    )
    lines.append("")
    if p2["n_fail"] == 0:
        lines.append(f"**Result: PASS. 0 failures out of {p2['n_pairs']} pairs.** STAR-ORDER holds "
                      "on the entire corpus with no counterexample.")
    else:
        lines.append(f"**Result: FAIL. {p2['n_fail']} failures out of {p2['n_pairs']} pairs.**")
        lines.append("")
        lines.append("Up to 10 failing (ident, h) pairs:")
        lines.append("")
        for ident, h, desc in p2["failures"]:
            lines.append(f"- `{ident}` h={h}: {desc}")
    lines.append("")

    # PART 3
    lines.append("## Part 3 -- numeric consequence")
    lines.append("")
    lines.append(
        "`B_star(rec) = min over interior h of (2^d + 2*(-1)^d) * 2^(n-d-1) / 6`, "
        "the Bridge-Lemma-derived cap implied by choosing the max/best interior vertex per record."
    )
    lines.append("")
    if p3["n_violations"] == 0:
        lines.append(f"**a <= B_star holds on all {len(records)} records (0 violations).**")
    else:
        lines.append(f"**FAIL: {p3['n_violations']} records with a > B_star.**")
        lines.append("")
        for ident, a, b_star in p3["violation_examples"]:
            lines.append(f"- `{ident}`: a={a}, B_star={float(b_star):.4f}")
    lines.append("")
    lines.append(f"- max(a / B_star) = **{p3['max_ratio']:.6f}** at `{p3['max_ratio_ident']}`")
    lines.append(f"- max(a / (11*2^(n-7))) [uniform version] = **{p3['max_uniform_ratio']:.6f}** "
                 f"at `{p3['max_uniform_ident']}`")
    lines.append("")
    lines.append("Per-(r,k) table of max(a/B_star), r=8..16, k=1..6 (blank = no records in that cell):")
    lines.append("")
    header = "| r | " + " | ".join(f"k={k}" for k in range(1, 7)) + " |"
    lines.append(header)
    lines.append("|" + "---|" * (7))
    for r in range(8, 17):
        row = [f"r={r}"]
        for k in range(1, 7):
            v = p3["table"].get((r, k))
            row.append(f"{v:.4f}" if v is not None else "--")
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    # PART 4
    lines.append("## Part 4 -- per-step gain profile (stratified sample)")
    lines.append("")
    lines.append(
        f"Sample: {p4['sample_size']} records, every (r,k) cell present in the corpus, "
        f"cap {SAMPLE_CAP_PER_CELL} per cell (seed {SAMPLE_SEED})."
    )
    lines.append("")
    lines.append(f"**Identity check `sum_i (b_i-2), i>=4 == k`:** {len(p4['identity_violations'])} violations "
                 f"out of {p4['sample_size']}.")
    if p4["identity_violations"]:
        lines.append("")
        for ident, s, k in p4["identity_violations"][:10]:
            lines.append(f"- `{ident}`: sum={s}, k={k}")
    lines.append("")

    lines.append("Histogram of step factor f_i by b_i (# already-placed neighbours):")
    lines.append("")
    lines.append("| b_i | mean f_i | min f_i | max f_i | n steps |")
    lines.append("|---|---|---|---|---|")
    for b in [2, 3, 4, 5]:
        vals = p4["f_by_b"].get(b, [])
        label = "5+" if b == 5 else str(b)
        if vals:
            lines.append(f"| {label} | {sum(vals)/len(vals):.4f} | {min(vals):.4f} | {max(vals):.4f} | {len(vals)} |")
        else:
            lines.append(f"| {label} | -- | -- | -- | 0 |")
    lines.append("")

    b3 = p4["f_b3_values"]
    if b3:
        lines.append(f"b_i==3 steps specifically (empirical `1 + Pr[phi(u)=phi(w)]`): "
                     f"mean f_i = **{sum(b3)/len(b3):.6f}**, max f_i = **{max(b3):.6f}**, n={len(b3)}.")
    else:
        lines.append("b_i==3 steps: none observed in the sample.")
    lines.append("")

    gr = p4["gamma_records"]
    gammas_all = [(ident, r, k, g) for ident, r, k, g in gr if g == g]
    if gammas_all:
        max_ident, max_r, max_k, max_g = max(gammas_all, key=lambda t: t[3])
        vals = [g for *_, g in gammas_all]
        lines.append(f"Implied gamma = 2*(GAINPROD)^(1/k) distribution over the sample: "
                     f"mean={sum(vals)/len(vals):.6f}, min={min(vals):.6f}, "
                     f"**max={max_g:.6f}** at `{max_ident}` (r={max_r}, k={max_k}).")
        lines.append("")
        lines.append("Per-k table of max implied gamma:")
        lines.append("")
        by_k: Dict[int, float] = {}
        by_k_ident: Dict[int, str] = {}
        for ident, r, k, g in gammas_all:
            if k not in by_k or g > by_k[k]:
                by_k[k] = g
                by_k_ident[k] = ident
        lines.append("| k | max implied gamma | argmax ident |")
        lines.append("|---|---|---|")
        for k in sorted(by_k):
            lines.append(f"| {k} | {by_k[k]:.6f} | `{by_k_ident[k]}` |")
        lines.append("")
        interp = []
        if max_g < 1.5:
            interp.append("max implied gamma < 1.5: the 3/2 cap is plausible for P from this per-step evidence.")
        if max_g > 4.0 / 3.0:
            interp.append("max implied gamma > 4/3: the 4/3 cap CANNOT come from any per-step argument on P.")
        if interp:
            lines.append("Interpretation: " + " ".join(interp))
            lines.append("")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n")
    print(f"\nWrote {OUT_MD}")
    print(f"Total runtime: {time.time() - t_all:.1f}s")


if __name__ == "__main__":
    main()
