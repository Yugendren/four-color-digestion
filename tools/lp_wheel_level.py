#!/usr/bin/env python3
"""Cutting-plane feasibility check for the STRONG (wheel-level, max-of-affine) reading
of the discharging argument -- and why it is the WRONG encoding.

QUESTION
--------
``tools/lp_discharge.py`` encodes the true necessary condition, which is a statement
about fully refined LEAVES of the search tree: a surviving leaf must have charge <= 0
(strict < 0 in the cases where the leaf is not allowed to survive at all). Survivors
with charge == 0 are explicitly PERMITTED there; the module docstring explains why (the
three gluing lemmas mop them up).

A naive reading of "discharging closes the argument" instead demands the much stronger
statement: every stage-1 "possible bad wheel" (``enum_possible_bad_wheels`` output --
the wheel BEFORE any degree refinement, i.e. what's on disk under ``wheels/d{7..11}``)
must be charge-killed outright, so that ``enum_possible_bad_wheels`` returns the EMPTY
set for every hub degree 7..11 and the refinement/leaf search never even starts. This
module measures whether THAT (over-strong) condition is achievable for some amount
vector x, and documents that it is not the right encoding of "the argument closes":
even in the *published* amounts x0, thousands of stage-1 wheels survive by design --
that is the entire point of doing leaf-level refinement instead of stopping here.

THE WHEEL-LEVEL BOUND IS MAX-OF-AFFINE, NOT LINEAR
---------------------------------------------------
Per ``src/fourcolor/nl4ct.py`` (``charge_bound_symbolic`` / ``ChargeBoundForm``):

    f_w(x) = 10*(6-d) - <out_flags, x> + sum_i max(0, max_{c in candidates_i} <flag_c, x>)

``nl4ct.amount_of_possible_charge_send`` initializes ``amount = 0`` and only ever
``max()``s upward, so there is an IMPLICIT ZERO option in every per-spoke max --
"the hub may receive nothing across this spoke" is always on the table, even when the
combined-rule candidate list is nonempty. ``charge_bound_symbolic.in_choices`` does
*not* include that zero vector; this module adds it explicitly to every spoke's choice
list before doing anything else with it. See ``--report-zero-option`` /
:func:`build_wheel_forms` for the empirical check of whether this actually changes any
answer (spoiler, argued and confirmed below: with the LP's standing hypothesis x >= 0
and every ``combined_flag`` a 0/1 vector, every real candidate's dot product with x is
already >= 0 = dot(zero, x), so adding zero can only ever matter when a spoke's
candidate list is empty to begin with -- otherwise it is a no-op on the VALUE of the
max, though it does matter for well-definedness of "max of an empty list").

Since ``max_i(...) < 0`` (or ``<= 0``) holds iff EVERY selection in the max is
``< 0`` (``<= 0``), the feasible set ``{x >= 0 : f_w(x) < 0 for every wheel w}`` is
LP-representable, but only with exponentially many rows (one per combination of
per-spoke selections). This module solves it by CUTTING-PLANE / constraint generation:
start from a small row set, solve, and for every wheel whose TRUE (argmax-evaluated)
bound still violates the target, add the single linear row corresponding to that
argmax selection; repeat until no wheel violates (FEASIBLE) or the LP itself becomes
infeasible (INFEASIBLE, witnessed by an exact Farkas certificate via
``lp_discharge.farkas_check``/``exact_certificate_from_ray``).

WITHOUT THE d<=6 ROWS THE LP IS VACUOUS
----------------------------------------
Exactly as in ``lp_discharge``: the hub degrees enumerated here are 7..11, where the
initial charge ``10*(6-d)`` is already negative, so ``x = 0`` trivially satisfies every
wheel-level row. The lower bounds on x that make the LP meaningful come from the other
half of the argument (degree-5/6 hubs must give away all/none of their initial charge);
this module reuses ``lp_discharge.lowdeg_rows`` verbatim for that half (same cache
files, same semantics -- see that module's docstring for the derivation).

ROW SEMANTICS: INT VS REAL
---------------------------
Rule amounts are C++ ``int``s (tenths of a unit), so "the strong condition" of
``f_w(x) < 0`` is, for integral x, ``f_w(x) <= -1``. ``--real`` drops integrality and
uses the literal ``f_w(x) <= 0`` (weaker requirement on x, i.e. a logically STRONGER
claim if it still comes back INFEASIBLE, and a weaker one if FEASIBLE).

CAVEAT: THE ON-DISK WHEEL SET IS ITSELF x0-DEPENDENT
------------------------------------------------------
``wheels/d{7..11}/*.cartwheel`` are the SURVIVORS of stage-1 pruning AT x0 (i.e. exactly
the wheels with ``charge_bound(w, x0) >= 0`` and not blocked by a reducible
configuration -- see ``nl4ct.py``'s module docstring, "A wheel is a member of
wheels/d{d}/*.cartwheel iff..."). They are NOT the full necklace enumeration: for a
different x, entirely different necklaces (never generated at x0, because the C++'s
own prune step never emitted them) could become the survivors. Consequently:

  - A FEASIBLE verdict from this tool is only SUGGESTIVE: it exhibits an x under which
    the specific wheels observed at x0 are all killed, but says nothing about whether
    some other x-dependent necklace would then survive instead.
  - An INFEASIBLE verdict is valid ONLY relative to this fixed wheel set: it proves no
    x kills every wheel in ``wheels/d{7..11}`` (as currently enumerated at x0), which is
    already enough to refute "the argument closes by stage-1 pruning alone" for x0
    itself, but is not, in general, a statement about every possible x's own stage-1
    survivor set.

This is a genuinely different (and weaker, on the feasible side) monotonicity story
than ``lp_discharge``'s leaf-level argument, which has an explicit monotonicity lemma
(any leaf produced at x0 remains a valid constraint for every x >= 0). No such lemma is
claimed or used here for the wheel LEVEL; see the docstring of ``lp_discharge.py``
("WHY A LEAF FOUND AT x0 IS A VALID CONSTRAINT FOR EVERY x") for the leaf-level version
of the argument this module deliberately does NOT attempt to make.

MEMORY / PERFORMANCE
---------------------
~16k wheels x up to ~700 candidate combined rules per spoke: the symbolic form
(``out_flags``, per-spoke candidate flag matrices, constant) is computed ONCE per wheel
via ``nl4ct.charge_bound_symbolic`` and cached as small integer numpy arrays
(:class:`WheelForm`); every cutting-plane iteration only recomputes per-spoke argmax dot
products against the current LP solution, not the symbolic form itself. Measured: build
is ~70-90s and ~500MB of int8 arrays for ~16k wheels on this machine (well under the
~6GB budget); no full-graph or homomorphism work is repeated across iterations.

USAGE
-----
    python tools/lp_wheel_level.py --control                # full-pool stage-1 wheels
    python tools/lp_wheel_level.py --main                    # ring<=14 pool
    python tools/lp_wheel_level.py --main --real              # drop integrality
    python tools/lp_wheel_level.py --control --max-iter 50
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import lp_discharge as L  # noqa: E402  (Row, rhs_of, solve_lp, lowdeg_rows, farkas_check,
# exact_certificate_from_ray, load_rules, x0_of, OUT_DIR)
from fourcolor import nl4ct as N  # noqa: E402

OUT_DIR = L.OUT_DIR

FULL_POOL_WHEEL_DIRS = [ROOT / f"third_party/computer-checks/wheels/d{d}" for d in range(7, 12)]
FULL_POOL_DIR = ROOT / "third_party/computer-checks/reducible-configurations/D"
FULL_POOL_COMBINED_DIR = ROOT / "third_party/computer-checks/combined_rules/non_blocked"

R14_WHEEL_DIRS = [
    ROOT / f"results/p3/runs/steinberger-s1/work/wheels/d{d}" for d in range(7, 12)
]
R14_POOL_DIR = ROOT / "build/steinberger-pool-r14/D"
R14_COMBINED_DIR = ROOT / "results/p3/runs/steinberger-s1/work/combined_rules/non_blocked"


@dataclass(frozen=True)
class ModeConfig:
    wheel_dirs: list[Path]
    pool_dir: Path
    combined_dir: Path


def mode_config(mode: str) -> ModeConfig:
    if mode == "control":
        return ModeConfig(FULL_POOL_WHEEL_DIRS, FULL_POOL_DIR, FULL_POOL_COMBINED_DIR)
    if mode == "main":
        return ModeConfig(R14_WHEEL_DIRS, R14_POOL_DIR, R14_COMBINED_DIR)
    raise ValueError(mode)


# --------------------------------------------------------------------------
# Wheel forms: compute nl4ct.charge_bound_symbolic once per wheel, add the
# implicit zero option, cache as small integer numpy arrays.
# --------------------------------------------------------------------------


@dataclass
class WheelForm:
    name: str
    d: int
    spoke_degs: tuple[int, ...]
    constant: int
    out_flags: np.ndarray  # (n_rules,) int64
    spoke_choices: list[np.ndarray]  # per spoke: (n_cand_i + 1, n_rules) int8, zero row appended
    raw_choice_counts: tuple[int, ...]  # per spoke, BEFORE the zero row was added


def _wheel_paths(wheel_dirs) -> list[Path]:
    paths: list[Path] = []
    for d in wheel_dirs:
        p = Path(d)
        if p.is_dir():
            paths.extend(sorted(p.glob("*.cartwheel")))
    return paths


def build_wheel_forms(wheel_paths, rules, combined_rules) -> list[WheelForm]:
    n_rules = len(rules)
    zero_row = np.zeros((1, n_rules), dtype=np.int8)
    forms: list[WheelForm] = []
    for p in wheel_paths:
        w = N.parse_cartwheel_file(p)
        f = N.charge_bound_symbolic(w, rules, combined_rules)
        spoke_choices = []
        raw_counts = []
        for choices in f.in_choices:
            raw_counts.append(len(choices))
            if choices:
                arr = np.asarray(choices, dtype=np.int8)
                arr = np.vstack([arr, zero_row])
            else:
                arr = zero_row.copy()
            spoke_choices.append(arr)
        forms.append(
            WheelForm(
                name=p.name,
                d=f.d,
                spoke_degs=N.spoke_degree_sequence(w),
                constant=f.constant,
                out_flags=np.asarray(f.out_flags, dtype=np.int64),
                spoke_choices=spoke_choices,
                raw_choice_counts=tuple(raw_counts),
            )
        )
    return forms


def zero_option_report(forms: list[WheelForm]) -> dict:
    """Empirical check of whether the implicit-zero fix changes anything.

    With the LP's standing hypothesis x >= 0 and every candidate a 0/1 flag vector,
    dot(candidate, x) >= 0 = dot(zero, x) always, so the zero row can only ever change
    the SELECTED max when a spoke's real candidate list is empty (in which case it is
    not merely a value change but the difference between a well-defined 0 and an
    undefined "max of an empty list"). We report both counts.
    """
    n_wheels = len(forms)
    n_spokes = sum(len(f.raw_choice_counts) for f in forms)
    empty_spokes = sum(1 for f in forms for c in f.raw_choice_counts if c == 0)
    wheels_with_empty_spoke = sum(
        1 for f in forms if any(c == 0 for c in f.raw_choice_counts)
    )
    return {
        "n_wheels": n_wheels,
        "n_spokes": n_spokes,
        "empty_candidate_spokes": empty_spokes,
        "wheels_with_an_empty_candidate_spoke": wheels_with_empty_spoke,
        "zero_option_can_change_the_max": empty_spokes > 0,
        "note": (
            "candidates are 0/1 flag vectors and x >= 0 always holds (LP variable "
            "bounds), so dot(candidate,x) >= 0 = dot(zero,x) whenever a candidate "
            "exists; the zero row can only change the selected VALUE when a spoke's "
            "candidate list is empty to begin with. Still added unconditionally "
            "(matches nl4ct.amount_of_possible_charge_send's actual semantics, and "
            "guards well-definedness even in the empty case)."
        ),
    }


def evaluate_wheel(form: WheelForm, x: np.ndarray) -> tuple[float, np.ndarray]:
    """True (argmax-evaluated) f_w(x), and the coefficient vector of the row that
    argmax selection induces (``constant + <coeffs, x> == f_w(x)`` by construction)."""
    n_rules = x.shape[0]
    selected_sum = np.zeros(n_rules, dtype=np.int64)
    for arr in form.spoke_choices:
        dots = arr @ x
        idx = int(np.argmax(dots))
        selected_sum += arr[idx]
    out_dot = float(form.out_flags @ x)
    in_dot = float(selected_sum @ x)
    f_val = form.constant - out_dot + in_dot
    coeffs = selected_sum - form.out_flags
    return f_val, coeffs


def make_row(form: WheelForm, coeffs: np.ndarray) -> "L.Row":
    return L.Row(
        coeffs=tuple(int(c) for c in coeffs),
        constant=form.constant,
        strict=True,  # the strong condition is f_w(x) < 0 for EVERY wheel, unconditionally
        d=form.d,
        spoke_degs=form.spoke_degs,
        sources=(form.name,),
    )


def is_violated(row: "L.Row", x, integral: bool) -> bool:
    """Does ``row`` (i.e. f_w(x)) still fail the strong condition at ``x``?

    NOTE: this compares ``row.value_at(x)`` (== constant + <coeffs, x> == f_w(x))
    against the LIMIT directly (mirrors ``lp_discharge.run``'s own x0-violation check),
    NOT against ``L.rhs_of(row, integral)`` -- ``rhs_of`` returns ``limit - constant``,
    the right-hand side for the LP's ``<coeffs, x> <= rhs`` row (which already has the
    constant moved to the other side), so comparing ``value_at`` (which still HAS the
    constant folded in) to ``rhs_of``'s output directly would double-count it.
    """
    limit = -1 if (row.strict and integral) else 0
    return row.value_at(x) > limit


# --------------------------------------------------------------------------
# Cutting-plane driver
# --------------------------------------------------------------------------


def run(
    mode: str,
    integral: bool,
    max_iter: int = 200,
    dump: bool = True,
) -> dict:
    t_start = time.time()
    cfg = mode_config(mode)
    rules = L.load_rules()
    x0 = L.x0_of(rules)
    n_rules = len(rules)

    combined_rules = N.load_combined_rules(cfg.combined_dir, n_rules)
    wheel_paths = _wheel_paths(cfg.wheel_dirs)
    n_wheels = len(wheel_paths)

    t0 = time.time()
    forms = build_wheel_forms(wheel_paths, rules, combined_rules)
    build_s = time.time() - t0
    zero_report = zero_option_report(forms)

    ld_rows, ld_counts = L.lowdeg_rows(
        cfg.pool_dir, rules, cache=OUT_DIR / f"lowdeg_rows_{mode}.json"
    )
    rows: dict[tuple, L.Row] = {r.key(): r for r in ld_rows}
    n_lowdeg_rows = len(rows)

    # Step 1(b): one initial row per wheel, using the argmax selection at x0. Also
    # doubles as the x0-violation sanity check: every wheel here is on disk BECAUSE
    # charge_bound(w, x0) >= 0 (see nl4ct.py), so this count should equal n_wheels.
    x0_arr = np.array(x0, dtype=float)
    x0_violations = []
    for f in forms:
        f_val, coeffs = evaluate_wheel(f, x0_arr)
        row = make_row(f, coeffs)
        if is_violated(row, x0, integral):
            x0_violations.append(f.name)
        rows[row.key()] = row

    n_vars = n_rules
    log: list[dict] = []
    status = None
    x_sol = None
    cert = None
    final_status = None

    for it in range(1, max_iter + 1):
        t_it = time.time()
        row_list = list(rows.values())
        status, x_sol, ray = L.solve_lp(row_list, n_vars, integral)

        if status == "INFEASIBLE":
            wall = time.time() - t_it
            log.append(
                {"iteration": it, "n_rows": len(row_list), "n_violated": None,
                 "status": status, "wall_s": wall}
            )
            print(f"[{mode}] iter {it}: rows={len(row_list)} status=INFEASIBLE wall={wall:.2f}s")
            y = L.exact_certificate_from_ray(row_list, ray, integral)
            if y is None:
                cert = {"certificate": None, "certificate_verified": False}
            else:
                ok, detail = L.farkas_check(row_list, y, integral)
                support = [i for i, v in enumerate(y) if v != 0]
                cert = {
                    "certificate_verified": ok,
                    "certificate_detail": detail,
                    "certificate": {
                        "integral": integral,
                        "n_rows": len(row_list),
                        "multipliers": [[i, str(y[i])] for i in support],
                        "rows": [
                            {
                                "index": i,
                                "coeffs": list(row_list[i].coeffs),
                                "constant": row_list[i].constant,
                                "strict": row_list[i].strict,
                                "rhs": L.rhs_of(row_list[i], integral),
                                "d": row_list[i].d,
                                "spoke_degs": list(row_list[i].spoke_degs),
                                "source": row_list[i].sources[0] if row_list[i].sources else None,
                            }
                            for i in support
                        ],
                    },
                }
            final_status = "INFEASIBLE"
            break

        if status != "FEASIBLE":
            wall = time.time() - t_it
            log.append(
                {"iteration": it, "n_rows": len(row_list), "n_violated": None,
                 "status": status, "wall_s": wall}
            )
            print(f"[{mode}] iter {it}: rows={len(row_list)} status={status} (unexpected) wall={wall:.2f}s")
            final_status = status
            break

        x_arr = np.array(x_sol, dtype=float)
        violated: list[tuple[WheelForm, "L.Row"]] = []
        for f in forms:
            f_val, coeffs = evaluate_wheel(f, x_arr)
            row = make_row(f, coeffs)
            limit = -1 if integral else 0
            if row.value_at(x_sol) > limit + 1e-7:
                violated.append((f, row))

        wall = time.time() - t_it
        log.append(
            {"iteration": it, "n_rows": len(row_list), "n_violated": len(violated),
             "status": status, "wall_s": wall}
        )
        print(
            f"[{mode}] iter {it}: rows={len(row_list)} violated={len(violated)} "
            f"status={status} wall={wall:.2f}s"
        )

        if not violated:
            final_status = "FEASIBLE"
            break

        for f, row in violated:
            rows[row.key()] = row
    else:
        final_status = "MAX_ITER_EXCEEDED"

    total_s = time.time() - t_start
    stats = {
        "mode": mode,
        "integral": integral,
        "max_iter": max_iter,
        "wheel_dirs": [str(d) for d in cfg.wheel_dirs],
        "pool_dir": str(cfg.pool_dir),
        "combined_dir": str(cfg.combined_dir),
        "n_wheels": n_wheels,
        "build_s": build_s,
        "zero_option_report": zero_report,
        "lowdeg_counts": ld_counts,
        "n_lowdeg_rows": n_lowdeg_rows,
        "x0_violations": len(x0_violations),
        "x0_violations_equal_n_wheels": len(x0_violations) == n_wheels,
        "n_iterations": len(log),
        "n_rows_final": len(rows),
        "final_status": final_status,
        "log": log,
        "total_s": total_s,
    }
    if final_status == "FEASIBLE":
        stats["feasible_x"] = [round(v, 9) for v in x_sol]
    if cert is not None:
        stats.update(cert)

    if dump:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        tag = f"{mode}{'-real' if not integral else ''}"
        (OUT_DIR / f"wheel_level_{tag}_stats.json").write_text(json.dumps(stats, indent=1))

    summary = (
        f"[{mode}{'(real)' if not integral else ''}] n_wheels={n_wheels} "
        f"x0_violations={len(x0_violations)}/{n_wheels} "
        f"iterations={len(log)} rows_final={len(rows)} "
        f"status={final_status} total={total_s:.1f}s "
        f"zero_option_matters={zero_report['zero_option_can_change_the_max']}"
    )
    print(summary)
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--control", action="store_true")
    ap.add_argument("--main", action="store_true")
    ap.add_argument("--real", action="store_true", help="drop integrality: rows become <= 0 instead of <= -1")
    ap.add_argument("--max-iter", type=int, default=200)
    args = ap.parse_args(argv)
    if args.control:
        run("control", not args.real, max_iter=args.max_iter)
    if args.main:
        run("main", not args.real, max_iter=args.max_iter)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
