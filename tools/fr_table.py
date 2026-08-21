#!/usr/bin/env python3
"""f(r) theorem sweep: exhaustively enumerate every ring-r configuration
with interior size STRICTLY BELOW the published-catalog D-reducible
minimum f_catalog(r), and verify none of them is D-reducible.

This is the generalization of the "Candidate B" dual rule in
`results/theorem/candidates.md` (`r == 11 AND n_interior <= 6 ->
non-reducible`, mined from an already-exhaustive r=11 plantri sweep) to
rings 8-12, turned into a documented, reproducible, checkpointed sweep
with a manifest suitable for a THEOREM.md writeup.

Pipeline per (r, n) -- identical to `tools/datagen.py`'s (reused directly,
not reimplemented, so the two stay in lockstep):

    plantri -P<r> -c3 -a <n>          (exhaustive, one member per
                                        isomorphism class, of chordless
                                        disk triangulations of ring size r
                                        and n total vertices -- see
                                        third_party/plantri/plantri55/
                                        plantri-guide.txt's -P section:
                                        default -c3m3 forbids ring chords
                                        AND ring vertices of degree 2)
      -> trace_outer_face             (recover the ring cycle from the
                                        rotation system)
      -> to_configuration             (relabel to RSST convention 1..r
                                        ring / r+1..n interior; filters:
                                        interior nonempty, interior degree
                                        >= 5, interior connected)
      -> is_legal_configuration       (SECOND, independently-implemented
                                        check against RSST's own ReadConf
                                        well-formedness conditions
                                        (2),(4)-(7) -- logged loudly as an
                                        EXCEPTION if it and the filter
                                        above ever disagree; see
                                        `fourcolor.mutate.is_legal_configuration`)
      -> fourcolor.reduce.check       (D-/C-reducibility verdict)

Every valid configuration at every (r, n) in range is written to a JSONL
shard; a per-ring manifest tracks plantri's raw output count, the
post-outer-face-length count, the post-structural-filter count (= configs
actually checked), and the D-reducible count (must be exactly 0, or the
sweep has found a counterexample -- an EXCEPTION, flagged loudly both to
stdout and in the manifest).

Usage:
    .venv/bin/python tools/fr_table.py <r> <n_min> <n_max>
        [--outdir results/theorem/fr_table] [--resume]

Designed to be safe to re-run / resume: with --resume, any (r, n) shard
that already has a manifest entry is skipped (the shard file itself is
trusted as complete once its manifest entry is written -- manifest
entries are only written after a shard's JSONL is fully flushed).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from fourcolor.conf_parser import rotate_ring_starts  # noqa: E402
from fourcolor.mutate import is_legal_configuration  # noqa: E402
from fourcolor.reduce import check  # noqa: E402

import datagen  # noqa: E402  (reuse parse_ascii_line/trace_outer_face/to_configuration)

PLANTRI = datagen.PLANTRI

# Published-catalog D-reducible minimum interior size per ring size, as
# independently confirmed two ways (see results/theorem/fr_table/THEOREM.md
# section "Catalog minima -- how f_catalog(r) was determined"):
#   (a) parsing all 8200 files of third_party/reducible-configurations/D
#       (the nl4ct D-only catalog) via fourcolor.nl4ct_conf.parse_nl4ct_conf
#       and taking min(n - r) per ring size r;
#   (b) this project's own earlier plantri sweeps (data/configs_r8_n10-15
#       .jsonl, data/configs_r9_n11-15.jsonl, data/configs_r10_n12-17
#       .jsonl) independently finding the same first-D-reducible interior
#       size for r=8,9,10.
F_CATALOG = {8: 5, 9: 5, 10: 6, 11: 7, 12: 7}


def sweep_one(r: int, n: int, outdir: Path, log) -> dict:
    """Run plantri + filter + check for one (r, n); write the JSONL shard;
    return the manifest entry dict (does not write the manifest itself)."""
    t0 = time.time()
    shard = outdir / f"configs_r{r}_n{n}.jsonl"
    proc = subprocess.run(
        [str(PLANTRI), f"-P{r}", "-c3", "-a", str(n)],
        capture_output=True, text=True)
    lines = [l for l in proc.stdout.splitlines() if l and l[0].isdigit()]
    raw = len(lines)
    ring_ok = 0
    kept = 0            # passed to_configuration's filter (candidate configs)
    rsst_legal = 0      # of those, also RSST-legal (the true configuration class)
    excluded_cond6 = 0  # RSST condition (6): interior vertex touches ring in >2 arcs
    d_reducible = 0     # counted only among rsst_legal configs
    exceptions: list[dict] = []
    with shard.open("w") as f:
        for k, line in enumerate(lines):
            adj = datagen.parse_ascii_line(line)
            ring = datagen.trace_outer_face(adj)
            if ring is None or len(ring) != r:
                continue
            ring_ok += 1
            cfg = datagen.to_configuration(adj, ring, f"fr-r{r}-n{n}-{k}")
            if cfg is None:
                continue
            kept += 1
            # Independent second check against RSST's own well-formedness
            # conditions (mutate.is_legal_configuration, ported from
            # ReadConf in reduce.c). Condition (4) there requires each ring
            # vertex's neighbor list to *start* at a specific position
            # (ring-neighbor i+1) -- a pure serialization/labeling
            # convention, not a structural graph property (fourcolor.
            # reduce.check and Configuration.validate are both
            # rotation-start-agnostic), and tools/datagen.py's relabeling
            # does not track it. So the legality check is run against a
            # rotate_ring_starts()-normalized copy of the adjacency (a
            # no-op on the actual rotation system/graph -- see
            # conf_parser.rotate_ring_starts's docstring), isolating
            # genuine structural gaps from that labeling artifact.
            #
            # What's left after that normalization is real: a nonzero
            # fraction of near-triangulations passing to_configuration's
            # filter (chordless ring, ring-vertex degree>=3, interior
            # degree>=5, interior connected) fail RSST's condition (6) --
            # some interior vertex touches the ring boundary in more than
            # 2 separate contiguous arcs. reduce.c's own ReadConf REJECTS
            # such inputs outright (ReadErr(6, ...)) -- they are not
            # "configurations" in RSST's technical sense at all, so they
            # are excluded from the enumerated configuration class here
            # (not counted in `rsst_legal`/d_reducible_count) but still
            # written to the shard (tagged rsst_legal=False) for
            # transparency, since fourcolor.reduce.check still computes
            # SOME verdict for them (the algorithm doesn't itself depend
            # on condition (6) to terminate) even though that verdict is
            # out of RSST's defined scope.
            legal = is_legal_configuration(
                rotate_ring_starts(cfg.adjacency, cfg.r), cfg.r, cfg.n)
            res = check(cfg)
            if legal:
                rsst_legal += 1
                d_reducible += res.d_reducible
            else:
                excluded_cond6 += 1
            rec = {
                "ident": cfg.ident, "n": n, "r": r, "n_interior": n - r,
                "adjacency": {str(v): nb for v, nb in cfg.adjacency.items()},
                "n_extendable": res.n_extendable,
                "n_consistent": res.n_consistent,
                "d_reducible": res.d_reducible,
                "rounds": res.rounds, "trace": res.trace,
                "is_legal_configuration": legal,
            }
            f.write(json.dumps(rec) + "\n")
            if legal and res.d_reducible:
                exceptions.append({
                    "kind": "D_REDUCIBLE_BELOW_THRESHOLD",
                    "ident": cfg.ident, "n": n, "r": r, "n_interior": n - r,
                })
                log(f"  *** EXCEPTION: D-REDUCIBLE BELOW THRESHOLD *** "
                    f"{cfg.ident} (r={r}, n={n}, interior={n - r})")
            elif (not legal) and res.d_reducible:
                # Would-be exception, but out of scope (not an RSST
                # configuration) -- still surfaced loudly, never silent.
                exceptions.append({
                    "kind": "D_REDUCIBLE_BUT_NOT_RSST_LEGAL",
                    "ident": cfg.ident, "n": n, "r": r, "n_interior": n - r,
                })
                log(f"  *** NOTE: d_reducible=True but excluded (RSST "
                    f"condition 6 violation) *** {cfg.ident}")
    dt = time.time() - t0
    entry = {
        "r": r, "n": n, "n_interior": n - r,
        "raw_triangulations": raw,
        "ring_length_ok": ring_ok,
        "candidate_configs": kept,
        "excluded_condition6": excluded_cond6,
        "valid_configs": rsst_legal,
        "d_reducible_count": d_reducible,
        "exceptions": exceptions,
        "elapsed_s": round(dt, 1),
        "shard": str(shard.relative_to(ROOT)),
    }
    log(f"r={r} n={n} (interior={n - r}): {raw} raw -> {ring_ok} ring-ok -> "
        f"{kept} candidate configs ({excluded_cond6} excluded, cond-6) -> "
        f"{rsst_legal} valid configs, {d_reducible} D-reducible, {dt:.1f}s")
    return entry


def load_manifest(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {"entries": {}}


def save_manifest(path: Path, manifest: dict) -> None:
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("r", type=int)
    ap.add_argument("n_min", type=int)
    ap.add_argument("n_max", type=int)
    ap.add_argument("--outdir", default=str(ROOT / "results" / "theorem" / "fr_table"))
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    manifest_path = outdir / f"manifest_r{args.r}.json"
    manifest = load_manifest(manifest_path)
    entries = manifest.setdefault("entries", {})
    manifest["r"] = args.r
    manifest["f_catalog"] = F_CATALOG.get(args.r)
    manifest["plantri_binary"] = str(PLANTRI.relative_to(ROOT))

    def log(msg: str) -> None:
        print(msg, flush=True)

    log(f"=== f(r) sweep: r={args.r}, n={args.n_min}..{args.n_max} "
        f"(interior {args.n_min - args.r}..{args.n_max - args.r}), "
        f"f_catalog(r)={F_CATALOG.get(args.r)} ===")

    t0 = time.time()
    for n in range(args.n_min, args.n_max + 1):
        key = str(n)
        if args.resume and key in entries:
            log(f"r={args.r} n={n}: already in manifest, skipping (--resume)")
            continue
        entry = sweep_one(args.r, n, outdir, log)
        entries[key] = entry
        save_manifest(manifest_path, manifest)

    total_candidate = sum(e["candidate_configs"] for e in entries.values())
    total_excluded = sum(e["excluded_condition6"] for e in entries.values())
    total_valid = sum(e["valid_configs"] for e in entries.values())
    total_dred = sum(e["d_reducible_count"] for e in entries.values())
    all_exceptions = [x for e in entries.values() for x in e["exceptions"]]
    hard_exceptions = [x for x in all_exceptions
                       if x["kind"] == "D_REDUCIBLE_BELOW_THRESHOLD"]
    manifest["summary"] = {
        "total_candidate_configs": total_candidate,
        "total_excluded_condition6": total_excluded,
        "total_valid_configs": total_valid,
        "total_d_reducible": total_dred,
        "total_exceptions": len(all_exceptions),
        "total_hard_exceptions": len(hard_exceptions),
        "verdict": "PASS (0 D-reducible below threshold, among RSST-legal configs)"
                   if not hard_exceptions
                   else f"EXCEPTIONS FOUND: {len(hard_exceptions)} D-reducible "
                        f"below threshold",
        "elapsed_s": round(time.time() - t0, 1),
    }
    save_manifest(manifest_path, manifest)
    log(f"=== r={args.r} DONE: {total_valid} valid configs ({total_excluded} "
        f"excluded, cond-6) across n={args.n_min}..{args.n_max}, {total_dred} "
        f"D-reducible (expect 0), {len(hard_exceptions)} hard exceptions "
        f"-> {manifest_path} ===")
    return 0 if not hard_exceptions else 1


if __name__ == "__main__":
    raise SystemExit(main())
