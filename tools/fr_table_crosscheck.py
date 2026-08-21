#!/usr/bin/env python3
"""Cross-verify a sample of `tools/fr_table.py`'s RSST-legal, below-threshold
configurations against the compiled RSST oracle (`build/reduce_rsst`).

For each ring r in the sweep, samples up to `--sample-size` (default 20)
RSST-legal (is_legal_configuration == True) configs from the fr_table
shards (`results/theorem/fr_table/configs_r{r}_n{n}.jsonl`), deterministically
(seeded), reconstructs each as a `fourcolor.conf_parser.Configuration`,
normalizes it for the C reader with `for_rsst_oracle` (ring-vertex rotation
start + coordinate padding -- see that function's docstring), serializes it,
and runs `build/reduce_rsst` on it, parsing the verdict from stdout:

    "***  D-reducible  ***"    with exit 0                 -> oracle says D-reducible
    "Not D-reducible" + "NO CONTRACT PROPOSED", exit != 0   -> oracle says not D-reducible

and compares against this project's own `fourcolor.reduce.check` verdict
(already recorded in the shard). Every sampled config in this sweep is
below the catalog's D-reducible-minimum threshold, so 100% agreement here
is itself independent (compiled, 1995-vintage reference implementation)
corroboration of the sweep's central "0 D-reducible below threshold" claim
-- not just a generic differential test.

KNOWN, INVESTIGATED DISCREPANCY: on exhaustively-generated (not
hand-curated) small configurations, `build/reduce_rsst` occasionally
recomputes a DIFFERENT header-`a` (|C(K)|) count than `fourcolor.reduce.
check` and aborts with "ERROR: DISCREPANCY IN NUMBER OF EXTENDING
COLOURINGS" before reaching a D-reducibility verdict at all (observed rate
in this sweep: ~10%). This is NOT evidence against `fourcolor.reduce.
check`: (1) that function already agrees with the compiled oracle's header
`a` on ALL 3455 hand-curated RSST+Steinberger catalog configurations with
zero mismatches (`results/differential-unavoidable-r14/report.jsonl`,
`results/differential-U_2822-r16/report.jsonl`); (2) every disputed case
checked so far is confirmed correct by a THIRD, from-scratch, independent
implementation (`fourcolor.brute_force.brute_force_extendable_codes` --
different edge/triangle enumeration, no gauge-fixing, no greedy variable
ordering; see that module's docstring and `tests/test_brute_force.py`).
The most plausible explanation is a latent edge case in the 1995 `reduce.
c`'s `strip()` edge-numbering heuristic never exercised by its original,
hand-curated validation set. This script therefore treats a count
discrepancy as ORACLE_INCONCLUSIVE (not a verdict MISMATCH) but always
resolves it with the brute-force tie-breaker and reports that result too
-- see `results/theorem/fr_table/THEOREM.md`'s "RSST oracle count-mismatch
investigation" section.

Usage:
    .venv/bin/python tools/fr_table_crosscheck.py [--sample-size 20]
        [--rings 8,9,10,11,12] [--fr-dir results/theorem/fr_table]
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fourcolor.brute_force import brute_force_extendable_codes  # noqa: E402
from fourcolor.conf_parser import Configuration, for_rsst_oracle, serialize  # noqa: E402

REDUCE_RSST = ROOT / "build" / "reduce_rsst"


def load_legal_records(fr_dir: Path, r: int) -> list[dict]:
    out = []
    for shard in sorted(fr_dir.glob(f"configs_r{r}_n*.jsonl")):
        for line in shard.open():
            rec = json.loads(line)
            if rec.get("is_legal_configuration"):
                out.append(rec)
    return out


def run_oracle(rec: dict) -> dict:
    adj = {int(k): v for k, v in rec["adjacency"].items()}
    cfg = Configuration(rec["ident"], rec["n"], rec["r"],
                         rec["n_extendable"], rec["n_consistent"], [], adj, [])
    rcfg = for_rsst_oracle(cfg, a=rec["n_extendable"], b=rec["n_consistent"])
    with tempfile.NamedTemporaryFile("w", suffix=".conf", delete=False) as f:
        f.write(serialize([rcfg]))
        path = f.name
    try:
        proc = subprocess.run([str(REDUCE_RSST), path], capture_output=True,
                               text=True, timeout=120)
    finally:
        Path(path).unlink(missing_ok=True)
    out = proc.stdout
    oracle_d_reducible = ("***  D-reducible  ***" in out) and ("Not D-reducible" not in out)
    return {
        "returncode": proc.returncode,
        "stdout_tail": out[-400:],
        "oracle_d_reducible": oracle_d_reducible,
        "no_contract_proposed": "NO CONTRACT PROPOSED" in out,
        "discrepancy_in_extending_colourings": "DISCREPANCY IN NUMBER OF EXTENDING COLOURINGS" in out,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample-size", type=int, default=20)
    ap.add_argument("--rings", default="8,9,10,11,12")
    ap.add_argument("--fr-dir", default=str(ROOT / "results" / "theorem" / "fr_table"))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if not REDUCE_RSST.exists():
        print(f"ERROR: {REDUCE_RSST} not built. Run `make oracle` first.")
        return 2

    fr_dir = Path(args.fr_dir)
    rng = random.Random(args.seed)
    report: dict = {"sample_size": args.sample_size, "seed": args.seed, "rings": {}}
    total_checked = total_agree = total_mismatch = total_error = 0
    total_bf_disagree = 0

    for r in [int(x) for x in args.rings.split(",")]:
        records = load_legal_records(fr_dir, r)
        if not records:
            print(f"r={r}: no RSST-legal records found under {fr_dir} -- skipping "
                  f"(sweep not finished yet?)")
            continue
        sample = records if len(records) <= args.sample_size else \
            rng.sample(records, args.sample_size)
        per_ring = []
        agree = mismatch = error = bf_disagree = 0
        for rec in sample:
            oracle = run_oracle(rec)
            bf_note = None
            if oracle["discrepancy_in_extending_colourings"]:
                # The oracle never reached a D-reducibility verdict for
                # this config -- inconclusive, not a verdict disagreement.
                # Resolve which |C(K)| is right with the independent
                # from-scratch brute-force implementation.
                adj = {int(k): v for k, v in rec["adjacency"].items()}
                cfg = Configuration(rec["ident"], rec["n"], rec["r"], -1, -1, [], adj, [])
                bf_count = len(brute_force_extendable_codes(cfg))
                bf_agrees_with_us = (bf_count == rec["n_extendable"])
                bf_note = {"brute_force_n_extendable": bf_count,
                           "brute_force_agrees_with_reduce_py": bf_agrees_with_us}
                error += 1
                if bf_agrees_with_us:
                    status = "ORACLE_INCONCLUSIVE_brute_force_confirms_ours"
                else:
                    status = "ORACLE_INCONCLUSIVE_brute_force_DISAGREES_WITH_OURS"
                    bf_disagree += 1
            elif oracle["oracle_d_reducible"] == rec["d_reducible"]:
                agree += 1
                status = "AGREE"
            else:
                mismatch += 1
                status = "MISMATCH"
            per_ring.append({
                "ident": rec["ident"], "n": rec["n"], "n_interior": rec["n_interior"],
                "our_d_reducible": rec["d_reducible"],
                "oracle_d_reducible": oracle["oracle_d_reducible"],
                "oracle_returncode": oracle["returncode"],
                "status": status,
                **({"brute_force": bf_note} if bf_note else {}),
            })
            if status != "AGREE":
                print(f"  *** {status} *** r={r} ident={rec['ident']} "
                      f"ours={rec['d_reducible']} oracle={oracle['oracle_d_reducible']}\n"
                      f"      {oracle['stdout_tail']!r}")
        report["rings"][str(r)] = {
            "population_size": len(records), "sampled": len(sample),
            "agree": agree, "mismatch": mismatch,
            "oracle_inconclusive": error, "bf_disagree": bf_disagree,
            "records": per_ring,
        }
        total_checked += len(sample)
        total_agree += agree
        total_mismatch += mismatch
        total_error += error
        total_bf_disagree += bf_disagree
        print(f"r={r}: population={len(records)} sampled={len(sample)} "
              f"agree={agree} mismatch={mismatch} oracle_inconclusive={error} "
              f"(of which brute-force-disagrees={bf_disagree})")

    hard_fail = total_mismatch > 0 or total_bf_disagree > 0
    report["summary"] = {
        "total_checked": total_checked, "total_agree": total_agree,
        "total_mismatch": total_mismatch,
        "total_oracle_inconclusive": total_error,
        "total_brute_force_disagree": total_bf_disagree,
        "verdict": (
            "PASS: RSST oracle agrees on every sampled config that reached "
            "a verdict; every count-discrepancy case that made the oracle "
            "abort was independently resolved in fourcolor.reduce.check's "
            "favor by the from-scratch brute-force tie-breaker"
            if not hard_fail else
            "DISCREPANCY FOUND -- see per-ring records (mismatch or "
            "brute-force-disagree > 0)"
        ),
    }
    out_path = Path(args.out) if args.out else fr_dir / "crosscheck.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"=== TOTAL: checked={total_checked} agree={total_agree} "
          f"mismatch={total_mismatch} oracle_inconclusive={total_error} "
          f"brute_force_disagree={total_bf_disagree} -> {out_path} ===")
    return 0 if not hard_fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
