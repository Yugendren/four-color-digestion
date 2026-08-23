#!/usr/bin/env python3
"""LP schema-robustness for the 2026 (Steinberger et al.) wheel discharging argument.

QUESTION
--------
The published proof fixes 84 rule *shapes* ``R`` (``third_party/discharging-rules/R``)
and a vector of *amounts* ``x0 in Z_{>=0}^84`` (the 4th field of each ``.rule`` file).
Is the failure of the ring<=14 pool (run ``results/p3/runs/steinberger-s1``) an accident
of the published amounts, or is it a property of the rule *shapes*?  This tool answers
that by deciding an LP over the amount vector ``x``.

WHAT IS ENCODED (read this before trusting any verdict)
-------------------------------------------------------
The discharging argument does NOT require every wheel to be charge-killed: survivors are
permitted and the three gluing lemmas mop them up.  The precise invariant the C++
enforces is in ``cartwheel.cpp::enum_bad_cartwheels``, on every *fully refined* cartwheel
``L`` that survives ``fix_in_rules`` + ``fix_out_rules``::

    assert(C == 0);                                        // C = upper_bound_of_charge(L)
    assert(d == 7 || d == 8);
    assert(darts_by_deg[7] + darts_by_deg[8] + darts_by_deg[9] > 0);   // a spoke of deg >= 7

S1's failure was exactly these asserts firing (833 wheels: 780x ``C>0`` at d=7,8 and
53x ``d in {9,10}``).  So the condition we encode is, for every such surviving leaf ``L``:

    d(L) in {9,10,11}                      ->  C(L, x) <  0     (L must not survive at all)
    d(L) in {7,8}, no spoke of degree >= 7 ->  C(L, x) <  0     (L must not survive at all)
    d(L) in {7,8}, some spoke degree >= 7  ->  C(L, x) <= 0     (C == 0 is the allowed case;
                                                                 C < 0 means L is pruned)

Note ``C == 0`` is not required, only ``C <= 0``: if ``C < 0`` the leaf is pruned by
``prune`` before it ever reaches the assert.  ``C <= 0`` is therefore the exact necessary
and sufficient charge condition at a leaf.

LEAF CHARGE IS *LINEAR* IN x (no max)
--------------------------------------
At a leaf, ``upper_bound_of_charge`` is called with a FULL ``combined_rule_with_spokes``
(length d), so the ``amount_of_possible_charge_send`` max never runs::

    C(L) = 10*(6-d) - sum_i amount_of_charge_send(out-dart i) + sum_j cr_j.amount

and ``prune_by_non_associated_rule`` (plus its companion assert) forces, for a survivor,

    cr_j.combined_flag[k] == 1  <=>  always_apply(center_darts[j], rules[k]).

So the spoke combined rules are *determined by the leaf graph*, and

    C(L, x) = 10*(6 - d) + sum_k (IN_k - OUT_k) * x_k
    IN_k  = #{ j : always_apply(center_darts[j], rules[k]) }        (into the hub)
    OUT_k = #{ i : always_apply(rev(center_darts[i]), rules[k]) }   (out of the hub)

purely affine in x, with integer coefficients.  (Validated: all 10,094 published
full-pool leaves in ``third_party/computer-checks/wheels/zero`` evaluate to exactly 0
at x0 under this formula -- see ``--validate``.)

THE d <= 6 SIDE -- WITHOUT IT THE LP IS VACUOUS
------------------------------------------------
The C++ only enumerates hubs of degree 7..11, where the initial charge ``10*(6-d)`` is
already negative.  Taken alone, the leaf rows above are satisfied by ``x = 0`` (send
nothing: every hub keeps its negative initial charge), so an LP over them decides
nothing.  The lower bounds on x come from the OTHER half of the discharging argument,
which the released code never checks because the paper does it by hand: a vertex of
degree 5 starts with +10 and must give it all away; a vertex of degree 6 starts with 0
and must not end up positive.  Discharging preserves total charge (= 120 by Euler), so
the argument needs EVERY vertex to end with charge <= 0.

For d in {5,6} we therefore add rows built from a *lower* bound on the hub's final
charge -- valid for any x >= 0 and at any level of degree refinement::

    LB(w, x) = 10*(6-d) - sum_i POSS_i(x) + sum_j ALW_j(x)
    POSS_i   = sum of x_k over base rules k that are NOT ``never_apply`` out of spoke i
               (an over-count of what the hub can actually send)
    ALW_j    = sum of x_k over base rules k that ``always_apply`` into the hub from spoke j
               (an under-count of what the hub actually receives)

``always_apply`` implies the rule really fires, and ``never_apply`` implies it really
cannot, in *any* graph extending the wheel -- so ``LB <= actual final charge``, and
``actual <= 0`` forces ``LB(w, x) <= 0``.  These are generated over every spoke-degree
necklace in ``{5,...,9}^d`` that the pool does not block; refining them further would
only strengthen them, so using the coarsest wheels is the conservative choice.

Sanity: at x0, over the ring<=14 pool, the maximum of LB over all 580 unblocked d=5 and
2,466 unblocked d=6 wheels is exactly 0 (attained e.g. at d=5 with all five spokes of
degree 9, where the row is exactly ``10 - 5*x_rule001 <= 0``).  x0 is on the boundary of
the low-degree rows and of all 3,425 distinct full-pool leaf rows simultaneously.

WHY A LEAF FOUND AT x0 IS A VALID CONSTRAINT FOR EVERY x  (the monotonicity lemma)
-----------------------------------------------------------------------------------
The refinement forest is enumerated with pruning at every node, so the leaves we observe
depend on x0.  Claim: if leaf ``L`` is produced by the search at (pool P0, amounts x0),
then ``C(L, x) <= 0`` is a *necessary* condition at (any pool P subset of P0, any
x >= 0).  Proof sketch:

  (a) Refinement only narrows degree intervals; rotations never change.  The forest's
      *branching* is x-independent, but it is NOT pool-independent: ``fix_in_rules``
      branches over the pool-dependent NON-BLOCKED combined-rule set.  That set moves the
      right way -- a smaller pool blocks fewer combined rules, so
      ``combined_rules(P_full) subset of combined_rules(P14)`` (measured: 671 vs 681, and
      the 671 are content-identical members of the 681).  Hence every branch available
      under the full pool is still available under P14, and the full-pool forest is a
      SUB-forest of the P14 forest.  (This is the direction we need; the reverse would
      have broken the argument.)
  (b) ``blocked_by_reducible_configuration`` is x-independent and monotone in the pool:
      unblocked under P0 implies unblocked under P subset of P0.  ``prune_by_non_associated_rule``
      is x- and pool-independent.  So every ancestor of L on its path stays un-pruned by
      those two tests.
  (c) ``upper_bound_of_charge`` is NON-INCREASING along refinement whenever x >= 0:
      narrowing degrees can only add ``always_apply`` matches (out-charge up, needs
      x >= 0), can only remove ``never_apply``-surviving candidates (the per-spoke max
      down), and fixing a spoke's combined rule replaces the max by one of its members.
  (d) Hence for any x >= 0: either every ancestor survives charge pruning, in which case
      the search reaches L and the assert demands C(L,x) <= 0; or some ancestor A has
      C(A,x) < 0, and then C(L,x) <= C(A,x) < 0 by (c).  Either way C(L,x) <= 0.

  The same argument upgrades to the strict rows: for d >= 9 (or d in {7,8} with no
  spoke of degree >= 7) the leaf must never survive, i.e. C(L,x) < 0 in both branches.

(c) is where ``x >= 0`` is used; it is a standing hypothesis of every claim made here.
Because ``.rule`` amounts are parsed as C++ ``int``, x is integral, so ``C < 0`` is
``C <= -1``; ``--real`` drops integrality and weakens the strict rows to ``C <= 0``.

Consequently the LP built from ANY set of observed leaves is a *relaxation* of the true
feasible set of amount vectors.  INFEASIBLE is therefore a proof; FEASIBLE is not
(it only means these rows do not suffice).

CODE-NECESSARY vs MATH-NECESSARY (the sharpest caveat, and its repair)
-----------------------------------------------------------------------
``upper_bound_of_charge`` counts only ``always_apply`` rules outward, and
``fix_out_rules`` stops refining once no rule is ``dominantly_apply``-but-not-
``always_apply``.  ``dominantly_apply`` is STRICTER than ``has_intersection``
(``pseudo_configuration.cpp:417-423``), so a leaf can retain rules that are neither
``always_apply`` nor ``never_apply`` on an out-dart: rules that might fire in some
realization but are not counted.  Measured on the IIS leaves: 11 of 5,292 (rule, out-dart)
pairs.  For such a leaf ``C`` STRICTLY over-estimates the hub's true final charge, so
``C(L,x) <= 0`` is a condition of the *released verification procedure* rather than,
obviously, of the underlying argument.  Two blunt diagnostics confirm this matters:
dropping the inexact rows (``--exact-only``) and weakening every row to a sound lower
bound (``--conservative``) both make the ring<=14 LP FEASIBLE.

The repair is :func:`row_is_math_necessary` / ``--audit-necessity``: pass to the
TAIL-MAXIMISED leaf (every open tail ``[a,9]`` narrowed to ``[9,9]``, i.e. restrict to
realizations where every unpinned second-neighbour has large degree).  If, as measured for
all 9 degree-7 rows of the IIS, that leaf (1) has a fully determined OUT side, (2) yields
the identical row, and (3) is still unblocked, then in those realizations ``OUT`` is exact
while ``IN`` can only exceed the branch's flag sum, so ``true final charge >= C(L,x)``;
the argument's ``true final charge <= 0`` then forces ``C(L,x) <= 0``.  Undetermined IN
rules are harmless precisely because they push the true charge UP.  All 12 IIS rows pass
this audit, so the certified infeasibility is a statement about the mathematics, not only
about the released code.

USAGE
-----
    python tools/lp_discharge.py --validate                # x0 vs the 10,094 published leaves
    python tools/lp_discharge.py --control                 # full 8,200-config pool: must be FEASIBLE
    python tools/lp_discharge.py --main                    # ring<=14 pool: the real question
    python tools/lp_discharge.py --main --real             # drop integrality (weaker, stronger claim)
    python tools/lp_discharge.py --wheel-level --control   # the STRONG (max-of-affine) condition,
                                                           # cutting-plane; documented as the wrong
                                                           # encoding -- its control fails
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fourcolor import nl4ct as N  # noqa: E402

# Leaf ("bad cartwheel") directories.
FULL_POOL_LEAVES = ROOT / "third_party/computer-checks/wheels/zero"
R14_LEAVES = [
    ROOT / "results/p3/runs/steinberger-s1/work/wheels/zero",
    ROOT / "results/p3/runs/steinberger-s1/work/wheels/zero_ndebug",
]
OUT_DIR = ROOT / "results/steinberger"


# --------------------------------------------------------------------------
# Row extraction
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Row:
    """``constant + <coeffs, x> <= rhs`` (rhs is 0, or -1/0 for a strict row)."""

    coeffs: tuple[int, ...]
    constant: int
    strict: bool
    d: int
    spoke_degs: tuple[int, ...]
    sources: tuple[str, ...] = field(default=(), compare=False)

    def key(self) -> tuple:
        return (self.coeffs, self.constant, self.strict)

    def value_at(self, x) -> int:
        return self.constant + sum(c * xi for c, xi in zip(self.coeffs, x))


def leaf_row(cw: N.CartWheel, rules) -> Row:
    """Exact linear form of ``upper_bound_of_charge`` at a fully refined cartwheel."""
    g = cw.g
    d = cw.degree
    n = len(rules)
    coeffs = [0] * n
    spoke_degs = []
    for j in range(d):
        dart_to_center = cw.center_darts[j]
        from_center = g.rev[dart_to_center]
        spoke_degs.append(g.deg_lo[g.head[from_center]])
        for k, r in enumerate(rules):
            if N.always_apply(g, dart_to_center, r):
                coeffs[k] += 1
            if N.always_apply(g, from_center, r):
                coeffs[k] -= 1
    strict = d >= 9 or max(spoke_degs) < 7
    return Row(
        coeffs=tuple(coeffs),
        constant=10 * (6 - d),
        strict=strict,
        d=d,
        spoke_degs=tuple(spoke_degs),
    )


def lowdeg_row(w: N.CartWheel, rules) -> Row:
    """Lower-bound charge row for a degree-5/6 hub (see module docstring)."""
    g = w.g
    d = w.degree
    coeffs = [0] * len(rules)
    spoke_degs = []
    for j in range(d):
        dart_to_center = w.center_darts[j]
        from_center = g.rev[dart_to_center]
        spoke_degs.append(g.deg_lo[g.head[from_center]])
        for k, r in enumerate(rules):
            if not N.never_apply(g, from_center, r):
                coeffs[k] -= 1  # over-count of what the hub may send
            if N.always_apply(g, dart_to_center, r):
                coeffs[k] += 1  # under-count of what the hub must receive
    return Row(
        coeffs=tuple(coeffs),
        constant=10 * (6 - d),
        strict=False,
        d=d,
        spoke_degs=tuple(spoke_degs),
    )


def lowdeg_rows(pool_dir, rules, degrees=(5, 6), cache: Path | None = None):
    """All low-degree rows for the unblocked wheels of the given pool (cached to JSON)."""
    if cache is not None and cache.exists():
        blob = json.loads(cache.read_text())
        return [
            Row(tuple(r["coeffs"]), r["constant"], False, r["d"], tuple(r["spoke_degs"]),
                (r.get("source", ""),))
            for r in blob["rows"]
        ], blob["counts"]
    confs = N.load_configurations(pool_dir)
    rows, counts = [], {}
    for d in degrees:
        tot = blocked = 0
        for degs in N.enum_wheel_degree_sequences(d):
            tot += 1
            w = N.generate_cartwheel(d, degs)
            if N.wheel_is_blocked(w, confs):
                blocked += 1
                continue
            r = lowdeg_row(w, rules)
            rows.append(Row(r.coeffs, r.constant, False, d, r.spoke_degs,
                            (f"d{d}-" + "".join(map(str, degs)),)))
        counts[str(d)] = {"necklaces": tot, "blocked": blocked, "rows": tot - blocked}
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({
            "pool": str(pool_dir),
            "counts": counts,
            "rows": [{"coeffs": list(r.coeffs), "constant": r.constant, "d": r.d,
                      "spoke_degs": list(r.spoke_degs),
                      "source": r.sources[0] if r.sources else ""} for r in rows],
        }))
    return rows, counts


def leaf_out_is_exact(cw: N.CartWheel, rules) -> bool:
    """Is the hub's OUT-charge fully determined at this leaf?

    ``fix_out_rules`` refines only while some rule is ``dominantly_apply`` but not
    ``always_apply``; ``dominantly_apply`` is STRICTER than ``has_intersection`` (see
    ``pseudo_configuration.cpp:417-423``: it additionally demands that either the rule's
    degree interval is unbounded above, or the cartwheel vertex's is bounded).  So a leaf
    can still carry rules that are neither ``always_apply`` nor ``never_apply`` on an
    out-dart -- i.e. rules that MIGHT fire in some realization but are not counted in
    ``out_charge_sum``.  For such a leaf the C++'s ``upper_bound_of_charge`` is a STRICT
    over-estimate of the hub's real final charge, so the row ``C(L,x) <= 0`` is a
    condition of *the released verification procedure* but is stronger than the
    mathematical requirement "final charge <= 0".

    When this returns True, no rule is undetermined outward, and (given the leaf's
    in-side is pinned by its ``combined_rule_with_spokes`` branch) ``C(L,x)`` IS the
    hub's exact final charge, making ``C(L,x) <= 0`` mathematically necessary.
    """
    g = cw.g
    for j in range(cw.degree):
        from_center = g.rev[cw.center_darts[j]]
        for r in rules:
            if not N.always_apply(g, from_center, r) and not N.never_apply(g, from_center, r):
                return False
    return True


def leaf_row_conservative(cw: N.CartWheel, rules) -> Row:
    """A leaf row that is necessary for the MATHEMATICS, not just for the released code.

    ``leaf_row`` mirrors the C++'s ``upper_bound_of_charge``, whose OUT term counts only
    ``always_apply`` rules.  That is a genuine *upper* bound on the hub's final charge,
    and :func:`leaf_out_is_exact` shows it is sometimes strict, so ``C(L,x) <= 0`` can be
    stronger than the real requirement "final charge <= 0".

    This variant replaces the OUT term by an over-count -- every rule that is not
    ``never_apply`` on the out-dart -- giving

        LBC(L, x) = 10*(6-d) - sum_i POSS_out_i(x) + sum_j <flag_j, x>   <=   final charge

    (the IN term stays exact because it is pinned by the leaf's own
    ``combined_rule_with_spokes`` branch).  ``LBC(L,x) <= 0`` is therefore implied by the
    mathematical requirement, and coincides with ``leaf_row`` exactly on the leaves where
    :func:`leaf_out_is_exact` holds.  Weakening rows this way is strictly less lossy than
    discarding the inexact ones.
    """
    g = cw.g
    d = cw.degree
    coeffs = [0] * len(rules)
    spoke_degs = []
    for j in range(d):
        dart_to_center = cw.center_darts[j]
        from_center = g.rev[dart_to_center]
        spoke_degs.append(g.deg_lo[g.head[from_center]])
        for k, r in enumerate(rules):
            if N.always_apply(g, dart_to_center, r):
                coeffs[k] += 1
            if not N.never_apply(g, from_center, r):
                coeffs[k] -= 1
    return Row(tuple(coeffs), 10 * (6 - d), d >= 9 or max(spoke_degs) < 7, d, tuple(spoke_degs))


def tail_maximise(cw: N.CartWheel) -> N.CartWheel:
    """Narrow every OPEN TAIL ``[a,9]`` (a < 9) to ``[9,9]``, i.e. "degree 9 or more".

    In the cartwheel abstraction ``9`` means "9 or more", so this selects the sub-family
    of realizations in which every not-yet-pinned second-neighbourhood vertex has large
    degree.  It is a narrowing, so it never invents structure.
    """
    import copy

    g = copy.deepcopy(cw.g)
    for v in range(len(g.deg_lo)):
        if g.deg_hi[v] == N.CARTWHEEL_DEG_MAX and g.deg_lo[v] < N.CARTWHEEL_DEG_MAX:
            g.deg_lo[v] = N.CARTWHEEL_DEG_MAX
    return N.CartWheel(center=cw.center, center_darts=list(cw.center_darts), g=g)


def row_is_math_necessary(cw: N.CartWheel, rules, confs) -> tuple[bool, dict]:
    """Is ``leaf_row(cw).value(x) <= 0`` necessary for the MATHEMATICS, not just the code?

    ``leaf_row`` mirrors ``upper_bound_of_charge``, which counts only ``always_apply``
    rules outward.  Where some rule is undetermined on an out-dart
    (:func:`leaf_out_is_exact` False) the bound strictly over-estimates the hub's true
    final charge, so ``C <= 0`` is a condition of the released verification procedure but
    not obviously of the underlying argument.

    This checks the repair: pass to the tail-maximised leaf (:func:`tail_maximise`) and
    verify

      (1) the OUT side is then fully determined -- every rule is ``always_apply`` or
          ``never_apply`` on every out-dart, so ``OUT_true == sum of always_apply``;
      (2) the row is UNCHANGED by the narrowing (same coefficients and constant);
      (3) the narrowed structure is still not blocked by the pool, so realizations of it
          are exactly the ones the discharging argument must handle.

    Given (1)-(3): in those realizations ``OUT`` is exact while ``IN`` can only exceed
    the branch's flag sum, so ``true final charge >= C(L,x)``.  The argument demands
    ``true final charge <= 0``, hence ``C(L,x) <= 0`` -- mathematically necessary.
    (Undetermined IN rules are harmless precisely because they push the true charge UP.)
    """
    cw2 = tail_maximise(cw)
    r1, r2 = leaf_row(cw, rules), leaf_row(cw2, rules)
    exact_after = leaf_out_is_exact(cw2, rules)
    same_row = (r1.coeffs == r2.coeffs and r1.constant == r2.constant and r1.strict == r2.strict)
    blocked_after = N.wheel_is_blocked(cw2, confs)
    ok = exact_after and same_row and not blocked_after
    return ok, {
        "out_exact_before": leaf_out_is_exact(cw, rules),
        "out_exact_after_tail_maximise": exact_after,
        "row_unchanged_by_tail_maximise": same_row,
        "blocked_after_tail_maximise": blocked_after,
        "mathematically_necessary": ok,
    }


def audit_certificate_necessity(cert_path: Path, pool_dir: Path) -> dict:
    """Run :func:`row_is_math_necessary` on every leaf row of a certificate."""
    rules = load_rules()
    confs = N.load_configurations(pool_dir)
    cert = json.loads(Path(cert_path).read_text())
    out = {"certificate": str(cert_path), "pool": str(pool_dir), "rows": []}
    for r in cert["rows"]:
        src = r["source"]
        if not src.endswith(".cartwheel"):
            out["rows"].append({"source": src, "kind": "lowdeg",
                                "mathematically_necessary": True,
                                "why": "lower-bound form: over-counts OUT, under-counts IN"})
            continue
        path = None
        for d in [FULL_POOL_LEAVES] + R14_LEAVES:
            if (Path(d) / src).exists():
                path = Path(d) / src
                break
        if path is None:
            raise FileNotFoundError(src)
        ok, detail = row_is_math_necessary(N.parse_cartwheel_file(path), rules, confs)
        out["rows"].append({"source": src, "kind": "leaf", **detail})
    out["all_mathematically_necessary"] = all(
        r.get("mathematically_necessary") for r in out["rows"]
    )
    return out


def _leaf_paths(dirs) -> list[Path]:
    paths: list[Path] = []
    for d in dirs:
        p = Path(d)
        if p.is_dir():
            paths.extend(sorted(p.glob("*.cartwheel")))
    return paths


def extract_rows(dirs, rules, exact_only: bool = False, conservative: bool = False):
    """Deduplicated leaf rows.

    ``exact_only`` keeps only rows witnessed by at least one leaf whose OUT-charge is
    fully determined (:func:`leaf_out_is_exact`) -- the mathematically necessary subset,
    as opposed to the full set of conditions the released pipeline imposes.
    Returns ``(rows, n_leaves, n_exact_leaves)``.
    """
    paths = _leaf_paths(dirs)
    seen: dict[tuple, Row] = {}
    n_exact = 0
    for p in paths:
        cw = N.parse_cartwheel_file(p)
        row = leaf_row_conservative(cw, rules) if conservative else leaf_row(cw, rules)
        if exact_only:
            if not leaf_out_is_exact(cw, rules):
                continue
            n_exact += 1
        k = row.key()
        if k not in seen:
            seen[k] = Row(row.coeffs, row.constant, row.strict, row.d, row.spoke_degs, (p.name,))
    return list(seen.values()), len(paths), n_exact


# --------------------------------------------------------------------------
# LP
# --------------------------------------------------------------------------


def rhs_of(row: Row, integral: bool) -> int:
    """Right-hand side for ``<coeffs, x> <= rhs``, after moving the constant over."""
    limit = -1 if (row.strict and integral) else 0
    return limit - row.constant


def solve_lp(rows: list[Row], n_vars: int, integral: bool, x_lower: float = 0.0):
    """Feasibility LP: exists x >= x_lower with A x <= b?  Returns (status, x, dual_ray)."""
    import highspy

    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    h.setOptionValue("presolve", "off")  # keep row indices; needed for the dual ray
    inf = highspy.kHighsInf
    h.addVars(n_vars, [x_lower] * n_vars, [inf] * n_vars)
    h.changeColsCost(n_vars, list(range(n_vars)), [0.0] * n_vars)
    starts, idxs, vals, lowers, uppers = [], [], [], [], []
    for row in rows:
        starts.append(len(idxs))
        for k, c in enumerate(row.coeffs):
            if c:
                idxs.append(k)
                vals.append(float(c))
        lowers.append(-inf)
        uppers.append(float(rhs_of(row, integral)))
    h.addRows(len(rows), lowers, uppers, len(idxs), starts, idxs, vals)
    h.run()
    status = h.getModelStatus()
    name = h.modelStatusToString(status)
    if name == "Optimal":
        sol = h.getSolution()
        return "FEASIBLE", list(sol.col_value), None
    if name == "Infeasible":
        # highspy 1.15 returns (HighsStatus, bool has_ray, ndarray ray); older builds
        # returned (bool, ndarray).  Pick the last array-like element defensively.
        ret = h.getDualRay()
        vec = None
        if isinstance(ret, tuple):
            for item in reversed(ret):
                if hasattr(item, "__len__") and not isinstance(item, (str, bytes)):
                    vec = item
                    break
        return "INFEASIBLE", None, (list(vec) if vec is not None else None)
    return name, None, None


# --------------------------------------------------------------------------
# Exact-rational Farkas certificate: search + independent check
# --------------------------------------------------------------------------


def farkas_check(rows: list[Row], y: list[Fraction], integral: bool):
    """Independent, solver-free, exact-rational verification of a Farkas certificate.

    For the system ``{x >= 0 : A x <= b}``, a vector ``y >= 0`` with
    ``(y^T A)_k >= 0`` for all k and ``y^T b < 0`` proves infeasibility:
    ``0 <= (y^T A) x = y^T (A x) <= y^T b < 0``.
    Returns ``(ok, detail_dict)``.
    """
    assert len(y) == len(rows)
    n = len(rows[0].coeffs)
    bad_sign = [i for i, yi in enumerate(y) if yi < 0]
    combo = [Fraction(0)] * n
    total_b = Fraction(0)
    for yi, row in zip(y, rows):
        if yi == 0:
            continue
        for k, c in enumerate(row.coeffs):
            if c:
                combo[k] += yi * c
        total_b += yi * rhs_of(row, integral)
    neg_cols = [k for k, v in enumerate(combo) if v < 0]
    ok = not bad_sign and not neg_cols and total_b < 0
    return ok, {
        "n_support": sum(1 for yi in y if yi != 0),
        "negative_multipliers": bad_sign,
        "negative_columns": neg_cols,
        "yTb": str(total_b),
        "yTA_min": str(min(combo)) if combo else None,
        "ok": ok,
    }


def exact_certificate_from_ray(rows, ray, integral, max_den=10**6):
    """Rationalize a floating-point HiGHS dual ray into an exact Farkas certificate.

    The solver is only a heuristic here: whatever it returns is rationalized, sign-fixed,
    scaled to integers and then *verified exactly*.  If verification fails we fall back to
    an exact rational LP over the ray's support (:func:`exact_certificate_on_support`).
    """
    if ray is None:
        return None
    # HiGHS' ray sign convention is not guaranteed; try both.
    for sgn in (1.0, -1.0):
        y = [Fraction(max(0.0, sgn * v)).limit_denominator(max_den) for v in ray]
        if all(v == 0 for v in y):
            continue
        ok, _ = farkas_check(rows, y, integral)
        if ok:
            return scale_to_integers(y)
    for sgn in (1.0, -1.0):
        support = [i for i, v in enumerate(ray) if sgn * v > 1e-9]
        if not support:
            continue
        y = exact_certificate_on_support(rows, support, integral)
        if y is not None:
            return y
    return None


def scale_to_integers(y: list[Fraction]) -> list[Fraction]:
    from math import gcd

    den = 1
    for v in y:
        den = den * v.denominator // gcd(den, v.denominator)
    scaled = [v * den for v in y]
    num = 0
    for v in scaled:
        num = gcd(num, int(v))
    if num > 1:
        scaled = [v / num for v in scaled]
    return scaled


def exact_certificate_on_support(rows, support, integral):
    """Exact rational LP (Fraction simplex) for ``y_S >= 0, y_S^T A_S >= 0, y_S^T b_S = -1``."""
    sub = [rows[i] for i in support]
    n = len(sub[0].coeffs)
    # Variables y_1..y_m >= 0.  Constraints:  -(y^T A)_k <= 0  for each k,  y^T b = -1.
    # Solve as a phase-1 LP with Fractions.
    A_ub = [[Fraction(-r.coeffs[k]) for r in sub] for k in range(n)]
    b_ub = [Fraction(0)] * n
    A_eq = [[Fraction(rhs_of(r, integral)) for r in sub]]
    b_eq = [Fraction(-1)]
    y = _phase1_simplex(A_ub, b_ub, A_eq, b_eq, len(sub))
    if y is None:
        return None
    full = [Fraction(0)] * len(rows)
    for i, v in zip(support, y):
        full[i] = v
    ok, _ = farkas_check(rows, full, integral)
    return scale_to_integers(full) if ok else None


def _phase1_simplex(A_ub, b_ub, A_eq, b_eq, n):
    """Minimal exact-rational phase-1 simplex: find y >= 0 with A_ub y <= b_ub, A_eq y = b_eq.

    Standard Big-M-free two-phase formulation with slacks + artificials, Bland's rule
    (guarantees termination, exactness via Fraction).  Returns y or None.
    """
    rows_ = []
    rhs = []
    for a, b in zip(A_ub, b_ub):
        rows_.append(list(a))
        rhs.append(b)
    n_ub = len(A_ub)
    for a, b in zip(A_eq, b_eq):
        rows_.append(list(a))
        rhs.append(b)
    m = len(rows_)
    # Make rhs >= 0.
    for i in range(m):
        if rhs[i] < 0:
            rows_[i] = [-v for v in rows_[i]]
            rhs[i] = -rhs[i]
            if i < n_ub:
                rows_[i].append(Fraction(-1))  # placeholder; handled below
    # Build tableau: [y | slacks (only for the <= rows, sign-corrected) | artificials]
    slack_cols = []
    for i in range(n_ub):
        col = [Fraction(0)] * m
        col[i] = Fraction(1) if b_ub[i] >= 0 else Fraction(-1)
        slack_cols.append(col)
    width = n + n_ub + m
    T = [[Fraction(0)] * (width + 1) for _ in range(m)]
    for i in range(m):
        for j in range(n):
            T[i][j] = rows_[i][j] if j < len(rows_[i]) else Fraction(0)
        for j in range(n_ub):
            T[i][n + j] = slack_cols[j][i]
        T[i][n + n_ub + i] = Fraction(1)
        T[i][width] = rhs[i]
    basis = [n + n_ub + i for i in range(m)]
    cost = [Fraction(0)] * (width + 1)
    for i in range(m):
        for j in range(width + 1):
            cost[j] -= T[i][j]
    for i in range(m):
        cost[n + n_ub + i] = Fraction(0)
    for _ in range(20000):
        enter = -1
        for j in range(width):
            if j in basis:
                continue
            if cost[j] < 0:
                enter = j
                break
        if enter < 0:
            break
        leave, best = -1, None
        for i in range(m):
            if T[i][enter] > 0:
                ratio = T[i][width] / T[i][enter]
                if best is None or ratio < best or (ratio == best and basis[i] < basis[leave]):
                    best, leave = ratio, i
        if leave < 0:
            return None
        piv = T[leave][enter]
        T[leave] = [v / piv for v in T[leave]]
        for i in range(m):
            if i != leave and T[i][enter] != 0:
                f = T[i][enter]
                T[i] = [a - f * b for a, b in zip(T[i], T[leave])]
        if cost[enter] != 0:
            f = cost[enter]
            cost = [a - f * b for a, b in zip(cost, T[leave])]
        basis[leave] = enter
    if -cost[width] != 0:
        return None
    y = [Fraction(0)] * n
    for i, bvar in enumerate(basis):
        if bvar < n:
            y[bvar] = T[i][width]
    return y


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------


def load_rules():
    return N.load_rules(ROOT / "third_party/discharging-rules/R")


def x0_of(rules):
    return [r.amount for r in rules]


FULL_POOL_DIR = ROOT / "third_party/computer-checks/reducible-configurations/D"
R14_POOL_DIR = ROOT / "build/steinberger-pool-r14/D"

# In-process memo of the (expensive) leaf-row extraction, so `--all` can solve several
# LP variants without re-parsing ~98k cartwheel files each time.
_ROW_CACHE: dict[str, tuple[list, int] | None] = {}


def run(mode: str, integral: bool, dump: bool = True, no_lowdeg: bool = False,
        exact_only: bool = False, conservative: bool = False):
    rules = load_rules()
    x0 = x0_of(rules)
    dirs = [FULL_POOL_LEAVES] if mode == "control" else [FULL_POOL_LEAVES] + R14_LEAVES
    pool = FULL_POOL_DIR if mode == "control" else R14_POOL_DIR
    ck = f"{mode}{'-exact' if exact_only else ''}{'-cons' if conservative else ''}"
    if _ROW_CACHE.get(ck) is not None:
        rows, n_leaves, n_exact = list(_ROW_CACHE[ck][0]), _ROW_CACHE[ck][1], _ROW_CACHE[ck][2]
    else:
        rows, n_leaves, n_exact = extract_rows(dirs, rules, exact_only=exact_only,
                                               conservative=conservative)
        _ROW_CACHE[ck] = (list(rows), n_leaves, n_exact)
    n_leaf_rows = len(rows)
    ld_counts = {}
    if not no_lowdeg:
        ld_rows, ld_counts = lowdeg_rows(
            pool, rules, cache=OUT_DIR / f"lowdeg_rows_{mode}.json"
        )
        seen = {r.key() for r in rows}
        for r in ld_rows:
            if r.key() not in seen:
                seen.add(r.key())
                rows.append(r)
    stats = {
        "mode": mode,
        "integral": integral,
        "leaf_dirs": [str(d) for d in dirs],
        "pool_dir": str(pool),
        "n_leaves": n_leaves,
        "exact_only": exact_only,
        "conservative": conservative,
        "n_exact_leaves": n_exact,
        "n_leaf_rows_dedup": n_leaf_rows,
        "lowdeg": ld_counts,
        "n_rows_dedup": len(rows),
        "n_strict_rows": sum(1 for r in rows if r.strict),
        "rows_by_degree": {},
        "x0_violations": [],
    }
    for r in rows:
        stats["rows_by_degree"][str(r.d)] = stats["rows_by_degree"].get(str(r.d), 0) + 1
    for r in rows:
        v = r.value_at(x0)
        lim = -1 if (r.strict and integral) else 0
        if v > lim:
            stats["x0_violations"].append(
                {"d": r.d, "spokes": list(r.spoke_degs), "C_at_x0": v, "strict": r.strict,
                 "source": r.sources[0] if r.sources else None}
            )
    status, x, ray = solve_lp(rows, len(rules), integral)
    stats["lp_status"] = status
    result = {"stats": stats}
    if status == "FEASIBLE":
        xr = [round(v, 9) for v in x]
        stats["feasible_x"] = xr
        stats["x0_is_feasible"] = len(stats["x0_violations"]) == 0
    elif status == "INFEASIBLE":
        y = exact_certificate_from_ray(rows, ray, integral)
        if y is None:
            stats["certificate"] = None
            stats["certificate_verified"] = False
        else:
            ok, detail = farkas_check(rows, y, integral)
            stats["certificate_verified"] = ok
            stats["certificate_detail"] = detail
            support = [i for i, v in enumerate(y) if v != 0]
            cert = {
                "integral": integral,
                "n_rows": len(rows),
                "multipliers": [[i, str(y[i])] for i in support],
                "rows": [
                    {
                        "index": i,
                        "coeffs": list(rows[i].coeffs),
                        "constant": rows[i].constant,
                        "strict": rows[i].strict,
                        "rhs": rhs_of(rows[i], integral),
                        "d": rows[i].d,
                        "spoke_degs": list(rows[i].spoke_degs),
                        "source": rows[i].sources[0] if rows[i].sources else None,
                    }
                    for i in support
                ],
            }
            result["certificate"] = cert
    if dump:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        tag = f"{mode}{'-real' if not integral else ''}{'-exact' if exact_only else ''}"
        (OUT_DIR / f"lp_{tag}_stats.json").write_text(json.dumps(stats, indent=1))
        if "certificate" in result:
            (OUT_DIR / f"lp_{tag}_certificate.json").write_text(json.dumps(result["certificate"], indent=1))
    return result


def shrink_to_iis(rows: list[Row], n_vars: int, integral: bool) -> list[Row]:
    """Greedy deletion filter: shrink an infeasible row set to an IRREDUCIBLE one.

    Every row of the result is essential -- deleting any single one restores feasibility.
    Run on the Farkas support (a few dozen rows), so the O(|rows|) LP re-solves are cheap.
    """
    keep = list(range(len(rows)))
    for i in list(keep):
        trial = [j for j in keep if j != i]
        if trial and solve_lp([rows[j] for j in trial], n_vars, integral)[0] == "INFEASIBLE":
            keep = trial
    return [rows[j] for j in keep]


def certificate_blob(rows: list[Row], y, integral: bool) -> dict:
    return {
        "integral": integral,
        "n_rows": len(rows),
        "multipliers": [[i, str(y[i])] for i in range(len(rows)) if y[i] != 0],
        "rows": [
            {"index": i, "coeffs": list(r.coeffs), "constant": r.constant, "strict": r.strict,
             "rhs": rhs_of(r, integral), "d": r.d, "spoke_degs": list(r.spoke_degs),
             "source": r.sources[0] if r.sources else None}
            for i, r in enumerate(rows)
        ],
    }


def run_iis(mode: str = "main", integral: bool = True):
    """Re-solve `mode`, then shrink its Farkas support to an IIS and certify that."""
    res = run(mode, integral, dump=False)
    if res["stats"]["lp_status"] != "INFEASIBLE":
        return {"status": res["stats"]["lp_status"]}
    cert = res["certificate"]
    rules = load_rules()
    rows = [Row(tuple(r["coeffs"]), r["constant"], r["strict"], r["d"],
                tuple(r["spoke_degs"]), (r["source"],)) for r in cert["rows"]]
    iis = shrink_to_iis(rows, len(rules), integral)
    status, _, ray = solve_lp(iis, len(rules), integral)
    assert status == "INFEASIBLE", status
    y = exact_certificate_from_ray(iis, ray, integral)
    ok, detail = farkas_check(iis, y, integral)
    each_deletion_feasible = all(
        solve_lp([r for k, r in enumerate(iis) if k != i], len(rules), integral)[0] == "FEASIBLE"
        for i in range(len(iis))
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"lp_{mode}_certificate_iis.json").write_text(
        json.dumps(certificate_blob(iis, y, integral), indent=1)
    )
    return {"status": "INFEASIBLE", "support_before": len(rows), "iis_size": len(iis),
            "certificate_verified": ok, "detail": detail,
            "irreducible": each_deletion_feasible}


def validate(rules=None):
    """x0 must reproduce C == 0 on every published full-pool leaf."""
    rules = rules or load_rules()
    x0 = x0_of(rules)
    paths = _leaf_paths([FULL_POOL_LEAVES])
    bad = []
    by_d: dict[int, int] = {}
    for p in paths:
        row = leaf_row(N.parse_cartwheel_file(p), rules)
        by_d[row.d] = by_d.get(row.d, 0) + 1
        if row.value_at(x0) != 0:
            bad.append((p.name, row.d, row.value_at(x0)))
        if row.strict:
            bad.append((p.name, row.d, "strict-row-in-full-pool-leaves"))
    return {"n_leaves": len(paths), "by_degree": by_d, "n_bad": len(bad), "bad": bad[:20]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--control", action="store_true")
    ap.add_argument("--main", action="store_true")
    ap.add_argument("--real", action="store_true", help="drop integrality: strict rows become <= 0")
    ap.add_argument("--no-lowdeg", action="store_true", help="omit the d<=6 rows (vacuous LP; diagnostic only)")
    ap.add_argument("--all", action="store_true", help="both modes x {integral, real} x {with, without d<=6 rows}")
    ap.add_argument("--iis", action="store_true", help="shrink the main run's certificate to an irreducible one")
    ap.add_argument("--audit-necessity", action="store_true",
                    help="check every IIS row is necessary for the MATHEMATICS, not just "
                         "for the released code (see row_is_math_necessary)")
    ap.add_argument("--conservative", action="store_true",
                    help="weaken every leaf row to the mathematically necessary LBC form "
                         "(over-count the OUT side); see leaf_row_conservative")
    ap.add_argument("--exact-only", action="store_true",
                    help="keep only leaf rows whose OUT-charge is fully determined -- the "
                         "mathematically necessary subset (see leaf_out_is_exact)")
    args = ap.parse_args(argv)
    if args.audit_necessity:
        res = audit_certificate_necessity(
            OUT_DIR / "lp_main_certificate_iis.json", R14_POOL_DIR)
        (OUT_DIR / "iis_math_necessity.json").write_text(json.dumps(res, indent=1))
        print(json.dumps(res, indent=1))
        return 0
    if args.conservative:
        for mode in ("control", "main"):
            r = run(mode, not args.real, no_lowdeg=args.no_lowdeg, conservative=True)
            st = r["stats"]
            print(mode, json.dumps({k: st[k] for k in (
                "n_leaves", "n_rows_dedup", "n_strict_rows", "lp_status")}
                | {"n_x0_violations": len(st["x0_violations"]),
                   "certificate_verified": st.get("certificate_verified"),
                   "yTb": (st.get("certificate_detail") or {}).get("yTb"),
                   "cert_support": (st.get("certificate_detail") or {}).get("n_support")}),
                flush=True)
        return 0
    if args.exact_only:
        for mode in ("control", "main"):
            st = run(mode, not args.real, no_lowdeg=args.no_lowdeg, exact_only=True)["stats"]
            print(mode, json.dumps({k: st[k] for k in (
                "n_leaves", "n_exact_leaves", "n_rows_dedup", "n_strict_rows", "lp_status")}
                | {"n_x0_violations": len(st["x0_violations"]),
                   "certificate_verified": st.get("certificate_verified"),
                   "yTb": (st.get("certificate_detail") or {}).get("yTb"),
                   "cert_support": (st.get("certificate_detail") or {}).get("n_support")}),
                flush=True)
        return 0
    if args.iis:
        print(json.dumps(run_iis("main", not args.real), indent=1))
        return 0
    if args.all:
        summary = {}
        for mode in ("control", "main"):
            for integral in (True, False):
                for nolow in (False, True):
                    tag = f"{mode}-{'int' if integral else 'real'}-{'nolow' if nolow else 'low'}"
                    st = run(mode, integral, dump=False, no_lowdeg=nolow)["stats"]
                    summary[tag] = {
                        "lp_status": st["lp_status"],
                        "n_rows": st["n_rows_dedup"],
                        "n_strict_rows": st["n_strict_rows"],
                        "n_x0_violations": len(st["x0_violations"]),
                        "certificate_verified": st.get("certificate_verified"),
                        "yTb": (st.get("certificate_detail") or {}).get("yTb"),
                        "cert_support": (st.get("certificate_detail") or {}).get("n_support"),
                    }
                    print(tag, json.dumps(summary[tag]), flush=True)
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "lp_variants_summary.json").write_text(json.dumps(summary, indent=1))
        return 0
    if args.validate:
        print(json.dumps(validate(), indent=1))
    if args.control:
        print(json.dumps(run("control", not args.real, no_lowdeg=args.no_lowdeg)["stats"], indent=1))
    if args.main:
        r = run("main", not args.real, no_lowdeg=args.no_lowdeg)
        print(json.dumps(r["stats"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
