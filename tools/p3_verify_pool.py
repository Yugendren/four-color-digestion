#!/usr/bin/env python3
"""Independent D-reducibility verification of the nl4ct pool (our checker).

Usage: p3_verify_pool.py --pool DIR --out results/p3/pool-verify \
           --rings 6,7,8,9,10,11,12,13,14 [--shard I --shard-total N]

Each invocation processes the configs whose ring size is in --rings, sharded
by index if requested, writing JSONL records to
  <out>/shard_r<rings-tag>_<I>of<N>.jsonl
Resume-safe: already-recorded idents are skipped on restart.

Correctness discipline:
  * every config is converted (nl4ct_conf) and structurally validated;
  * the checker is the 3,455-config-validated fourcolor.reduce.check;
  * expected verdict is D-reducible for EVERY config (the pool's claim);
    any other verdict is recorded with flag=ANOMALY and echoed loudly to
    stderr — a potential error in the published pool, never suppressed.
"""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fourcolor.nl4ct_conf import parse_nl4ct_conf  # noqa: E402
from fourcolor.reduce import check  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--rings", required=True)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shard-total", type=int, default=1)
    args = ap.parse_args()

    rings = {int(x) for x in args.rings.split(",")}
    tag = "-".join(str(x) for x in sorted(rings))
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    outfile = outdir / f"shard_r{tag}_{args.shard}of{args.shard_total}.jsonl"

    done = set()
    if outfile.exists():
        for line in outfile.open():
            try:
                done.add(json.loads(line)["ident"])
            except Exception:
                pass

    # Deterministic work list: ring ascending, then name.
    work = []
    for f in sorted(Path(args.pool).glob("*.conf")):
        header = f.read_text().splitlines()[1].split()
        r = int(header[1])
        if r in rings:
            work.append((r, f))
    work.sort()
    work = [w for i, w in enumerate(work) if i % args.shard_total == args.shard]

    n_anom = 0
    with outfile.open("a") as out:
        for i, (r, f) in enumerate(work):
            if f.stem in done:
                continue
            t0 = time.time()
            rec = {"ident": f.stem, "r": r}
            try:
                cfg = parse_nl4ct_conf(f)
                res = check(cfg)
                rec.update(n=cfg.n, n_extendable=res.n_extendable,
                           n_consistent=res.n_consistent,
                           d_reducible=res.d_reducible,
                           rounds=res.rounds,
                           seconds=round(time.time() - t0, 2))
                if not res.d_reducible:
                    rec["flag"] = "ANOMALY"
                    n_anom += 1
                    print(f"ANOMALY: {f.stem} r={r} NOT D-reducible "
                          f"(ext={res.n_extendable}, consistent={res.n_consistent})",
                          file=sys.stderr, flush=True)
            except Exception as e:
                rec["flag"] = "CONVERSION_FLAGGED"
                rec["error"] = str(e)[:200]
                print(f"CONVERSION_FLAGGED: {f.stem}: {e}", file=sys.stderr,
                      flush=True)
            out.write(json.dumps(rec) + "\n")
            out.flush()
            if (i + 1) % 50 == 0:
                print(f"[shard {args.shard}/{args.shard_total} r{tag}] "
                      f"{i+1}/{len(work)} done, {n_anom} anomalies",
                      flush=True)
    print(f"[shard {args.shard}/{args.shard_total} r{tag}] COMPLETE: "
          f"{len(work)} configs, {n_anom} anomalies", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
