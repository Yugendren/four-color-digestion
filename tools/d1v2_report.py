#!/usr/bin/env python3
"""D1-v2 data-layer stats + honest report.

Reads data/v2/traces_r{8,9,10}.jsonl (written by tools/d1v2_datagen.py) and
data/v2/plantri_r{r}_n{n}.state.json checkpoints (if the background plantri
enrichment job is still running / hasn't been merged in yet), computes
per-ring totals/class-balance/boundary counts/set-trace size distributions/
storage sizes, runs the round-0-vs-counts-trace cross-check on a random
sample of configs (independent re-check via fourcolor.reduce.check, NOT a
copy of the stored data), and writes results/d1v2/data_report.md.

Usage: .venv/bin/python tools/d1v2_report.py
"""

from __future__ import annotations

import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fourcolor.conf_parser import Configuration  # noqa: E402
from fourcolor.reduce import check                # noqa: E402

V2_DIR = ROOT / "data" / "v2"
RINGS = (8, 9, 10)
REPORT_DIR = ROOT / "results" / "d1v2"
SANITY_SAMPLE_SIZE = 100
SANITY_SEED = 0


def load_jsonl(path: Path) -> list[dict]:
    recs = []
    if not path.exists():
        return recs
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def human_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def sanity_check(all_records: dict[int, list[dict]], sample_size: int, seed: int) -> dict:
    """Independent cross-check: for a random sample, rebuild the config from
    stored adjacency and re-run check() FRESH (no record_sets -- a separate
    code path from what produced the stored set_trace), then verify the
    per-round SIZE of the stored set_trace equals the freshly recomputed
    counts trace exactly, plus rounds and n_consistent agree."""
    rng = random.Random(seed)
    pool = [rec for recs in all_records.values() for rec in recs]
    sample = rng.sample(pool, min(sample_size, len(pool)))
    n_checked = 0
    n_mismatch = 0
    examples = []
    for rec in sample:
        adjacency = {int(v): nb for v, nb in rec["adjacency"].items()}
        cfg = Configuration(rec["ident"], rec["n"], rec["r"], -1, -1, [], adjacency, [])
        res = check(cfg)
        set_sizes = [len(rnd) for rnd in rec["set_trace"]]
        ok = (
            set_sizes == res.trace
            and res.rounds == rec["rounds"]
            and res.n_consistent == rec["n_consistent"]
            and res.d_reducible == rec["d_reducible"]
        )
        n_checked += 1
        if not ok:
            n_mismatch += 1
            if len(examples) < 5:
                examples.append({
                    "ident": rec["ident"], "r": rec["r"],
                    "recorded_set_sizes": set_sizes, "recomputed_trace": res.trace,
                })
    return {"n_checked": n_checked, "n_mismatch": n_mismatch, "examples": examples}


def per_ring_stats(r: int, recs: list[dict]) -> dict:
    n_total = len(recs)
    n_reducible = sum(1 for x in recs if x["d_reducible"])
    n_boundary = sum(1 for x in recs if x["boundary"])
    n_boundary_nonred_small = sum(
        1 for x in recs
        if not x["d_reducible"] and 0 < x["n_consistent"] <= 50
    )
    n_boundary_red_slow = sum(
        1 for x in recs if x["d_reducible"] and x["rounds"] >= 6
    )
    by_source: dict[str, int] = {}
    for x in recs:
        by_source[x.get("source", "?")] = by_source.get(x.get("source", "?"), 0) + 1

    round_sizes = [len(rnd) for x in recs for rnd in x["set_trace"]]
    round0_sizes = [len(x["set_trace"][0]) for x in recs if x["set_trace"]]
    rounds_per_config = [x["rounds"] for x in recs]

    return {
        "n_total": n_total,
        "n_reducible": n_reducible,
        "n_not_reducible": n_total - n_reducible,
        "fraction_reducible": n_reducible / n_total if n_total else 0.0,
        "n_boundary": n_boundary,
        "n_boundary_nonreducible_small_consistent": n_boundary_nonred_small,
        "n_boundary_reducible_slow": n_boundary_red_slow,
        "by_source": by_source,
        "set_trace_round_size_mean": statistics.mean(round_sizes) if round_sizes else 0.0,
        "set_trace_round_size_max": max(round_sizes) if round_sizes else 0,
        "set_trace_round0_size_mean": statistics.mean(round0_sizes) if round0_sizes else 0.0,
        "set_trace_round0_size_max": max(round0_sizes) if round0_sizes else 0,
        "rounds_mean": statistics.mean(rounds_per_config) if rounds_per_config else 0.0,
        "rounds_max": max(rounds_per_config) if rounds_per_config else 0,
    }


def plantri_job_status(r: int, n: int) -> dict | None:
    state_path = V2_DIR / f"plantri_r{r}_n{n}.state.json"
    if not state_path.exists():
        return None
    return json.loads(state_path.read_text())


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    all_records: dict[int, list[dict]] = {}
    stats: dict[int, dict] = {}
    storage: dict[str, int] = {}

    for r in RINGS:
        traces_path = V2_DIR / f"traces_r{r}.jsonl"
        recs = load_jsonl(traces_path)
        all_records[r] = recs
        stats[r] = per_ring_stats(r, recs)
        if traces_path.exists():
            storage[traces_path.name] = traces_path.stat().st_size
        idx_path = V2_DIR / f"code_index_r{r}.json"
        if idx_path.exists():
            storage[idx_path.name] = idx_path.stat().st_size

    sanity = sanity_check(all_records, SANITY_SAMPLE_SIZE, SANITY_SEED)

    plantri_status = {r: plantri_job_status(r, 18) for r in RINGS}

    lines = []
    lines.append("# D1-v2 data layer: per-round survivor-SET traces (rings 8-10)")
    lines.append("")
    lines.append(
        "Full per-round survivor SETS (not count buckets) for D-reducibility "
        "closure on rings 8, 9, 10, assembled from the existing corpus "
        "(data/d1_corpus.jsonl) plus new plantri generation at n=18 -- one "
        "ring size beyond anything in the prior corpus. Every record's "
        "set_trace comes from a single fourcolor.reduce.check(record_sets="
        "True) call on its own stored adjacency (not copied/joined from a "
        "separate source), so trace/verdict/set_trace are self-consistent "
        "by construction; the independent cross-check below re-derives the "
        "counts trace a SECOND time via a separate check() call to catch "
        "encoding bugs."
    )
    lines.append("")

    lines.append("## Code index maps")
    lines.append("")
    lines.append("| ring r | n canonical codes | file |")
    lines.append("|---|---|---|")
    for r in RINGS:
        idx_path = V2_DIR / f"code_index_r{r}.json"
        n_codes = json.loads(idx_path.read_text())["n_codes"] if idx_path.exists() else "?"
        lines.append(f"| {r} | {n_codes} | data/v2/code_index_r{r}.json |")
    lines.append("")

    lines.append("## Per-ring totals and class balance")
    lines.append("")
    lines.append(
        "| ring r | n configs | d_reducible | not reducible | frac reducible | "
        "boundary (total) | boundary: non-red, small C\\' (0<n<=50) | "
        "boundary: reducible, rounds>=6 |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in RINGS:
        s = stats[r]
        lines.append(
            f"| {r} | {s['n_total']} | {s['n_reducible']} | {s['n_not_reducible']} | "
            f"{s['fraction_reducible']:.3f} | {s['n_boundary']} | "
            f"{s['n_boundary_nonreducible_small_consistent']} | "
            f"{s['n_boundary_reducible_slow']} |"
        )
    lines.append("")

    lines.append("## Source breakdown (corpus vs new plantri n=18)")
    lines.append("")
    for r in RINGS:
        lines.append(f"- ring {r}: {stats[r]['by_source']}")
    lines.append("")

    lines.append("## Set-trace size distributions")
    lines.append("")
    lines.append(
        "| ring r | mean codes/round (all rounds) | max codes/round | "
        "mean round-0 size | max round-0 size | mean rounds/config | max rounds/config |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for r in RINGS:
        s = stats[r]
        lines.append(
            f"| {r} | {s['set_trace_round_size_mean']:.1f} | {s['set_trace_round_size_max']} | "
            f"{s['set_trace_round0_size_mean']:.1f} | {s['set_trace_round0_size_max']} | "
            f"{s['rounds_mean']:.2f} | {s['rounds_max']} |"
        )
    lines.append("")

    lines.append("## Storage")
    lines.append("")
    total_bytes = sum(storage.values())
    for name, sz in sorted(storage.items()):
        lines.append(f"- `data/v2/{name}`: {human_bytes(sz)} ({sz} bytes)")
    lines.append(f"- **total**: {human_bytes(total_bytes)} ({total_bytes} bytes)")
    lines.append("")

    lines.append("## Sanity check: round-0..N set SIZES vs an independently recomputed counts trace")
    lines.append("")
    lines.append(
        f"Sampled {sanity['n_checked']} random configs (seed={SANITY_SEED}) across all "
        f"three rings from data/v2/traces_r*.jsonl, rebuilt each Configuration from its "
        f"stored adjacency, called `fourcolor.reduce.check()` fresh (WITHOUT record_sets, "
        f"a distinct code path from the one that produced the stored set_trace), and "
        f"compared `len(set_trace[i])` per round against the freshly recomputed `trace[i]` "
        f"counts, plus `rounds`, `n_consistent`, and `d_reducible` agreement."
    )
    lines.append("")
    lines.append(f"**Result: {sanity['n_checked'] - sanity['n_mismatch']}/{sanity['n_checked']} exact matches.**")
    if sanity["n_mismatch"]:
        lines.append("")
        lines.append(f"{sanity['n_mismatch']} MISMATCHES (examples below) -- see raw data before trusting downstream training on these rings:")
        lines.append("")
        for ex in sanity["examples"]:
            lines.append(f"- `{ex['ident']}` (r={ex['r']}): recorded set sizes {ex['recorded_set_sizes']} "
                        f"vs recomputed trace {ex['recomputed_trace']}")
    lines.append("")

    lines.append("## New plantri n=18 generation status")
    lines.append("")
    lines.append(
        "plantri's search-tree size (and hence full-enumeration wall time) at n=18 is far "
        "beyond a single ~30-minute budget for these ring sizes (measured: ~33s CPU per "
        "1/200th `res/mod` split-shard, roughly independent of ring, i.e. a full unsplit "
        "n=18 run is on the order of 1-3+ hours per ring). Each (ring, n=18) job runs "
        "`res/mod`-split shards to completion one at a time (never truncating a partially-"
        "read plantri stream) in a fixed pseudo-random shard order (spread across the whole "
        "search space, not a biased prefix), stopping cleanly at a wall-clock budget with a "
        "resumable checkpoint."
    )
    lines.append("")
    for r in RINGS:
        st = plantri_status[r]
        if st is None:
            lines.append(f"- ring {r}, n=18: not yet started.")
        else:
            lines.append(
                f"- ring {r}, n=18: {st['n_residues_done']}/{st['n_residues_total']} "
                f"res/mod shards done, {'COMPLETE' if st['complete'] else 'PARTIAL (resumable via --resume)'}, "
                f"{st['configs_kept_total']} configs kept so far out of "
                f"{st['triangulations_seen_total']} disk triangulations scanned "
                f"(elapsed {st.get('elapsed_seconds', st.get('last_updated', '?'))})."
            )
    lines.append("")
    lines.append(
        "Re-run `tools/d1v2_datagen.py plantri --resume` to continue any partial job, then "
        "`tools/d1v2_datagen.py merge` to fold newly-completed shards into `traces_r{r}."
        "jsonl`, then re-run this report."
    )
    lines.append("")

    report_path = REPORT_DIR / "data_report.md"
    report_path.write_text("\n".join(lines) + "\n")
    print(f"Wrote {report_path}")

    stats_json_path = REPORT_DIR / "data_stats.json"
    stats_json_path.write_text(json.dumps({
        "per_ring": stats, "storage_bytes": storage, "sanity_check": sanity,
        "plantri_status": plantri_status,
    }, indent=2, default=str))
    print(f"Wrote {stats_json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
