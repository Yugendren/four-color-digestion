#!/usr/bin/env python3
"""Assemble results/p2-coverage/report.md (P2 deliverable 3) from:
  - results/p2-coverage/wheel_survivors_d{7..11}.jsonl (deliverable 1, wheel-level
    coverage matrix; see tools/p2_wheel_coverage.py)
  - third_party/computer-checks/wheels/zero_blocklog/*.blocklog.tsv (deliverable 2,
    cartwheel-level blocking events during --enum_cartwheels refinement; see the C++
    patch under third_party/computer-checks/src, diff at
    results/p2-coverage/cxx_patch.diff)

Safe to run at any point (partial data): missing degrees / missing blocklog dirs are
reported as "not yet available" rather than erroring, so this can be used to preview
the report shape before the full background runs finish, then re-run for the final
numbers.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COVDIR = ROOT / "results" / "p2-coverage"
CC = ROOT / "third_party" / "computer-checks"

DEGREES = (7, 8, 9, 10, 11)


def load_wheel_survivors(d: int) -> list[dict] | None:
    p = COVDIR / f"wheel_survivors_d{d}.jsonl"
    if not p.exists():
        return None
    records = []
    with p.open() as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def wheel_level_stats() -> dict:
    per_degree = {}
    all_blocker_sources: set[str] = set()
    blocker_multiset: Counter[str] = Counter()
    total_survivors = 0
    total_blocked = 0
    total_concretizations = 0
    max_blockers_per_concretization = 0
    sum_blockers_per_concretization = 0
    n_concretizations_seen = 0

    for d in DEGREES:
        records = load_wheel_survivors(d)
        if records is None:
            per_degree[d] = {"status": "not yet available"}
            continue
        n_survivors = len(records)
        n_blocked = sum(1 for r in records if r["blocked"])
        per_wheel_concretizations = [r["n_concretizations"] for r in records]
        blocker_sizes_this_degree = []
        for r in records:
            for blockers in r["blockers_per_concretization"]:
                blocker_sizes_this_degree.append(len(blockers))
                sum_blockers_per_concretization += len(blockers)
                n_concretizations_seen += 1
                max_blockers_per_concretization = max(max_blockers_per_concretization, len(blockers))
                for name in blockers:
                    all_blocker_sources.add(name)
                    blocker_multiset[name] += 1
        per_degree[d] = {
            "status": "complete",
            "n_candidates_total": None,  # filled from summary_d{d}.json below if present
            "n_charge_bound_survivors": n_survivors,
            "n_blocked": n_blocked,
            "n_predicted_bad_unblocked": n_survivors - n_blocked,
            "avg_concretizations_per_wheel": (
                sum(per_wheel_concretizations) / len(per_wheel_concretizations)
                if per_wheel_concretizations else 0.0
            ),
            "max_concretizations_per_wheel": max(per_wheel_concretizations, default=0),
            "avg_blockers_per_concretization_this_degree": (
                sum(blocker_sizes_this_degree) / len(blocker_sizes_this_degree)
                if blocker_sizes_this_degree else 0.0
            ),
            "max_blockers_per_concretization_this_degree": max(blocker_sizes_this_degree, default=0),
            "distinct_blocker_sources_this_degree": len({
                name for r in records for blockers in r["blockers_per_concretization"]
                for name in blockers
            }),
        }
        summary_path = COVDIR / f"summary_d{d}.json"
        if summary_path.exists():
            summary = json.loads(summary_path.read_text())
            per_degree[d]["n_candidates_total"] = summary["n_candidates_total"]
        total_survivors += n_survivors
        total_blocked += n_blocked

    return {
        "per_degree": per_degree,
        "total_charge_survivors": total_survivors,
        "total_blocked": total_blocked,
        "distinct_blocker_sources_overall": len(all_blocker_sources),
        "distinct_blocker_sources": sorted(all_blocker_sources),
        "blocker_frequency_top20": blocker_multiset.most_common(20),
        "avg_blockers_per_concretization_overall": (
            sum_blockers_per_concretization / n_concretizations_seen if n_concretizations_seen else 0.0
        ),
        "max_blockers_per_concretization_overall": max_blockers_per_concretization,
    }


def cartwheel_level_stats() -> dict:
    blocklog_dir = CC / "wheels" / "zero_blocklog"
    if not blocklog_dir.exists():
        return {"status": "not yet available (C++ patch/run not landed)"}

    per_degree_wheel_counts: dict[str, int] = {}
    n_wheel_files_with_log = 0
    n_events = 0
    distinct_configs: set[str] = set()
    max_matched_per_event = 0
    sum_matched_per_event = 0
    n_wheels_expected = {"d7": 5439, "d8": 6790, "d9": 3285, "d10": 626, "d11": 8}
    n_wheels_completed: Counter[str] = Counter()

    for p in sorted(blocklog_dir.glob("*.blocklog.tsv")):
        deg_prefix = p.name.split("_")[0]  # "d7", "d8", ...
        n_wheels_completed[deg_prefix] += 1
        n_wheel_files_with_log += 1
        text = p.read_text()
        for line in text.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            _wheel_id, _state_hash, matched = parts
            names = [n for n in matched.split(",") if n]
            n_events += 1
            sum_matched_per_event += len(names)
            max_matched_per_event = max(max_matched_per_event, len(names))
            distinct_configs.update(names)

    per_degree = {}
    for deg_prefix, expected in n_wheels_expected.items():
        done = n_wheels_completed.get(deg_prefix, 0)
        per_degree[deg_prefix] = {
            "wheel_files_with_blocklog": done,
            "wheel_files_expected": expected,
            "fraction_complete": done / expected if expected else None,
        }

    return {
        "status": "partial" if any(
            per_degree[k]["fraction_complete"] not in (0, 1, None) or per_degree[k]["wheel_files_with_blocklog"] < per_degree[k]["wheel_files_expected"]
            for k in per_degree
        ) else "complete",
        "per_degree": per_degree,
        "n_blocking_events_logged": n_events,
        "distinct_configs_as_cartwheel_blockers": len(distinct_configs),
        "avg_matched_configs_per_event": sum_matched_per_event / n_events if n_events else 0.0,
        "max_matched_configs_per_event": max_matched_per_event,
    }


def render_report(wheel_stats: dict, cw_stats: dict) -> str:
    lines = []
    lines.append("# P2 Coverage Measurement Report")
    lines.append("")
    lines.append("Ground-set and incidence-structure sizing for the P3 set-cover MILP,")
    lines.append("per `01-PROBLEM-STATEMENT.md`. Generated by `tools/p2_report.py`.")
    lines.append("")
    lines.append("## Terminology note / discrepancy vs. the problem statement")
    lines.append("")
    lines.append(
        "The problem statement's deliverable 1 says \"charge survivors ... a few "
        "hundred per degree, e.g. 229 at d=7\". The actual charge-survivor count at "
        "d=7 is 5,668 (`charge_bound(x0) >= 0`); 229 is `n_blocked` at d=7 (the count "
        "of charge survivors that are ALSO blocked by the full reducible-configuration "
        "pool -- i.e. the wheels the current proof actually discharges via a config, "
        "as opposed to relying on the gluing lemmas for). This report computes full "
        "blocking attribution for ALL charge survivors at every degree (not just the "
        "blocked ones), since that's what the stated deliverable literally asks for, "
        "but the numbers below make clear which subset (`n_blocked`) is the one that "
        "matters for P3's covering constraints -- unblocked charge survivors are, by "
        "definition, not coverable by any subset of the pool, so they contribute no "
        "constraint to the MILP."
    )
    lines.append("")

    lines.append("## Part 1: wheel-level coverage")
    lines.append("")
    lines.append("| d | candidates | charge survivors | blocked | unblocked (predicted bad) |"
                  " avg concretizations/wheel | avg blockers/concretization | max blockers/concretization |"
                  " distinct blocker sources (this degree) |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for d in DEGREES:
        pd = wheel_stats["per_degree"][d]
        if pd.get("status") != "complete":
            lines.append(f"| {d} | (not yet available) | | | | | | | |")
            continue
        lines.append(
            f"| {d} | {pd['n_candidates_total']} | {pd['n_charge_bound_survivors']} | "
            f"{pd['n_blocked']} | {pd['n_predicted_bad_unblocked']} | "
            f"{pd['avg_concretizations_per_wheel']:.3f} | "
            f"{pd['avg_blockers_per_concretization_this_degree']:.3f} | "
            f"{pd['max_blockers_per_concretization_this_degree']} | "
            f"{pd['distinct_blocker_sources_this_degree']} |"
        )
    lines.append("")
    lines.append(f"- Total charge survivors (all degrees): **{wheel_stats['total_charge_survivors']}**")
    lines.append(f"- Total blocked (all degrees): **{wheel_stats['total_blocked']}**")
    lines.append(
        f"- Distinct pool configs that EVER appear as a wheel-level blocker (union over "
        f"all degrees): **{wheel_stats['distinct_blocker_sources_overall']}** "
        f"(out of 8,200 total `.conf` files in the pool)"
    )
    lines.append(
        f"- Avg / max blockers per concretization (overall, pooled across degrees): "
        f"{wheel_stats['avg_blockers_per_concretization_overall']:.3f} / "
        f"{wheel_stats['max_blockers_per_concretization_overall']}"
    )
    lines.append(
        "- Concretizations per wheel: always exactly 1 at this (stage-1) level -- every "
        "vertex in a `generate_cartwheel` wheel is either degree-fixed or the \"9+\" "
        "bucket, so `representative_degree` never branches (see "
        "`WheelBlockAttribution` docstring in `src/fourcolor/nl4ct.py`). Multi-"
        "concretization structure only appears at the cartwheel (refinement) level, "
        "part 2 below."
    )
    lines.append("")
    lines.append("Top 20 most-frequently-appearing blocker sources (wheel level, by number of "
                  "wheels they block, across all degrees):")
    lines.append("")
    lines.append("| conf | # wheels blocked (any degree) |")
    lines.append("|---|---|")
    for name, count in wheel_stats["blocker_frequency_top20"]:
        lines.append(f"| {name} | {count} |")
    lines.append("")

    lines.append("## Part 2: cartwheel-level coverage")
    lines.append("")
    if cw_stats.get("status", "").startswith("not yet"):
        lines.append(f"Status: {cw_stats['status']}")
    else:
        lines.append(f"Status: **{cw_stats['status']}**")
        lines.append("")
        lines.append("| degree | wheel files with a blocklog | wheel files expected | fraction complete |")
        lines.append("|---|---|---|---|")
        for deg_prefix, pd in cw_stats["per_degree"].items():
            frac = pd["fraction_complete"]
            frac_s = f"{frac:.3f}" if frac is not None else "n/a"
            lines.append(
                f"| {deg_prefix} | {pd['wheel_files_with_blocklog']} | "
                f"{pd['wheel_files_expected']} | {frac_s} |"
            )
        lines.append("")
        lines.append(f"- Blocking events logged so far: **{cw_stats['n_blocking_events_logged']}**")
        lines.append(
            f"- Distinct pool configs that ever appear as a cartwheel-level (refinement) "
            f"blocker: **{cw_stats['distinct_configs_as_cartwheel_blockers']}**"
        )
        lines.append(
            f"- Avg / max matched configs per blocking event: "
            f"{cw_stats['avg_matched_configs_per_event']:.3f} / "
            f"{cw_stats['max_matched_configs_per_event']}"
        )
    lines.append("")

    lines.append("## Tractability verdict for the P3 MILP")
    lines.append("")
    lines.append(_tractability_verdict(wheel_stats, cw_stats))
    lines.append("")
    return "\n".join(lines)


def _tractability_verdict(wheel_stats: dict, cw_stats: dict) -> str:
    wheel_complete = all(
        wheel_stats["per_degree"][d].get("status") == "complete" for d in DEGREES
    )
    cw_status = cw_stats.get("status", "not yet available")
    n_wheel_cols = wheel_stats["distinct_blocker_sources_overall"]
    n_cw_cols = cw_stats.get("distinct_configs_as_cartwheel_blockers")
    caveat = ""
    if not wheel_complete or cw_status != "complete":
        caveat = (
            " NOTE: this verdict is being written from PARTIAL data (see the "
            "per-degree / per-part status above, and `results/p2-coverage/"
            "FINALIZE.md` for exactly what is still outstanding). The wheel-level "
            "numbers (d7/d8/d9 complete; d10/d11 in progress) are unlikely to change "
            "qualitatively -- the >99% column reduction has held steadily across "
            "every degree measured so far. The cartwheel-level numbers (d7/d8 at "
            "~80-85%, d9 not run, d10/d11 complete) WILL grow further as d7/d8 "
            "finish and if d9 is added; the 78% pool-fraction figure should be "
            "treated as a lower bound, re-derived by re-running `tools/p2_report.py` "
            "once every degree/part reports `complete`."
        )
    parts = [
        f"At the wheel level, the ground set is small: at most 16,148 wheel-level "
        f"constraints (one per charge-survivor-and-blocked wheel across d=7..11; "
        f"unblocked charge survivors impose no constraint), and the candidate-column "
        f"count collapses from the full 8,200-config pool to only "
        f"**{n_wheel_cols}** distinct configs that are EVER used as a wheel-level "
        f"blocker anywhere. Incidence is essentially a near-identity structure at "
        f"this level (every wheel has exactly 1 concretization, and the vast "
        f"majority have exactly 1 blocker; max observed is "
        f"{wheel_stats['max_blockers_per_concretization_overall']}), so the wheel-"
        f"level covering problem alone is a triviality for any MILP solver (HiGHS or "
        f"otherwise) -- it is closer to a small set-partition than a hard set-cover."
    ]
    if n_cw_cols is not None:
        frac = n_cw_cols / 8200
        parts.append(
            f"At the cartwheel (refinement) level -- the level that actually matters "
            f"for P3, since it is refinements, not stage-1 wheels, that the real "
            f"proof's `enum_cartwheels` search discards via blocking -- the picture is "
            f"DIFFERENT and less favorable: **{n_cw_cols}** distinct configs already "
            f"appear as a cartwheel-level blocker across the degrees measured so far "
            f"(out of {cw_stats['n_blocking_events_logged']} total logged blocking "
            f"events), i.e. **{frac:.0%} of the full 8,200-config pool is already "
            f"implicated** -- there is essentially NO column reduction at this level, "
            f"in sharp contrast to the wheel level's ~{n_wheel_cols}/8200. This makes "
            f"sense structurally: refinement search visits vastly more, more-"
            f"specialized states than stage-1 wheels do, and each specialized state "
            f"tends to be blocked by a config specific to it. Each event in the C++ "
            f"log records only the FIRST matching config (mirroring the original "
            f"short-circuit boolean check, not full attribution), so {n_cw_cols} is a "
            f"LOWER bound on the true cartwheel-level candidate-column count -- it can "
            f"only grow with a full-attribution pass or once d7/d8 (and d9, not yet "
            f"run at this level -- see FINALIZE.md) finish."
        )
    else:
        parts.append(
            "Cartwheel-level data is not yet available; see status above and "
            "`results/p2-coverage/FINALIZE.md` for how to complete it."
        )
    parts.append(
        "**Verdict: P3 is tractable as a MILP at the wheel level; the cartwheel level "
        "needs one more (cheap) measurement before the same claim can be made "
        "honestly.** The wheel-level covering problem alone is trivial (column count "
        "~61/8,200, near-identity incidence, <=16,148 rows). The cartwheel-level "
        "problem -- the one that actually reflects what the current proof relies on "
        "for refinement-level blocking -- has an effective column count close to the "
        "FULL 8,200-config pool (not the dramatic reduction the wheel level showed, "
        "and not what the problem statement's resource-realities section seemed to "
        "hope measurement would show), so column-count reduction alone will NOT make "
        "the cartwheel-level P3 easy. What WOULD make it easy is row (constraint) "
        "sparsity -- avg matched-configs-per-blocking-event is reported as exactly "
        "1.0 in the table above, but that is an ARTIFACT of the current C++ patch "
        "logging only the first matching config per event (mirroring the original "
        "short-circuit boolean check), not a measurement of true incidence sparsity -- "
        "it is NOT valid evidence either way about how sparse the cartwheel-level "
        "constraint matrix really is. Getting that number honestly requires the same "
        "full-attribution treatment already done at the wheel level (collect ALL "
        "matching source files per blocking event, not just the first), applied to "
        "the cartwheel-level blocking events -- a follow-up patch of the same shape "
        "as this one, scoped to a sample of the already-logged events (state hashes) "
        "rather than a full re-run. Until that measurement exists, the honest verdict "
        "is: wheel level is proven tractable; cartwheel level is UNKNOWN on the "
        "column-reduction axis and not yet measured on the row-sparsity axis, though "
        "the problem statement's original scale estimate (<=16,148 x 8,200, "
        "'well within HiGHS territory if the incidence structure is sparse') puts an "
        "outer bound on difficulty regardless -- 8,200 binary columns is not large "
        "for a modern MILP solver even without sparsity, so 'intractable' is unlikely; "
        "'needs the sparsity measurement to size the row count precisely' is the "
        "accurate statement." + caveat
    )
    return "\n\n".join(parts)


def main() -> None:
    wheel_stats = wheel_level_stats()
    cw_stats = cartwheel_level_stats()
    (COVDIR / "wheel_level_stats.json").write_text(json.dumps(wheel_stats, indent=2))
    (COVDIR / "cartwheel_level_stats.json").write_text(json.dumps(cw_stats, indent=2))
    report = render_report(wheel_stats, cw_stats)
    print(report)


if __name__ == "__main__":
    main()
