#!/usr/bin/env python3
"""Close the COARSE-CARTWHEEL gap in the d<=6 rows of ``tools/lp_discharge.py``.

THE GAP
-------
``lp_discharge.lowdeg_rows`` builds a row for every spoke-degree necklace that the pool
does not block, on the *coarse* cartwheel returned by ``nl4ct.generate_cartwheel``: a hub
plus ``d`` spokes of pinned degree, with every second-neighbour vertex left at the open
range ``[5, 9]``.  Blocking is tested on that coarse object.

A coarse wheel can be unblocked while EVERY full refinement of it -- every way of pinning
the second neighbourhood to concrete degrees in ``{5,...,9}`` (``9`` = "9 or more") -- is
blocked by the pool.  In that case no vertex of a minimum counterexample can carry that
necklace, and the emitted row is spurious.  That direction is *anti-conservative* for an
INFEASIBLE verdict, so it has to be checked, not assumed.  (Refining strengthens the
BOUND, which §4 of ``LP-SCHEMA-RESULT.md`` already notes -- but refining can also delete
the row entirely, which is the part that was not covered.)

WHAT THIS TOOL DOES
-------------------
For a given necklace it enumerates the full refinement space ``{5,...,9}^m`` (``m`` = the
number of open second-neighbour slots) EXACTLY -- not by sampling -- and reports how many
refinements the pool blocks, how many survive, and a witness.

Direct enumeration is out of reach (``m`` is 10-12, i.e. 10M-244M refinements, at ~1 ms a
blocking test).  Instead the blocking predicate is *compiled*: the wheel's rotation system
is fixed, so ``PseudoConfiguration::homomorphism`` branches only on structure, never on
degrees -- degrees only ever cause a rejection.  Running the homomorphism BFS with the
degree test switched off therefore yields, for each (configuration, root dart) pair, a
vertex map, and the pair matches iff every mapped vertex's degree interval is contained in
the configuration's.  For the pinned second neighbours that is a per-slot membership
constraint.  So

    "this refinement is blocked"  ==  a DNF over the slots,

one term per surviving (configuration, root dart) pair, each term a conjunction of
``slot in S`` literals.  Counting its models by DFS with two-sided pruning (a term fully
satisfied => the whole subtree is blocked; no term still alive => the whole subtree is
unblocked) is exact and fast.  ``--validate`` differentially checks the compiled predicate
against ``nl4ct.wheel_is_blocked`` on random refinements.

SEMANTICS NOTE (why the answer is never in doubt for an unblocked coarse wheel)
------------------------------------------------------------------------------
``PseudoConfiguration::representative_degree`` (``nl4ct._representative_degree``) collapses
any vertex whose degree upper bound exceeds 8 to the single value ``9``.  A coarse
second neighbour has range ``[5,9]``, so the coarse blocking test IS the blocking test of
the refinement that pins every second neighbour to ``9``.  Hence "coarse unblocked" already
implies that one specific full refinement -- the tail-maximised one, the same object §5 of
``LP-SCHEMA-RESULT.md`` uses for its necessity audit -- is unblocked, and no low-degree row
generated this way can be spurious.  The enumeration below confirms that mechanically and
quantifies how thin the surviving set is.

USAGE
-----
    .venv/bin/python tools/lowdeg_refinement_check.py            # the 3 degree-5 IIS necklaces
    .venv/bin/python tools/lowdeg_refinement_check.py --necklace 55767 --validate 500
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fourcolor import nl4ct as N  # noqa: E402

VALS = N.CARTWHEEL_DEGREES  # (5, 6, 7, 8, 9)
R14_POOL_DIR = ROOT / "build/steinberger-pool-r14/D"
FULL_POOL_DIR = ROOT / "third_party/computer-checks/reducible-configurations/D"
OUT_DIR = ROOT / "results/steinberger"

# The three necklaces supplying the degree-5 rows of the 12-row IIS, plus the fourth
# degree-5 necklace that appears in the wider 19-row Farkas support.
IIS_NECKLACES = ((5, 5, 7, 6, 7), (5, 7, 5, 7, 7), (5, 7, 6, 7, 7), (5, 5, 6, 7, 7))


# --------------------------------------------------------------------------
# refinement = pinning the open second-neighbour degrees
# --------------------------------------------------------------------------


def refinement_slots(w: N.CartWheel) -> list[int]:
    """The vertices ``generate_cartwheel`` leaves open, i.e. range ``[5, 9]``."""
    g = w.g
    return [v for v in range(g.N) if g.deg_lo[v] != g.deg_hi[v]]


def pin(w: N.CartWheel, assignment: dict[int, int]) -> N.CartWheel:
    """The refinement of ``w`` that fixes ``assignment[v]`` as ``v``'s degree."""
    g = w.g
    lo, hi = list(g.deg_lo), list(g.deg_hi)
    for v, d in assignment.items():
        lo[v] = hi[v] = d
    g2 = N.Graph(g.N, g.head, g.rev, g.succ, g.pred, lo, hi)
    return N.CartWheel(center=w.center, center_darts=w.center_darts, g=g2)


# --------------------------------------------------------------------------
# compiling ``blocked_by_reducible_configuration`` into a DNF over the slots
# --------------------------------------------------------------------------


def structural_vertex_map(Z: N.Graph, e: int, Z_star: N.Graph, e_star: int):
    """``nl4ct.homomorphism`` with the DEGREE TEST REMOVED.

    The BFS in ``PseudoConfiguration::homomorphism`` never branches on degrees -- a degree
    mismatch only makes it return ``None`` early -- so running it degree-blind and applying
    the degree tests afterwards to the resulting vertex map is equivalent.  Returns the
    list of ``(conf vertex, wheel vertex)`` pairs the traversal identifies, or ``None`` if
    the map fails *structurally* (for any degrees at all).
    """
    vmap = [-1] * Z.N
    dmap = [-1] * len(Z.head)
    pairs: list[tuple[int, int]] = []
    Q: deque[tuple[int, int]] = deque([(e, e_star)])
    while Q:
        f, f_star = Q.popleft()
        if dmap[f] != -1:
            if dmap[f] != f_star:
                return None
            continue
        dmap[f] = f_star
        h, h_star = Z.head[f], Z_star.head[f_star]
        if vmap[h] != -1 and vmap[h] != h_star:
            return None
        if vmap[h] == -1:
            pairs.append((h, h_star))
        vmap[h] = h_star
        Q.append((Z.rev[f], Z_star.rev[f_star]))
        for nxt, nxt_star in ((Z.succ[f], Z_star.succ[f_star]), (Z.pred[f], Z_star.pred[f_star])):
            if nxt != N.NIL:
                if nxt_star == N.NIL:
                    return None
                Q.append((nxt, nxt_star))
    return pairs


def compile_blocking_dnf(w: N.CartWheel, confs, slots: list[int]):
    """Compile "the pool blocks this refinement" into a DNF over the slot degrees.

    Returns ``(terms, always_blocked)`` where each term is a ``dict slot -> frozenset`` of
    permitted degrees; the refinement is blocked iff some term is satisfied.  A term with
    no literals means the wheel is blocked for every refinement (``always_blocked``).

    Mirrors ``nl4ct._contain_conf`` exactly: root darts come from the degree bucket
    ``(deg_lo[head], deg_lo[tail])`` of the configuration's own root dart, the
    ``d_y > 8 => head must be the centre`` filter is applied, and the match test is the
    ``include`` homomorphism.  The difference is only that the bucket lookup and the
    degree tests are turned into constraints on the not-yet-pinned slots instead of being
    evaluated against one fixed graph.
    """
    g = w.g
    slotset = set(slots)
    n_darts = len(g.head)
    # confs grouped by their root dart's (head degree, tail degree) bucket key
    by_bucket: dict[tuple[int, int], list] = {}
    for conf in confs:
        y = conf.g.head[conf.dart_id]
        x = conf.g.head[conf.g.rev[conf.dart_id]]
        d_y, d_x = conf.g.deg_lo[y], conf.g.deg_lo[x]
        if d_y > N.CONF_DEG_MAX or d_x > N.CONF_DEG_MAX:
            continue
        by_bucket.setdefault((d_y, d_x), []).append(conf)

    terms: list[dict[int, frozenset]] = []
    for f_star in range(n_darts):
        y_s = g.head[f_star]
        x_s = g.head[g.rev[f_star]]
        y_vals = VALS if y_s in slotset else (g.deg_lo[y_s],)
        x_vals = VALS if x_s in slotset else (g.deg_lo[x_s],)
        for d_y in y_vals:
            for d_x in x_vals:
                if d_y > 8 and y_s != w.center:
                    continue
                for conf in by_bucket.get((d_y, d_x), ()):
                    pairs = structural_vertex_map(conf.g, conf.dart_id, g, f_star)
                    if pairs is None:
                        continue
                    cons: dict[int, set] = {}
                    if y_s in slotset:
                        cons[y_s] = {d_y}
                    if x_s in slotset:
                        cons.setdefault(x_s, set(VALS)).intersection_update({d_x})
                    ok = True
                    for h, h_star in pairs:
                        clo, chi = conf.g.deg_lo[h], conf.g.deg_hi[h]
                        if h_star in slotset:
                            allowed = {k for k in VALS if clo <= k <= chi}
                            cur = cons.get(h_star)
                            cons[h_star] = allowed if cur is None else (cur & allowed)
                            if not cons[h_star]:
                                ok = False
                                break
                        elif not (clo <= g.deg_lo[h_star] and g.deg_hi[h_star] <= chi):
                            ok = False
                            break
                    if ok:
                        terms.append({v: frozenset(s) for v, s in cons.items()})
    # dedupe, then drop terms subsumed by a strictly weaker one
    uniq = {tuple(sorted((v, s) for v, s in t.items())): t for t in terms}
    terms = list(uniq.values())
    always = any(len(t) == 0 for t in terms)
    kept = []
    for i, t in enumerate(terms):
        if any(
            j != i
            and set(u).issubset(t)
            and all(t[v] <= u[v] for v in u)
            and (len(u) < len(t) or any(t[v] < u[v] for v in u))
            for j, u in enumerate(terms)
        ):
            continue
        kept.append(t)
    return kept, always


def blocked_by_dnf(terms, assignment: dict[int, int]) -> bool:
    return any(all(assignment[v] in s for v, s in t.items()) for t in terms)


# --------------------------------------------------------------------------
# exact model counting of the compiled DNF
# --------------------------------------------------------------------------


def count_blocked(terms, slots: list[int], want_witness: int = 3):
    """Exact ``(n_blocked, witnesses)`` over ``{5,...,9}^len(slots)``.

    DFS over the constrained slots with two-sided pruning: a fully satisfied term blocks
    the whole remaining subtree, and an empty live-term list leaves it entirely unblocked.
    Slots no term mentions just multiply the counts by ``5 ** (unconstrained)``.
    """
    nv = len(VALS)
    used = sorted({v for t in terms for v in t})
    free = [v for v in slots if v not in set(used)]
    # branch on the most-constrained slot first
    freq: dict[int, int] = {v: 0 for v in used}
    for t in terms:
        for v in t:
            freq[v] += 1
    order = sorted(used, key=lambda v: -freq[v])
    witnesses: list[dict[int, int]] = []
    nodes = 0

    def complete(assignment: dict[int, int]) -> dict[int, int]:
        out = dict(assignment)
        for v in order:
            out.setdefault(v, VALS[-1])
        for v in free:
            out[v] = VALS[-1]
        return out

    def dfs(i: int, live, assignment: dict[int, int]) -> int:
        nonlocal nodes
        nodes += 1
        if any(len(t) == 0 for t in live):
            return nv ** (len(order) - i)
        if not live:
            if len(witnesses) < want_witness:
                witnesses.append(complete(assignment))
            return 0
        if i == len(order):
            return 0
        v = order[i]
        total = 0
        for val in VALS:
            new_live = []
            satisfied = False
            for t in live:
                if v in t:
                    if val not in t[v]:
                        continue
                    t2 = {k: s for k, s in t.items() if k != v}
                    if not t2:
                        satisfied = True
                        break
                    new_live.append(t2)
                else:
                    new_live.append(t)
            if satisfied:
                total += nv ** (len(order) - i - 1)
                continue
            assignment[v] = val
            total += dfs(i + 1, new_live, assignment)
            del assignment[v]
        return total

    blocked_used = dfs(0, list(terms), {})
    scale = nv ** len(free)
    return blocked_used * scale, witnesses, nodes


# --------------------------------------------------------------------------
# per-necklace driver
# --------------------------------------------------------------------------


def analyse(necklace, confs, rules, validate: int = 0, seed: int = 20260823) -> dict:
    d = len(necklace)
    w = N.generate_cartwheel(d, list(necklace))
    slots = refinement_slots(w)
    m = len(slots)
    total = len(VALS) ** m

    t0 = time.time()
    terms, always = compile_blocking_dnf(w, confs, slots)
    t_compile = time.time() - t0

    t0 = time.time()
    n_blocked, witnesses, nodes = count_blocked(terms, slots)
    t_count = time.time() - t0

    coarse_blocked = N.wheel_is_blocked(w, confs)
    tailmax = {v: VALS[-1] for v in slots}
    tailmax_blocked = N.wheel_is_blocked(pin(w, tailmax), confs)

    out = {
        "necklace": list(necklace),
        "d": d,
        "tag": f"d{d}-" + "".join(map(str, necklace)),
        "n_slots": m,
        "n_refinements": total,
        "n_blocked": n_blocked,
        "n_unblocked": total - n_blocked,
        "coarse_blocked": coarse_blocked,
        "tail_maximised_blocked": tailmax_blocked,
        "dnf_terms": len(terms),
        "blocked_for_every_refinement": always,
        "dfs_nodes": nodes,
        "seconds": {"compile": round(t_compile, 3), "count": round(t_count, 3)},
        "witnesses": [],
    }

    # every reported witness is re-checked with the untouched blocking machinery
    for a in witnesses:
        wr = pin(w, a)
        out["witnesses"].append(
            {
                "slot_degrees": {str(v): a[v] for v in sorted(a)},
                "blocked_recheck": N.wheel_is_blocked(wr, confs),
            }
        )

    if rules is not None:
        from lp_discharge import lowdeg_row  # noqa: PLC0415

        coarse = lowdeg_row(w, rules)
        out["coarse_row"] = {"coeffs": list(coarse.coeffs), "constant": coarse.constant}
        for a, rec in zip(witnesses, out["witnesses"]):
            r = lowdeg_row(pin(w, a), rules)
            rec["row_equals_coarse"] = r.coeffs == coarse.coeffs
            # LB_coarse <= LB_refined pointwise on x >= 0 <=> coeffs increase termwise
            rec["row_dominates_coarse"] = all(
                b >= c for b, c in zip(r.coeffs, coarse.coeffs)
            )

    if validate:
        rnd = random.Random(seed)
        bad = 0
        for _ in range(validate):
            a = {v: rnd.choice(VALS) for v in slots}
            if blocked_by_dnf(terms, a) != N.wheel_is_blocked(pin(w, a), confs):
                bad += 1
        out["validation"] = {"samples": validate, "disagreements": bad}
    return out


def sweep_tail_maximised(confs, degrees=(5, 6)) -> dict:
    """Every low-degree row at once, via the tail-maximised refinement.

    ``_representative_degree`` collapses a ``[5,9]`` second neighbour to the single value
    ``9``, so the coarse blocking test and the blocking test of the all-9 refinement are
    the *same* test on the *same* graph.  Checking that mechanically over all 3,046
    unblocked ``d in {5,6}`` necklaces closes the coarse-row gap for every low-degree row
    of the LP, not only for the ones in the certificate: each such row is witnessed by an
    explicit full refinement (all second neighbours of degree >= 9) that the pool does not
    block.
    """
    out = {}
    for d in degrees:
        tot = unblocked = witnessed = mismatched = 0
        for degs in N.enum_wheel_degree_sequences(d):
            tot += 1
            w = N.generate_cartwheel(d, list(degs))
            if N.wheel_is_blocked(w, confs):
                continue
            unblocked += 1
            slots = refinement_slots(w)
            tm = pin(w, {v: VALS[-1] for v in slots})
            if N.wheel_is_blocked(tm, confs):
                mismatched += 1
            else:
                witnessed += 1
        out[str(d)] = {
            "necklaces": tot,
            "coarse_unblocked": unblocked,
            "tail_maximised_refinement_unblocked": witnessed,
            "tail_maximised_refinement_blocked": mismatched,
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--necklace", action="append", default=None,
                    help="spoke-degree necklace, e.g. 55767 (repeatable); "
                         "default = the 4 degree-5 necklaces of the certificate")
    ap.add_argument("--pool", default=str(R14_POOL_DIR))
    ap.add_argument("--validate", type=int, default=0,
                    help="differentially check the compiled DNF against "
                         "nl4ct.wheel_is_blocked on N random refinements")
    ap.add_argument("--sweep", action="store_true",
                    help="also check the tail-maximised refinement of EVERY unblocked "
                         "d in {5,6} necklace (i.e. of every low-degree LP row)")
    ap.add_argument("--json", default=str(OUT_DIR / "lowdeg_refinement_check.json"))
    args = ap.parse_args()

    necklaces = (
        [tuple(int(c) for c in s) for s in args.necklace] if args.necklace else list(IIS_NECKLACES)
    )
    confs = N.load_configurations(args.pool)
    rules = N.load_rules(ROOT / "third_party/discharging-rules/R")
    print(f"pool {args.pool}: {len(confs)} configurations")

    results = [analyse(nk, confs, rules, validate=args.validate) for nk in necklaces]
    for r in results:
        print(
            f"{r['tag']}: slots={r['n_slots']} refinements={r['n_refinements']:,} "
            f"blocked={r['n_blocked']:,} unblocked={r['n_unblocked']:,} "
            f"(coarse_blocked={r['coarse_blocked']}, tail_max_blocked={r['tail_maximised_blocked']}, "
            f"terms={r['dnf_terms']}, nodes={r['dfs_nodes']}, {r['seconds']})"
        )
        if r.get("validation"):
            print(f"    validation: {r['validation']}")
        for wt in r["witnesses"][:1]:
            print(f"    witness: {wt}")

    blob = {"pool": args.pool, "n_configurations": len(confs), "results": results}
    if args.sweep:
        t0 = time.time()
        blob["tail_maximised_sweep"] = sweep_tail_maximised(confs)
        print(f"tail-maximised sweep ({time.time() - t0:.0f} s): "
              f"{json.dumps(blob['tail_maximised_sweep'])}")
    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(blob, indent=1))
    print(f"wrote {args.json}")

    spurious = [r["tag"] for r in results if r["n_unblocked"] == 0]
    if spurious:
        print(f"SPURIOUS ROWS (every refinement blocked): {spurious}")
        return 1
    print("no spurious rows: every necklace has at least one unblocked full refinement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
