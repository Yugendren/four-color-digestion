#!/usr/bin/env python3
"""D1 corpus assembly: merge every configuration source we have into one
deduplicated JSONL corpus for process-supervised D-reducibility training.

Sources merged (see the D1 task spec / sources/method-survey.md §2):
  (a) generated:      data/configs_r*.jsonl        -- plantri search hits,
                       already carry adjacency/r/n/d_reducible/trace/
                       n_extendable/n_consistent/ident.
  (b) rsst633:         third_party/arxiv-1401.6481/src/anc/unavoidable.conf
                       (adjacency, via fourcolor.conf_parser) joined by
                       ident against results/differential-unavoidable-r14/
                       report.jsonl (trace, computed_a/b, d_reducible,
                       rounds -- our independent checker's output, not the
                       header claim, so trace is self-consistent with the
                       verdict).
  (c) steinberger2822: third_party/arxiv-0905.0043/src/anc/U_2822.conf
                       joined by ident against results/differential-
                       U_2822-r16/report.jsonl the same way.
  (d) nl4ct_pool:      results/p3/pool-verify/shard_*.jsonl -- the audited
                       8,200-config nl4ct pool. These records do NOT carry
                       a trace field (n_extendable/n_consistent/d_reducible/
                       rounds only), so trace=null here; they are eval-only
                       for the process-supervision target and can still
                       serve the outcome head / encoder-side smoke data.
                       adjacency is recovered from the pool's own .conf
                       files (third_party/reducible-configurations/D/
                       <ident>.conf) via fourcolor.nl4ct_conf, since the
                       shard reports themselves only carry summary stats.

Dedup: canonical adjacency form via fourcolor.canonical.canonical_key,
which is invariant to the ring's rotation-start + reflection (the only
degree of freedom the shared RSST-style numbering convention leaves
unconstrained across these sources -- see that module's docstring for the
exact argument and its documented limitation). Records are processed in
source-priority order (rsst633 > steinberger2822 > generated > nl4ct_pool
-- prefer the two named, independently-cross-checked historical sets,
then trace-bearing search hits, then the trace-less pool) so that when
the same canonical configuration appears more than once, the
highest-priority (most informative) copy is kept and the rest are logged
as collisions, not silently dropped.

Usage: .venv/bin/python tools/d1_assemble.py
Writes: data/d1_corpus.jsonl, results/d1/corpus_stats.json
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fourcolor.canonical import canonical_key  # noqa: E402
from fourcolor.conf_parser import parse_conf  # noqa: E402
from fourcolor.nl4ct_conf import ConversionError, parse_nl4ct_conf  # noqa: E402

RSST_CONF = ROOT / "third_party" / "arxiv-1401.6481" / "src" / "anc" / "unavoidable.conf"
RSST_REPORT = ROOT / "results" / "differential-unavoidable-r14" / "report.jsonl"
STEIN_CONF = ROOT / "third_party" / "arxiv-0905.0043" / "src" / "anc" / "U_2822.conf"
STEIN_REPORT = ROOT / "results" / "differential-U_2822-r16" / "report.jsonl"
NL4CT_POOL_DIR = ROOT / "third_party" / "reducible-configurations" / "D"
POOL_VERIFY_DIR = ROOT / "results" / "p3" / "pool-verify"
GENERATED_GLOB = "configs_r*.jsonl"

SOURCE_PRIORITY = ["rsst633", "steinberger2822", "generated", "nl4ct_pool"]


def _record(
    ident: str,
    source: str,
    r: int,
    n: int,
    adjacency: dict[int, list[int]],
    d_reducible: bool,
    n_extendable: int | None,
    n_consistent: int | None,
    rounds: int | None,
    trace: list[int] | None,
) -> dict:
    return {
        "ident": ident,
        "source": source,
        "r": r,
        "n": n,
        "adjacency": {str(v): nbrs for v, nbrs in adjacency.items()},
        "d_reducible": d_reducible,
        "n_extendable": n_extendable,
        "n_consistent": n_consistent,
        "rounds": rounds,
        "trace": trace,
    }


def load_generated(data_dir: Path) -> list[dict]:
    out = []
    for f in sorted(data_dir.glob(GENERATED_GLOB)):
        with f.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                adjacency = {int(v): nbrs for v, nbrs in rec["adjacency"].items()}
                out.append(
                    _record(
                        ident=rec["ident"],
                        source="generated",
                        r=rec["r"],
                        n=rec["n"],
                        adjacency=adjacency,
                        d_reducible=rec["d_reducible"],
                        n_extendable=rec.get("n_extendable"),
                        n_consistent=rec.get("n_consistent"),
                        rounds=rec.get("rounds"),
                        trace=rec.get("trace"),
                    )
                )
    return out


def load_conf_plus_report(conf_path: Path, report_path: Path, source: str) -> list[dict]:
    configs = {c.ident: c for c in parse_conf(conf_path)}
    out = []
    unmatched = []
    with report_path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rep = json.loads(line)
            cfg = configs.get(rep["ident"])
            if cfg is None:
                unmatched.append(rep["ident"])
                continue
            out.append(
                _record(
                    ident=rep["ident"],
                    source=source,
                    r=cfg.r,
                    n=cfg.n,
                    adjacency=cfg.adjacency,
                    d_reducible=rep["d_reducible"],
                    n_extendable=rep.get("computed_a"),
                    n_consistent=rep.get("computed_b"),
                    rounds=rep.get("rounds"),
                    trace=rep.get("trace"),
                )
            )
    if unmatched:
        print(
            f"WARNING [{source}]: {len(unmatched)} report idents had no "
            f".conf match (first 5: {unmatched[:5]})",
            file=sys.stderr,
        )
    return out


def load_nl4ct_pool(pool_verify_dir: Path, conf_dir: Path) -> tuple[list[dict], list[str]]:
    out = []
    conversion_failures: list[str] = []
    for f in sorted(pool_verify_dir.glob("shard_*.jsonl")):
        with f.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                ident = rec["ident"]
                conf_path = conf_dir / f"{ident}.conf"
                if not conf_path.exists():
                    conversion_failures.append(ident)
                    continue
                try:
                    cfg = parse_nl4ct_conf(conf_path)
                except ConversionError:
                    conversion_failures.append(ident)
                    continue
                out.append(
                    _record(
                        ident=ident,
                        source="nl4ct_pool",
                        r=rec["r"],
                        n=rec["n"],
                        adjacency=cfg.adjacency,
                        d_reducible=rec["d_reducible"],
                        n_extendable=rec.get("n_extendable"),
                        n_consistent=rec.get("n_consistent"),
                        rounds=rec.get("rounds"),
                        trace=None,
                    )
                )
    return out, conversion_failures


def dedup(records_by_source: dict[str, list[dict]]) -> tuple[list[dict], dict]:
    """First-seen-wins dedup by canonical adjacency key, source priority
    order. Returns (kept records, collision stats)."""
    seen: dict[str, dict] = {}  # canonical_key -> kept record
    collisions: list[dict] = []
    per_source_seen_keys: dict[str, set[str]] = defaultdict(set)
    within_source_dupes = Counter()

    for source in SOURCE_PRIORITY:
        for rec in records_by_source.get(source, []):
            key = canonical_key(
                {int(v): nbrs for v, nbrs in rec["adjacency"].items()},
                rec["r"],
                rec["n"],
            )
            if key in per_source_seen_keys[source]:
                within_source_dupes[source] += 1
            per_source_seen_keys[source].add(key)

            if key in seen:
                collisions.append(
                    {
                        "canonical_key_prefix": key[:60],
                        "kept_source": seen[key]["source"],
                        "kept_ident": seen[key]["ident"],
                        "dropped_source": source,
                        "dropped_ident": rec["ident"],
                    }
                )
                continue
            rec = dict(rec)
            rec["canonical_key"] = key
            seen[key] = rec

    kept = list(seen.values())
    stats = {
        "collisions": collisions,
        "n_collisions_total": len(collisions),
        "within_source_dupes": dict(within_source_dupes),
        "cross_source_overlap": Counter(
            (c["kept_source"], c["dropped_source"]) for c in collisions
        ),
    }
    return kept, stats


def compute_stats(records: list[dict], pre_dedup_counts: dict, dedup_stats: dict, conversion_failures: list[str]) -> dict:
    per_ring = Counter(r["r"] for r in records)
    per_source = Counter(r["source"] for r in records)
    class_balance = Counter(r["d_reducible"] for r in records)
    trace_lens = Counter(len(r["trace"]) for r in records if r["trace"] is not None)
    n_with_trace = sum(1 for r in records if r["trace"] is not None)
    n_without_trace = len(records) - n_with_trace

    per_source_per_ring = defaultdict(Counter)
    for r in records:
        per_source_per_ring[r["source"]][r["r"]] += 1

    cross_source_overlap = {
        f"{kept}<-{dropped}": n
        for (kept, dropped), n in dedup_stats["cross_source_overlap"].items()
    }

    return {
        "total_records_pre_dedup": sum(pre_dedup_counts.values()),
        "pre_dedup_counts_by_source": pre_dedup_counts,
        "total_records": len(records),
        "per_source_counts": dict(per_source),
        "per_ring_counts": dict(sorted(per_ring.items())),
        "per_source_per_ring_counts": {
            src: dict(sorted(c.items())) for src, c in per_source_per_ring.items()
        },
        "class_balance": {
            "d_reducible_true": class_balance.get(True, 0),
            "d_reducible_false": class_balance.get(False, 0),
            "fraction_d_reducible": (
                class_balance.get(True, 0) / len(records) if records else 0.0
            ),
        },
        "trace_availability": {
            "with_trace": n_with_trace,
            "without_trace": n_without_trace,
        },
        "trace_length_distribution": dict(sorted(trace_lens.items())),
        "dedup": {
            "n_collisions_total": dedup_stats["n_collisions_total"],
            "within_source_dupes": dedup_stats["within_source_dupes"],
            "cross_source_overlap_kept_from_dropped": cross_source_overlap,
            "example_collisions": dedup_stats["collisions"][:20],
        },
        "nl4ct_pool_conversion_failures": {
            "count": len(conversion_failures),
            "examples": conversion_failures[:20],
        },
        "canonicalization_note": (
            "dedup key = fourcolor.canonical.canonical_key (dihedral-on-ring "
            "canonical form); see that module's docstring for exact scope "
            "and documented limitations."
        ),
    }


def main() -> int:
    data_dir = ROOT / "data"

    print("Loading generated configs...")
    generated = load_generated(data_dir)
    print(f"  {len(generated)} records")

    print("Loading RSST 633...")
    rsst = load_conf_plus_report(RSST_CONF, RSST_REPORT, "rsst633")
    print(f"  {len(rsst)} records")

    print("Loading Steinberger 2822...")
    stein = load_conf_plus_report(STEIN_CONF, STEIN_REPORT, "steinberger2822")
    print(f"  {len(stein)} records")

    print("Loading nl4ct pool (audited)...")
    pool, conversion_failures = load_nl4ct_pool(POOL_VERIFY_DIR, NL4CT_POOL_DIR)
    print(f"  {len(pool)} records ({len(conversion_failures)} conversion failures)")

    records_by_source = {
        "generated": generated,
        "rsst633": rsst,
        "steinberger2822": stein,
        "nl4ct_pool": pool,
    }
    pre_dedup_counts = {k: len(v) for k, v in records_by_source.items()}

    print("Deduping by canonical adjacency form...")
    kept, dedup_stats = dedup(records_by_source)
    print(f"  {len(kept)} unique records ({dedup_stats['n_collisions_total']} collisions)")

    out_path = ROOT / "data" / "d1_corpus.jsonl"
    with out_path.open("w") as f:
        for rec in kept:
            f.write(json.dumps(rec) + "\n")
    print(f"Wrote {out_path}")

    stats = compute_stats(kept, pre_dedup_counts, dedup_stats, conversion_failures)
    stats_dir = ROOT / "results" / "d1"
    stats_dir.mkdir(parents=True, exist_ok=True)
    stats_path = stats_dir / "corpus_stats.json"
    with stats_path.open("w") as f:
        json.dump(stats, f, indent=2)
    print(f"Wrote {stats_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
