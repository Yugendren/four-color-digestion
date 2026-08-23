#!/usr/bin/env python3
"""Evaluate the BFS-LINK ORDERING proof scheme's upper bound on P(S,4) (hence
on a = |Phi(K)| via the Bridge Lemma) for every corpus configuration.

THE SCHEME (deterministic given the graph -- see the mass-law program's
"BFS-LINK ORDERING" writeup):

  1. H = induced subgraph on interior vertices r+1..n (must be connected).
  2. h_1 = interior vertex of maximum degree (ties -> smallest label).
     L_1 = link(h_1) = cyclic neighbour sequence of h_1.  C := {h_1} u L_1.
     F := 4 * (2**d_1 + 2*(-1)**d_1),  d_1 = deg(h_1).
  3. BFS over H from h_1 giving h_2..h_k (ties among a vertex's unvisited
     H-neighbours broken by smallest label). For each h_j (j=2..k):
       - h_j must already be in C (a structural fact: h_j is a graph-neighbour
         of the BFS-vertex that discovered it, and that discoverer is already
         in C by induction);
       - L_j = link(h_j) as a CYCLIC sequence, recovered from the graph
         (NOT trusted from the rotation-system order in `adjacency`): the
         neighbours of h_j form a cycle in S, so we build the induced
         subgraph on N(h_j) and verify every vertex there has exactly two
         neighbours within N(h_j), then walk it;
       - split L_j into maximal cyclic runs ("arcs") of vertices NOT in C.
         Each arc of length t contributes a factor arc_factor(t) to F and is
         then added to C.
  4. After the loop, C must equal all n vertices.
  5. BOUND := F / 24 (claimed upper bound on a).

Any verification failure (H disconnected, a link not a single cycle, h_j not
already in C, C incomplete at the end) is a scheme-integrity failure: it is
reported loudly and the record is written to the output with an "error"
field and null numeric fields -- it is NOT silently patched or dropped.

Usage:
    PYTHONPATH=src .venv/bin/python tools/arc_profile.py
    PYTHONPATH=src .venv/bin/python tools/arc_profile.py --limit 500   # smoke test

Writes:
    results/mass-law/arc_profile.jsonl  -- one line per record:
        {ident, r, k, n, d1, arcs:[t,...], bound, a, ok (= a <= bound),
         gain, gamma_prov}
        (failed records instead carry {ident, r, k, n, error}, all other
        fields null)
    results/mass-law/arc-profile.md     -- sections A-F described in the
        mass-law program's arc-profile task.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, deque
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fourcolor.lemma_corpus import load_corpus  # noqa: E402

OUT_JSONL = ROOT / "results" / "mass-law" / "arc_profile.jsonl"
OUT_MD = ROOT / "results" / "mass-law" / "arc-profile.md"
PROGRESS_EVERY = 5000


class SchemeError(Exception):
    """A verification step of the BFS-LINK ORDERING scheme failed."""


def arc_factor(t: int) -> int:
    """Max over endpoint colour pairs of the number of walks of length t+1
    in K_3.  2 for t=1, 3 for t=2, 6 for t=3, 11 for t=4, 22 for t=5, 43 for
    t=6, ..."""
    v = 2 ** (t + 1)
    if (t + 1) % 2 == 0:
        return (v + 2) // 3
    return (v + 1) // 3


def g_factor(t: int) -> Fraction:
    """g(t) = arc_factor(t) / 2**t."""
    return Fraction(arc_factor(t), 2 ** t)


def build_link_cycle(adj: dict[int, list[int]], h: int) -> list[int]:
    """Recover the cyclic order of N(h) by walking the induced subgraph on
    N(h) (does NOT trust the rotation-system order stored in `adjacency`).
    Raises SchemeError if N(h) is not covered by a single cycle."""
    neigh = adj.get(h, [])
    N = set(neigh)
    if not N:
        raise SchemeError(f"link({h}) is empty")
    ind: dict[int, list[int]] = {}
    for v in N:
        nb = [u for u in adj.get(v, []) if u in N]
        if len(nb) != 2:
            raise SchemeError(
                f"link({h}): vertex {v} has {len(nb)} neighbours within N({h}) (expected 2)"
            )
        ind[v] = nb
    start = min(N)
    cycle = [start]
    prev, cur = None, start
    while True:
        a, b = ind[cur]
        nxt = a if a != prev else b
        if nxt == start:
            break
        cycle.append(nxt)
        prev, cur = cur, nxt
    if len(cycle) != len(N):
        raise SchemeError(
            f"link({h}) is not a single cycle covering all {len(N)} neighbours (walk found {len(cycle)})"
        )
    return cycle


def process_record(adj: dict[int, list[int]], r: int, n: int) -> dict:
    """Run the BFS-LINK ORDERING scheme once. Returns a dict of derived
    quantities on success; raises SchemeError on any verification failure."""
    interior = list(range(r + 1, n + 1))
    k = len(interior)
    interior_set = set(interior)
    all_vertices = set(range(1, n + 1))

    if k == 0:
        raise SchemeError("k=0: no interior vertices, scheme requires h_1")

    H_adj = {v: sorted(u for u in adj.get(v, []) if u in interior_set) for v in interior}

    # H connectivity check.
    seen = {interior[0]}
    dq = deque([interior[0]])
    while dq:
        u = dq.popleft()
        for w in H_adj[u]:
            if w not in seen:
                seen.add(w)
                dq.append(w)
    if len(seen) != k:
        raise SchemeError(
            f"H (interior induced subgraph) not connected: BFS from {interior[0]} reached {len(seen)}/{k}"
        )

    # Step 1: h_1 = max-degree interior vertex, ties -> smallest label.
    deg = {v: len(adj.get(v, [])) for v in interior}
    maxdeg = max(deg[v] for v in interior)
    h1 = min(v for v in interior if deg[v] == maxdeg)
    d1 = deg[h1]
    L1 = build_link_cycle(adj, h1)
    if len(L1) != d1:
        raise SchemeError(f"h1={h1}: link length {len(L1)} != degree {d1}")
    C = {h1} | set(L1)
    F = 4 * (2 ** d1 + 2 * ((-1) ** d1))

    # BFS order over H from h1, ties -> smallest label.
    order = [h1]
    visited = {h1}
    dq = deque([h1])
    while dq:
        u = dq.popleft()
        for w in H_adj[u]:
            if w not in visited:
                visited.add(w)
                order.append(w)
                dq.append(w)
    if len(order) != k:
        raise SchemeError(f"BFS order length {len(order)} != k={k}")

    arcs_flat: list[int] = []
    per_step: list[list[int]] = []
    for h_j in order[1:]:
        if h_j not in C:
            raise SchemeError(f"h_j={h_j} not already in C when its BFS step is processed")
        Lj = build_link_cycle(adj, h_j)
        m = len(Lj)
        in_c = [v in C for v in Lj]
        start_idx = next((i for i in range(m) if in_c[i]), None)
        if start_idx is None:
            raise SchemeError(f"h_j={h_j}: link entirely outside C (no anchor found)")
        step_arcs: list[list[int]] = []
        i = 0
        while i < m:
            idx = (start_idx + i) % m
            if in_c[idx]:
                i += 1
                continue
            run = []
            while i < m and not in_c[(start_idx + i) % m]:
                run.append(Lj[(start_idx + i) % m])
                i += 1
            step_arcs.append(run)
        for run in step_arcs:
            t = len(run)
            F *= arc_factor(t)
            arcs_flat.append(t)
            C.update(run)
        per_step.append([len(run) for run in step_arcs])

    if C != all_vertices:
        missing = all_vertices - C
        raise SchemeError(f"C does not cover all n vertices after the loop; missing {sorted(missing)}")

    gain = Fraction(1, 1)
    for t in arcs_flat:
        gain *= g_factor(t)

    bound = Fraction(F, 24)
    gamma_prov = 2 * float(gain) ** (1 / (k - 1)) if k >= 2 else None

    # |link(h) ^ link(h')| for every H-edge (all adjacent interior pairs,
    # not just BFS-tree edges), links taken as sets (order irrelevant).
    xor_pairs: list[tuple[int, int, int]] = []
    for u in interior:
        lu = set(adj.get(u, []))
        for w in H_adj[u]:
            if u < w:
                lw = set(adj.get(w, []))
                xor_pairs.append((u, w, len(lu ^ lw)))

    return {
        "d1": d1,
        "F": F,
        "bound": bound,
        "arcs": arcs_flat,
        "per_step": per_step,
        "gain": gain,
        "gamma_prov": gamma_prov,
        "xor_pairs": xor_pairs,
    }


def sharp_cap(r: int, k: int) -> float:
    return (2 ** r + 2) / 6 * (4 / 3) ** (k - 1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=None, help="only process the first N records (smoke test)")
    ap.add_argument("--out", default=str(OUT_JSONL), help=f"output JSONL path (default {OUT_JSONL})")
    ap.add_argument("--md-out", default=str(OUT_MD), help=f"output markdown report path (default {OUT_MD})")
    args = ap.parse_args()

    out_path = Path(args.out)
    md_path = Path(args.md_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    corpus = load_corpus()
    records = corpus.records
    if args.limit is not None:
        records = records[: args.limit]
    total = len(records)
    print(f"loaded corpus: {len(corpus.records)} records; processing {total}")

    t0 = time.time()

    n_no_adjacency = 0
    n_failed = 0
    failure_reasons: Counter[str] = Counter()
    failure_examples: list[tuple[str, str]] = []  # (ident, message)

    refuted: list[dict] = []  # a > bound
    n_ok_success = 0
    n_success = 0

    arc_hist_overall: Counter[int] = Counter()
    arc_hist_by_k: dict[int, Counter[int]] = {}

    max_gamma_overall = None
    max_gamma_ident = None
    max_gamma_by_rk: dict[tuple[int, int], float] = {}
    max_gamma_by_rk_ident: dict[tuple[int, int], str] = {}

    xor_dist: Counter[int] = Counter()
    xor_anomalies: list[tuple[str, int, int, int]] = []  # (ident, h, h', xor_size)

    steps_total_by_k: Counter[int] = Counter()
    steps_zero_by_k: Counter[int] = Counter()
    steps_only1_by_k: Counter[int] = Counter()

    max_bound_ratio_by_rk: dict[tuple[int, int], float] = {}

    with out_path.open("w") as f:
        for i, rec in enumerate(records, start=1):
            adj = rec.adjacency
            if adj is None:
                n_no_adjacency += 1
                print(f"WARNING: no adjacency for ident={rec.ident}, skipping")
                continue

            row: dict
            try:
                res = process_record(adj, rec.r, rec.n)
            except SchemeError as exc:
                n_failed += 1
                msg = str(exc)
                failure_reasons[msg.split(":")[0]] += 1
                if len(failure_examples) < 50:
                    failure_examples.append((rec.ident, msg))
                print(f"SCHEME FAILURE ident={rec.ident} r={rec.r} n={rec.n} k={rec.k}: {msg}")
                row = {
                    "ident": rec.ident,
                    "r": rec.r,
                    "k": rec.k,
                    "n": rec.n,
                    "d1": None,
                    "arcs": None,
                    "bound": None,
                    "a": rec.a,
                    "ok": None,
                    "gain": None,
                    "gamma_prov": None,
                    "error": msg,
                }
                f.write(json.dumps(row) + "\n")
                continue

            n_success += 1
            bound = res["bound"]
            ok = rec.a <= bound
            n_ok_success += int(ok)
            bound_f = float(bound)

            row = {
                "ident": rec.ident,
                "r": rec.r,
                "k": rec.k,
                "n": rec.n,
                "d1": res["d1"],
                "arcs": res["arcs"],
                "bound": bound_f,
                "a": rec.a,
                "ok": ok,
                "gain": float(res["gain"]),
                "gamma_prov": res["gamma_prov"],
            }
            f.write(json.dumps(row) + "\n")

            if not ok:
                refuted.append(
                    {
                        "ident": rec.ident,
                        "r": rec.r,
                        "k": rec.k,
                        "a": rec.a,
                        "bound": bound_f,
                        "ratio": rec.a / bound_f if bound_f else float("inf"),
                    }
                )

            for t in res["arcs"]:
                arc_hist_overall[t] += 1
                arc_hist_by_k.setdefault(rec.k, Counter())[t] += 1

            gp = res["gamma_prov"]
            if gp is not None:
                if max_gamma_overall is None or gp > max_gamma_overall:
                    max_gamma_overall = gp
                    max_gamma_ident = rec.ident
                key = (rec.r, rec.k)
                if key not in max_gamma_by_rk or gp > max_gamma_by_rk[key]:
                    max_gamma_by_rk[key] = gp
                    max_gamma_by_rk_ident[key] = rec.ident

            for (h, hp, xv) in res["xor_pairs"]:
                xor_dist[xv] += 1
                if xv != 2 and len(xor_anomalies) < 200:
                    xor_anomalies.append((rec.ident, h, hp, xv))

            for step_arcs in res["per_step"]:
                steps_total_by_k[rec.k] += 1
                if len(step_arcs) == 0:
                    steps_zero_by_k[rec.k] += 1
                elif all(a == 1 for a in step_arcs):
                    steps_only1_by_k[rec.k] += 1

            sc = sharp_cap(rec.r, rec.k)
            if sc > 0:
                ratio = bound_f / sc
                key = (rec.r, rec.k)
                if key not in max_bound_ratio_by_rk or ratio > max_bound_ratio_by_rk[key]:
                    max_bound_ratio_by_rk[key] = ratio

            if i % PROGRESS_EVERY == 0:
                print(f"processed {i}/{total} ...")

    dt = time.time() - t0
    print(
        f"done: {n_success} scheme successes ({n_ok_success} with a<=bound), "
        f"{n_failed} scheme failures, {n_no_adjacency} skipped (no adjacency); {dt:.2f}s elapsed"
    )

    write_report(
        md_path=md_path,
        total=total,
        n_success=n_success,
        n_ok_success=n_ok_success,
        n_failed=n_failed,
        failure_reasons=failure_reasons,
        failure_examples=failure_examples,
        refuted=refuted,
        arc_hist_overall=arc_hist_overall,
        arc_hist_by_k=arc_hist_by_k,
        max_gamma_overall=max_gamma_overall,
        max_gamma_ident=max_gamma_ident,
        max_gamma_by_rk=max_gamma_by_rk,
        max_gamma_by_rk_ident=max_gamma_by_rk_ident,
        xor_dist=xor_dist,
        xor_anomalies=xor_anomalies,
        steps_total_by_k=steps_total_by_k,
        steps_zero_by_k=steps_zero_by_k,
        steps_only1_by_k=steps_only1_by_k,
        max_bound_ratio_by_rk=max_bound_ratio_by_rk,
    )
    try:
        out_display = out_path.relative_to(ROOT)
        md_display = md_path.relative_to(ROOT)
    except ValueError:
        out_display, md_display = out_path, md_path
    print(f"wrote {out_display} and {md_display}")
    return 0


def write_report(
    *,
    md_path: Path,
    total: int,
    n_success: int,
    n_ok_success: int,
    n_failed: int,
    failure_reasons: Counter,
    failure_examples: list[tuple[str, str]],
    refuted: list[dict],
    arc_hist_overall: Counter,
    arc_hist_by_k: dict[int, Counter],
    max_gamma_overall,
    max_gamma_ident,
    max_gamma_by_rk: dict[tuple[int, int], float],
    max_gamma_by_rk_ident: dict[tuple[int, int], str],
    xor_dist: Counter,
    xor_anomalies: list[tuple[str, int, int, int]],
    steps_total_by_k: Counter,
    steps_zero_by_k: Counter,
    steps_only1_by_k: Counter,
    max_bound_ratio_by_rk: dict[tuple[int, int], float],
) -> None:
    lines: list[str] = []
    lines.append("# BFS-LINK ORDERING scheme: arc-profile evaluation")
    lines.append("")
    lines.append(
        f"Corpus: {total} records processed. Scheme succeeded (all verification steps passed) on "
        f"{n_success}; {n_failed} hit a scheme-integrity failure (see the note below); "
        f"{total - n_success - n_failed} had no adjacency."
    )
    lines.append("")

    n_refuted = len(refuted)
    if n_failed or n_refuted:
        lines.append("## LEAD: scheme status")
        lines.append("")
        if n_refuted:
            lines.append(
                f"**REFUTED**: {n_refuted} record(s) have a > BOUND. The BFS-LINK ORDERING scheme as "
                "specified does NOT give a valid upper bound on every corpus configuration. See section A."
            )
        if n_failed:
            lines.append(
                f"**{n_failed} record(s) failed a scheme verification step** (H disconnected / a link "
                "was not a single cycle / C did not cover all vertices / etc.) -- these are reported, "
                "not patched. Breakdown of failure kinds:"
            )
            for reason, count in failure_reasons.most_common():
                lines.append(f"  - {reason}: {count}")
            lines.append("")
            lines.append("First failure examples (up to 50 collected):")
            for ident, msg in failure_examples[:20]:
                lines.append(f"  - `{ident}`: {msg}")
        lines.append("")
    else:
        lines.append(
            "**Scheme holds on every record with adjacency, with a <= BOUND in all cases, and no "
            "verification-step failures.**"
        )
        lines.append("")

    # A
    lines.append("## A. a > BOUND count (scheme validity)")
    lines.append("")
    lines.append(f"Records with a > BOUND: **{n_refuted}** (must be 0 for the scheme to be valid).")
    lines.append("")
    if n_refuted:
        lines.append("REFUTED. Worst 20 by ratio a/bound:")
        lines.append("")
        lines.append("| ident | r | k | a | bound | ratio |")
        lines.append("|---|---|---|---|---|---|")
        worst = sorted(refuted, key=lambda d: -d["ratio"])[:20]
        for d in worst:
            lines.append(
                f"| {d['ident']} | {d['r']} | {d['k']} | {d['a']} | {d['bound']:.6g} | {d['ratio']:.6g} |"
            )
    else:
        lines.append("None. (a <= bound holds on all successfully-processed records.)")
    lines.append("")

    # B
    lines.append("## B. Arc-length histogram")
    lines.append("")
    lines.append("Over the whole corpus (t -> count):")
    lines.append("")
    lines.append("| t | count |")
    lines.append("|---|---|")
    for t in sorted(arc_hist_overall):
        lines.append(f"| {t} | {arc_hist_overall[t]} |")
    lines.append("")
    lines.append("Per k (rows = t, columns = k):")
    lines.append("")
    ks = sorted(arc_hist_by_k)
    ts = sorted(arc_hist_overall)
    header = "| t | " + " | ".join(f"k={k}" for k in ks) + " |"
    sep = "|---|" + "|".join("---" for _ in ks) + "|"
    lines.append(header)
    lines.append(sep)
    for t in ts:
        row = " | ".join(str(arc_hist_by_k.get(k, Counter()).get(t, 0)) for k in ks)
        lines.append(f"| {t} | {row} |")
    lines.append("")

    # C
    lines.append("## C. gamma_prov (provable gamma)")
    lines.append("")
    if max_gamma_overall is not None:
        lines.append(f"Max gamma_prov over the corpus: **{max_gamma_overall:.6f}** (ident `{max_gamma_ident}`).")
    else:
        lines.append("No record had k >= 2 with a successful scheme run; gamma_prov undefined everywhere.")
    lines.append("")
    lines.append(
        "Interpretation: gamma_prov < 2 means the scheme provably beats the current cap 2^(r+k-3); "
        "gamma_prov < 1.5 would mean it provably beats 3/2."
    )
    lines.append("")
    lines.append("Max gamma_prov per (r,k), r=8..16, k=2..8 (blank = no corpus record in that cell):")
    lines.append("")
    r_range = range(8, 17)
    k_range = range(2, 9)
    header = "| r\\k | " + " | ".join(str(k) for k in k_range) + " |"
    sep = "|---|" + "|".join("---" for _ in k_range) + "|"
    lines.append(header)
    lines.append(sep)
    for r in r_range:
        cells = []
        for k in k_range:
            v = max_gamma_by_rk.get((r, k))
            cells.append(f"{v:.4f}" if v is not None else "")
        lines.append(f"| {r} | " + " | ".join(cells) + " |")
    lines.append("")

    # D
    lines.append("## D. |link(h) XOR link(h')| for adjacent interior pairs")
    lines.append("")
    lines.append("Distribution over the whole corpus (value -> count of H-edges with that symmetric-difference size):")
    lines.append("")
    lines.append("| |link^link| | count |")
    lines.append("|---|---|")
    for v in sorted(xor_dist):
        lines.append(f"| {v} | {xor_dist[v]} |")
    lines.append("")
    n_anom = sum(c for v, c in xor_dist.items() if v != 2)
    if n_anom:
        lines.append(
            f"**{n_anom} H-edge(s) have |link^link| != 2** -- this is the fact that is supposed to "
            "guarantee arcs of length >= 2 at the second interior vertex; it does NOT hold universally. "
            f"Up to 200 examples collected, listing up to 40 here:"
        )
        lines.append("")
        lines.append("| ident | h | h' | xor |")
        lines.append("|---|---|---|---|")
        for ident, h, hp, xv in xor_anomalies[:40]:
            lines.append(f"| {ident} | {h} | {hp} | {xv} |")
    else:
        lines.append("No H-edge with |link^link| != 2 was found: the guarantee holds universally in this corpus.")
    lines.append("")

    # E
    lines.append("## E. Zero-gain BFS steps (j >= 2)")
    lines.append("")
    lines.append(
        "For each j >= 2, the step 'contributes zero arcs' if its entire link was already coloured "
        "(link subset of C), and 'contributes only length-1 arcs' if every arc it produced has t=1. "
        "These are exactly the steps where the scheme gains nothing beyond a factor of 2."
    )
    lines.append("")
    lines.append("| k | total steps | zero-arc steps | frac | only-len-1 steps | frac |")
    lines.append("|---|---|---|---|---|---|")
    for k in sorted(steps_total_by_k):
        tot = steps_total_by_k[k]
        z = steps_zero_by_k.get(k, 0)
        o1 = steps_only1_by_k.get(k, 0)
        lines.append(f"| {k} | {tot} | {z} | {z/tot:.4f} | {o1} | {o1/tot:.4f} |")
    tot_all = sum(steps_total_by_k.values())
    z_all = sum(steps_zero_by_k.values())
    o1_all = sum(steps_only1_by_k.values())
    if tot_all:
        lines.append(f"| all | {tot_all} | {z_all} | {z_all/tot_all:.4f} | {o1_all} | {o1_all/tot_all:.4f} |")
    lines.append("")

    # F
    lines.append("## F. BOUND vs empirical sharp cap")
    lines.append("")
    lines.append(
        "Max over the cell of BOUND / sharp_cap, sharp_cap = (2^r+2)/6 * (4/3)^(k-1), for r=8..16, k=1..8 "
        "(blank = no corpus record in that cell). Larger = the provable bound is looser relative to the "
        "empirical sharp cap."
    )
    lines.append("")
    r_range = range(8, 17)
    k_range = range(1, 9)
    header = "| r\\k | " + " | ".join(str(k) for k in k_range) + " |"
    sep = "|---|" + "|".join("---" for _ in k_range) + "|"
    lines.append(header)
    lines.append(sep)
    for r in r_range:
        cells = []
        for k in k_range:
            v = max_bound_ratio_by_rk.get((r, k))
            cells.append(f"{v:.4f}" if v is not None else "")
        lines.append(f"| {r} | " + " | ".join(cells) + " |")
    lines.append("")

    md_path.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
