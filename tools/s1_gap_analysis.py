#!/usr/bin/env python3
"""Steinberger S1: failure/gap analysis for the ring<=14 restricted-pool pipeline run.

Experiment S1 (see ``03-MASS-LAW-PROGRAM.md`` M5) re-runs the full 2026 proof pipeline
(``tools/p3_pipeline_run.sh``) against the pool restricted to ring size <= 14
(``tools/s1_build_pool.py``). A PASS answers Steinberger's open question YES. This
script's job is the other branch: given the run directory, localize *exactly* where a
ring<=14 proof diverges from the full-pool proof, at all three stages.

  (a) COMBINED RULES (Lemma A.1/A.2, charge structure). Baseline: 1,832 combined rules,
      671 surviving as ``non_blocked``. Dropping ring>14 configs can only ever UNBLOCK
      combos, so ``non_blocked`` can only grow; each extra one is a "revived combo",
      i.e. a discharging combination the full pool killed and this pool does not --
      the charge accounting downstream is genuinely different. Each revived combo is
      attributed to the ring>14 configs that used to block it, using the full (not
      first-match) attribution in ``results/p3/combo_blockers.jsonl``, which was
      validated 1,832/1,832 against ground truth (see ``tools/p3_combo_blockers.py``).
      The same attribution yields an independent PREDICTION of the revived set, which
      is cross-checked against what the run actually produced.

  (b) WHEELS (stage-2 pruning). Baseline per-degree counts 5439/6790/3285/626/8 for
      d7..d11 and 10,094 bad cartwheels total. Deltas are reported per degree, and
      predicted from the full attribution in
      ``results/p2-coverage/wheel_survivors_d{7..11}.jsonl``: a blocked wheel revives
      under the restriction iff some representative-degree concretization has no
      blocker of ring <= 14. Predicted-vs-observed disagreement is flagged (it would
      mean the restriction changed something beyond simple blocker loss).

  (c) GLUING (Lemma A.4/A.5/A.6 -- ``check_deg8`` / ``check_7triangle`` / ``check_deg7``).
      This is the stage that killed batch1 (``assert(combined.size() == 0)`` in
      ``check88``, exit 134). We report which check failed and where, then answer the
      question that matters: WHICH glued composites lost their blockers -- the list of
      objects any ring<=14 proof must handle differently.

      Two modes:
        * STATIC (default, no extra compute): reads the full-pool gluing blocklog
          ``third_party/computer-checks/wheels/glue_blocklog/check_*.gluelog.tsv``
          (14.6M events, produced by ``main_gluelog`` -- the instrumentation described
          in ``results/p2-coverage/cxx_patch.diff`` and now in-tree at
          ``third_party/computer-checks/src/combine_cartwheel.cpp``). Each line is
          ``<check>\\t<state_hash>\\t<name1,name2,...>``, one name per representative-
          degree concretization of the glued composite, FIRST MATCH only. Hence: a
          composite is *definitely still blocked* iff every logged name has ring <= 14,
          and *at risk* otherwise. At-risk is therefore an UPPER bound on the truly
          lost set (a ring>14 first match may be shadowing a ring<=14 match).
        * EXACT (``--s1-gluelog-dir``): if you re-run ``main_gluelog`` against this
          run's cartwheels and the restricted pool, the composites present in the
          baseline log but absent from the S1 log are exactly the ones that lost every
          blocker. The command to produce it is printed by this script.

Read-only over the run directory: nothing here writes inside ``--run-dir``; all output
goes to ``--out`` (default ``results/steinberger-s1/``).

Usage:
    tools/s1_gap_analysis.py                                  # defaults to the S1 run
    tools/s1_gap_analysis.py --run-dir results/p3/runs/steinberger-s1 --max-ring 14
    tools/s1_gap_analysis.py --s1-gluelog-dir results/steinberger-s1/gluelog
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from s1_build_pool import ring_index  # noqa: E402

CC = ROOT / "third_party" / "computer-checks"
BASELINE_NON_BLOCKED = CC / "combined_rules" / "non_blocked"
BASELINE_ALL = CC / "combined_rules" / "all"
BASELINE_GLUELOG = CC / "wheels" / "glue_blocklog"
COMBO_BLOCKERS = ROOT / "results" / "p3" / "combo_blockers.jsonl"
P2_DIR = ROOT / "results" / "p2-coverage"

WHEEL_DEGREES = (7, 8, 9, 10, 11)
BASELINE_WHEELS = {7: 5439, 8: 6790, 9: 3285, 10: 626, 11: 8}
BASELINE_N_COMBINED_ALL = 1832
BASELINE_N_NON_BLOCKED = 671
BASELINE_N_BAD_CARTWHEELS = 10094
CHECKS = ("check_deg8", "check_7triangle", "check_deg7")
CHECK_DONE_MARKER = {
    "check_deg8": "Finished checking degree 8",
    "check_7triangle": "Finished checking 7-triangles",
    "check_deg7": "Finished checking degree 7",
}


# --------------------------------------------------------------------------------------
# parsing helpers
# --------------------------------------------------------------------------------------
# Ring lookups below use ``rings.get(name, 0)``: an unknown config name (a data bug --
# every blocker should be a pool .conf stem) defaults to ring 0, i.e. "still in the
# restricted pool", so it can never manufacture a spurious revival/at-risk report. All
# deltas therefore stay conservative in the direction of "nothing changed".
def norm_rule(text: str) -> str:
    """Whitespace-normalized combined-rule content, used as structural identity across
    independently-numbered combine_rules runs (same key as tools/p3_combo_blockers.py)."""
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip() != ""]
    return "\n".join(lines)


def rule_contents(rule_dir: Path) -> dict[str, str]:
    """Map combo file stem -> normalized content, over a ``*.combined_rule`` directory."""
    return {p.stem: norm_rule(p.read_text()) for p in sorted(rule_dir.glob("*.combined_rule"))}


def combo_flag(text: str) -> str:
    """The trailing 01 bitstring F naming which base rules are combined (FORMAT.md)."""
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip() != ""]
    return lines[-1] if lines else ""


def parse_check_log(path: Path, check: str) -> dict:
    """Extract outcome + counts from a gluing-check log.

    Returns ``finished`` (the stage's completion line is present), any assertion text
    with its source location, and the cartwheel/configuration counts the check loaded.
    """
    info: dict = {
        "check": check,
        "log": str(path),
        "present": path.exists(),
        "finished": False,
        "assertion": None,
        "assert_function": None,
        "assert_file": None,
        "assert_line": None,
        "n_cartwheels_loaded": None,
        "n_configurations_loaded": None,
        "n_cartwheels_remaining": None,
    }
    if not path.exists():
        return info
    text = path.read_text(errors="replace")
    info["finished"] = CHECK_DONE_MARKER[check] in text

    m = re.search(r"Total (\d+) cartwheels loaded", text)
    if m:
        info["n_cartwheels_loaded"] = int(m.group(1))
    m = re.search(r"Total (\d+) configurations loaded", text)
    if m:
        info["n_configurations_loaded"] = int(m.group(1))
    m = re.search(r"(\d+) cartwheels remain", text)
    if m:
        info["n_cartwheels_remaining"] = int(m.group(1))

    m = re.search(
        # The asserted expression itself contains parentheses (e.g.
        # "combined.size() == 0"), so match lazily up to the ", function" tail.
        r"Assertion failed: \((?P<expr>.*?)\), function (?P<fn>\w+), "
        r"file (?P<file>[\w.]+), line (?P<line>\d+)",
        text,
    )
    if m:
        info["assertion"] = m.group("expr")
        info["assert_function"] = m.group("fn")
        info["assert_file"] = m.group("file")
        info["assert_line"] = int(m.group("line"))
    elif "Assertion failed" in text:
        info["assertion"] = next(
            ln.strip() for ln in text.splitlines() if "Assertion failed" in ln
        )
    return info


def parse_gluelog(path: Path) -> dict[str, list[str]]:
    """Parse a ``*.gluelog.tsv`` into ``state_hash -> matched blocker names``.

    Each line is ``<check>\\t<state_hash>\\t<name1,name2,...>``: one FIRST-MATCH blocker
    name per representative-degree concretization of the glued composite. Repeated
    hashes (the same composite reached along different glue darts) are merged by union;
    the emission is deterministic, so this only deduplicates.
    """
    per_hash: dict[str, list[str]] = {}
    with path.open() as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 3:
                continue
            _, state_hash, names_field = parts
            names = [n for n in names_field.split(",") if n]
            prev = per_hash.get(state_hash)
            if prev is None:
                per_hash[state_hash] = names
            else:
                for n in names:
                    if n not in prev:
                        prev.append(n)
    return per_hash


# --------------------------------------------------------------------------------------
# (a) combined-rules delta
# --------------------------------------------------------------------------------------
def analyze_combos(run_dir: Path, rings: dict[str, int], max_ring: int) -> dict:
    run_nb_dir = run_dir / "work" / "combined_rules" / "non_blocked"
    run_all_dir = run_dir / "work" / "combined_rules" / "all"
    # p3_pipeline_run.sh pre-creates the output directories, so directory existence is
    # not evidence the stage ran; DONE_combine is.
    out: dict = {
        "stage_reached": (run_dir / "DONE_combine").exists() and run_nb_dir.is_dir(),
        "baseline_n_all": BASELINE_N_COMBINED_ALL,
        "baseline_n_non_blocked": BASELINE_N_NON_BLOCKED,
    }

    # Prediction from full attribution (independent of the run).
    predicted: list[dict] = []
    all_by_content = {c: s for s, c in rule_contents(BASELINE_ALL).items()}
    if COMBO_BLOCKERS.exists():
        with COMBO_BLOCKERS.open() as fh:
            for line in fh:
                rec = json.loads(line)
                if not rec["blocked"]:
                    continue
                dead = [
                    conc
                    for conc in rec["blockers_per_concretization"]
                    if all(rings.get(b, 0) > max_ring for b in conc)
                ]
                if dead:
                    predicted.append(
                        {
                            "combo_id": rec["combo_id"],
                            "amount": rec["amount"],
                            "n_concretizations": rec["n_concretizations"],
                            "lost_concretizations": len(dead),
                            "sole_blockers_above_ring": sorted(
                                {b for conc in dead for b in conc}
                            ),
                        }
                    )
    out["predicted_revived"] = predicted
    out["n_predicted_revived"] = len(predicted)
    out["predicted_n_non_blocked"] = BASELINE_N_NON_BLOCKED + len(predicted)

    if not out["stage_reached"]:
        return out

    baseline_nb = set(rule_contents(BASELINE_NON_BLOCKED).values())
    run_nb = rule_contents(run_nb_dir)
    run_nb_contents = set(run_nb.values())
    out["n_all"] = len(list(run_all_dir.glob("*.combined_rule"))) if run_all_dir.is_dir() else None
    out["n_non_blocked"] = len(run_nb)
    out["delta_non_blocked"] = len(run_nb) - BASELINE_N_NON_BLOCKED

    revived_contents = run_nb_contents - baseline_nb
    # Should be empty: shrinking the pool cannot re-block anything.
    lost_contents = baseline_nb - run_nb_contents

    revived: list[dict] = []
    predicted_ids = {p["combo_id"] for p in predicted}
    for content in sorted(revived_contents):
        combo_id = all_by_content.get(content)
        revived.append(
            {
                "combo_id": combo_id,
                "rule_flag": combo_flag(content),
                "predicted": combo_id in predicted_ids,
            }
        )
    out["revived"] = revived
    out["n_revived"] = len(revived)
    out["n_unexpectedly_reblocked"] = len(lost_contents)
    observed_ids = {r["combo_id"] for r in revived if r["combo_id"]}
    out["prediction_matches_observed"] = observed_ids == predicted_ids
    out["predicted_not_observed"] = sorted(predicted_ids - observed_ids)
    out["observed_not_predicted"] = sorted(observed_ids - predicted_ids)
    return out


# --------------------------------------------------------------------------------------
# (b) per-degree wheel deltas
# --------------------------------------------------------------------------------------
def analyze_wheels(run_dir: Path, rings: dict[str, int], max_ring: int) -> dict:
    # Counts are only meaningful once p3_pipeline_run.sh's stage markers land; while
    # enum_wheels is mid-flight a degree's directory is legitimately short, and
    # predicted-vs-observed disagreement means nothing.
    wheels_done = (run_dir / "DONE_enum_wheels").exists()
    cartwheels_done = (run_dir / "DONE_enum_cartwheels").exists()
    out: dict = {
        "baseline": dict(BASELINE_WHEELS),
        "stage_complete": wheels_done,
        "cartwheel_stage_complete": cartwheels_done,
        "per_degree": {},
    }

    predicted_revived: dict[int, list[dict]] = {}
    for d in WHEEL_DEGREES:
        path = P2_DIR / f"wheel_survivors_d{d}.jsonl"
        revived: list[dict] = []
        if path.exists():
            with path.open() as fh:
                for line in fh:
                    rec = json.loads(line)
                    if not rec.get("blocked"):
                        continue
                    dead = [
                        conc
                        for conc in rec["blockers_per_concretization"]
                        if all(rings.get(b, 0) > max_ring for b in conc)
                    ]
                    if dead:
                        revived.append(
                            {
                                "degree": d,
                                "seq": rec["seq"],
                                "charge_bound": rec.get("charge_bound"),
                                "sole_blockers_above_ring": sorted(
                                    {b for conc in dead for b in conc}
                                ),
                            }
                        )
        predicted_revived[d] = revived

    total_observed = 0
    total_predicted = 0
    for d in WHEEL_DEGREES:
        wdir = run_dir / "work" / "wheels" / f"d{d}"
        observed = len(list(wdir.glob("*.cartwheel"))) if wdir.is_dir() else None
        pred_n = len(predicted_revived[d])
        entry = {
            "baseline": BASELINE_WHEELS[d],
            "observed": observed,
            "delta": None if observed is None else observed - BASELINE_WHEELS[d],
            "predicted_revived": pred_n,
            "predicted_total": BASELINE_WHEELS[d] + pred_n,
            "matches_prediction": None
            if (observed is None or not wheels_done)
            else observed == BASELINE_WHEELS[d] + pred_n,
        }
        out["per_degree"][f"d{d}"] = entry
        total_predicted += pred_n
        if observed is not None:
            total_observed += observed
    out["predicted_revived_wheels"] = predicted_revived
    out["n_predicted_revived_total"] = total_predicted
    out["n_observed_total"] = total_observed or None
    out["baseline_total"] = sum(BASELINE_WHEELS.values())

    zero_dir = run_dir / "work" / "wheels" / "zero"
    if zero_dir.is_dir() and cartwheels_done:
        n_zero = len(list(zero_dir.glob("*.cartwheel")))
        out["bad_cartwheels"] = {
            "baseline": BASELINE_N_BAD_CARTWHEELS,
            "observed": n_zero,
            "delta": n_zero - BASELINE_N_BAD_CARTWHEELS,
        }
    else:
        out["bad_cartwheels"] = {"baseline": BASELINE_N_BAD_CARTWHEELS, "observed": None}
    return out


# --------------------------------------------------------------------------------------
# (c) gluing-stage localization
# --------------------------------------------------------------------------------------
def analyze_gluing(
    run_dir: Path,
    rings: dict[str, int],
    max_ring: int,
    s1_gluelog_dir: Path | None,
    top_n: int,
) -> tuple[dict, list[dict]]:
    out: dict = {"checks": {}}
    any_failure = False
    for check in CHECKS:
        info = parse_check_log(run_dir / "log" / f"{check}.log", check)
        out["checks"][check] = info
        if info["present"] and not info["finished"]:
            any_failure = True
    out["stage_reached"] = any(v["present"] for v in out["checks"].values())
    out["any_failure"] = any_failure
    out["failed_checks"] = [
        c for c, v in out["checks"].items() if v["present"] and not v["finished"]
    ]

    # Baseline composite -> first-match blockers, restricted to composites at risk.
    at_risk_rows: list[dict] = []
    per_check: dict[str, dict] = {}
    culprit_counts: Counter = Counter()
    for check in CHECKS:
        path = BASELINE_GLUELOG / f"{check}.gluelog.tsv"
        if not path.exists():
            per_check[check] = {"gluelog": str(path), "present": False}
            continue
        per_hash = parse_gluelog(path)
        n_at_risk = 0
        for state_hash, names in per_hash.items():
            lost = sorted({n for n in names if rings.get(n, 0) > max_ring})
            if not lost:
                continue
            n_at_risk += 1
            culprit_counts.update(lost)
            at_risk_rows.append(
                {
                    "check": check,
                    "state_hash": state_hash,
                    "blockers": names,
                    "blockers_above_ring": lost,
                    "all_blockers_above_ring": len(lost) == len(set(names)),
                }
            )
        per_check[check] = {
            "gluelog": str(path),
            "present": True,
            "n_composites_logged": len(per_hash),
            "n_at_risk": n_at_risk,
            "frac_at_risk": (n_at_risk / len(per_hash)) if per_hash else 0.0,
        }
    out["baseline_gluelog"] = per_check
    out["n_at_risk_composites"] = len(at_risk_rows)
    out["top_culprit_configs"] = [
        {"config": name, "ring": rings.get(name), "n_at_risk_composites": n}
        for name, n in culprit_counts.most_common(top_n)
    ]
    out["n_distinct_culprit_configs"] = len(culprit_counts)
    out["static_mode_caveat"] = (
        "gluelog attribution is FIRST-MATCH per representative, so 'at risk' is an UPPER "
        "bound on composites that truly lost every blocker; use --s1-gluelog-dir for the "
        "exact set"
    )

    # Exact mode: diff baseline composites against an S1 gluelog, if supplied.
    if s1_gluelog_dir is not None and s1_gluelog_dir.is_dir():
        exact: dict = {"gluelog_dir": str(s1_gluelog_dir), "per_check": {}}
        for check in CHECKS:
            base_path = BASELINE_GLUELOG / f"{check}.gluelog.tsv"
            s1_path = s1_gluelog_dir / f"{check}.gluelog.tsv"
            if not (base_path.exists() and s1_path.exists()):
                exact["per_check"][check] = {"present": False}
                continue
            base_hashes = set(parse_gluelog(base_path))
            s1_hashes = set(parse_gluelog(s1_path))
            lost = sorted(base_hashes - base_hashes.intersection(s1_hashes))
            exact["per_check"][check] = {
                "present": True,
                "n_baseline": len(base_hashes),
                "n_s1": len(s1_hashes),
                "n_lost": len(lost),
                "lost_state_hashes": lost,
            }
        out["exact"] = exact
    else:
        out["exact"] = None
        out["exact_mode_command"] = (
            "third_party/computer-checks/build/src/main_gluelog --check_deg8 "
            f"-W {run_dir}/work/wheels/zero -C build/steinberger-pool-r14/D "
            "-o results/steinberger-s1/gluelog   "
            "(repeat with --check_7triangle / --check_deg7; writes only into -o, "
            "leaving the run dir untouched)"
        )
    return out, at_risk_rows


# --------------------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------------------
def run_analysis(
    run_dir: Path,
    out_dir: Path,
    max_ring: int,
    s1_gluelog_dir: Path | None,
    top_n: int,
) -> dict:
    rings = ring_index()
    out_dir.mkdir(parents=True, exist_ok=True)

    verdict_path = run_dir / "VERDICT.txt"
    report: dict = {
        "run_dir": str(run_dir),
        "max_ring": max_ring,
        "verdict": verdict_path.read_text().strip() if verdict_path.exists() else "(no verdict yet)",
        "n_pool_expected": sum(1 for r in rings.values() if r <= max_ring),
        "n_source_configs": len(rings),
    }

    report["combined_rules"] = analyze_combos(run_dir, rings, max_ring)
    report["wheels"] = analyze_wheels(run_dir, rings, max_ring)
    gluing, at_risk_rows = analyze_gluing(run_dir, rings, max_ring, s1_gluelog_dir, top_n)
    report["gluing"] = gluing

    # Bulk lists go to their own files; the JSON summary stays readable.
    with (out_dir / "revived_combos.jsonl").open("w") as fh:
        for rec in report["combined_rules"].get("revived", []):
            fh.write(json.dumps(rec) + "\n")
    with (out_dir / "predicted_revived_wheels.jsonl").open("w") as fh:
        for d in WHEEL_DEGREES:
            for rec in report["wheels"]["predicted_revived_wheels"][d]:
                fh.write(json.dumps(rec) + "\n")
    with (out_dir / "at_risk_composites.jsonl").open("w") as fh:
        for rec in at_risk_rows:
            fh.write(json.dumps(rec) + "\n")

    slim = json.loads(json.dumps(report))
    slim["wheels"].pop("predicted_revived_wheels", None)
    slim["combined_rules"].pop("predicted_revived", None)
    (out_dir / "gap_analysis.json").write_text(json.dumps(slim, indent=2) + "\n")
    return report


def print_summary(report: dict, out_dir: Path) -> None:
    c = report["combined_rules"]
    w = report["wheels"]
    g = report["gluing"]
    print(f"S1 gap analysis  run={report['run_dir']}  ring<={report['max_ring']}")
    print(f"verdict: {report['verdict']}")

    print("\n(a) combined rules (charge structure)")
    if c["stage_reached"]:
        print(f"  non_blocked: {c['n_non_blocked']} vs baseline {BASELINE_N_NON_BLOCKED} "
              f"(delta {c['delta_non_blocked']:+d}); {c['n_revived']} revived combos")
        print(f"  prediction from full attribution: {c['n_predicted_revived']} revived -> "
              f"{'MATCH' if c['prediction_matches_observed'] else 'MISMATCH'}")
        if c["n_unexpectedly_reblocked"]:
            print(f"  !! {c['n_unexpectedly_reblocked']} baseline combos vanished "
                  "(impossible under pool restriction -- investigate)")
        for rec in c["revived"][:20]:
            print(f"    {rec['combo_id']}  predicted={rec['predicted']}")
    else:
        print(f"  stage not reached; predicted {c['n_predicted_revived']} revived combos "
              f"-> non_blocked would be {c['predicted_n_non_blocked']}")

    print("\n(b) wheels" + ("" if w["stage_complete"] else "  [enum_wheels IN FLIGHT -- "
                                                            "counts partial, deltas not yet meaningful]"))
    for d in WHEEL_DEGREES:
        e = w["per_degree"][f"d{d}"]
        obs = "-" if e["observed"] is None else str(e["observed"])
        delta = "" if e["delta"] is None else f" (delta {e['delta']:+d})"
        flag = "" if e["matches_prediction"] in (None, True) else "  MISMATCH"
        print(f"  d{d}: observed {obs} vs baseline {e['baseline']}{delta}; "
              f"predicted revived {e['predicted_revived']}{flag}")
    bc = w["bad_cartwheels"]
    if bc["observed"] is not None:
        print(f"  bad cartwheels: {bc['observed']} vs baseline {bc['baseline']} "
              f"(delta {bc['delta']:+d})")

    print("\n(c) gluing")
    if g["stage_reached"]:
        for check in CHECKS:
            info = g["checks"][check]
            if not info["present"]:
                continue
            state = "finished" if info["finished"] else "FAILED"
            extra = ""
            if info["assertion"]:
                extra = (f"  assert({info['assertion']}) in {info['assert_function']} "
                         f"@ {info['assert_file']}:{info['assert_line']}")
            print(f"  {check}: {state}  cartwheels_remaining="
                  f"{info['n_cartwheels_remaining']}{extra}")
    else:
        print("  stage not reached yet")
    print(f"  at-risk glued composites (upper bound, first-match log): "
          f"{g['n_at_risk_composites']} across "
          f"{g['n_distinct_culprit_configs']} ring>{report['max_ring']} configs")
    for row in g["top_culprit_configs"][:10]:
        print(f"    {row['config']} (ring {row['ring']}): "
              f"{row['n_at_risk_composites']} composites")
    if g["exact"] is None:
        print(f"  exact mode: {g['exact_mode_command']}")
    else:
        for check, e in g["exact"]["per_check"].items():
            if e.get("present"):
                print(f"  EXACT {check}: {e['n_lost']} composites lost every blocker")

    print(f"\nwrote {out_dir}/gap_analysis.json, revived_combos.jsonl, "
          "predicted_revived_wheels.jsonl, at_risk_composites.jsonl")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, default=ROOT / "results" / "p3" / "runs" / "steinberger-s1")
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "steinberger-s1")
    ap.add_argument("--max-ring", type=int, default=14)
    ap.add_argument("--s1-gluelog-dir", type=Path, default=None)
    ap.add_argument("--top-n", type=int, default=50)
    args = ap.parse_args()

    report = run_analysis(args.run_dir, args.out, args.max_ring, args.s1_gluelog_dir, args.top_n)
    print_summary(report, args.out)


if __name__ == "__main__":
    main()
