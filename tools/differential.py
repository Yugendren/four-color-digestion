#!/usr/bin/env python3
"""Full differential run: independent checker vs published header fields.

Usage: .venv/bin/python tools/differential.py [max_ring] [conf_path]

Writes results/differential-<name>/report.jsonl with one record per
configuration: ident, r, header (a, b), computed (a, b), verdicts, rounds,
closure trace (the future process-supervision labels), and wall time.
"""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fourcolor.conf_parser import parse_conf  # noqa: E402
from fourcolor.reduce import check  # noqa: E402


def main() -> int:
    max_ring = int(sys.argv[1]) if len(sys.argv) > 1 else 14
    conf = Path(sys.argv[2]) if len(sys.argv) > 2 else (
        ROOT / "third_party" / "arxiv-1401.6481" / "src" / "anc" / "unavoidable.conf"
    )
    name = conf.stem + f"-r{max_ring}"
    outdir = ROOT / "results" / f"differential-{name}"
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / "report.jsonl"

    configs = [c for c in parse_conf(conf) if c.r <= max_ring]
    print(f"{len(configs)} configurations with ring <= {max_ring} from {conf.name}")

    agree = disagree = 0
    with out.open("w") as f:
        for i, c in enumerate(configs):
            t0 = time.time()
            res = check(c)
            dt = time.time() - t0
            ok = (
                res.n_extendable == c.a
                and res.n_consistent == c.b
                and (res.d_reducible or res.c_reducible)
            )
            agree += ok
            disagree += not ok
            rec = {
                "ident": c.ident, "r": c.r, "n": c.n,
                "header_a": c.a, "header_b": c.b,
                "computed_a": res.n_extendable, "computed_b": res.n_consistent,
                "d_reducible": res.d_reducible, "c_reducible": res.c_reducible,
                "rounds": res.rounds, "trace": res.trace,
                "seconds": round(dt, 3), "agree": ok,
            }
            f.write(json.dumps(rec) + "\n")
            if not ok:
                print("DISAGREE", rec)
            if (i + 1) % 25 == 0:
                print(f"  {i+1}/{len(configs)} done ({agree} agree)")

    print(f"final: {agree} agree, {disagree} disagree -> {out}")
    return 0 if disagree == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
