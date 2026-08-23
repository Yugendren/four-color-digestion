#!/usr/bin/env python3
"""Measure P(S,4) -- the exact number of proper 4-colourings of the ring+
interior graph -- for every labeled configuration in the corpus, and derive
the Bridge-Lemma quantities the mass-law program needs (results/mass-law/
p4-summary.md): `p24 = p4/24`, `fiber = p24/a`, and the sharp-cap ratio
`p24 / sharp_cap` where `sharp_cap = (2^r+2)/6 * (4/3)^(k-1)`.

Uses `fourcolor.count4.count_proper_4colorings`, a validated exact counter
(frontier DP, ~0.0002s/record average, ~0.0013s worst case at n=32 -- see
src/fourcolor/count4.py). A full single-threaded sweep of the ~59k-record
corpus finishes in well under a minute; no multiprocessing needed.

Usage:
    .venv/bin/python tools/p4_measure.py
    .venv/bin/python tools/p4_measure.py --limit 500          # smoke test
    .venv/bin/python tools/p4_measure.py --out /tmp/p4.jsonl

Every record with usable adjacency gets one output line with:
    ident source r n k a d_reducible p4 p24 fiber sharp_cap

`p24` is `p4 // 24`, ASSERTING `p4 % 24 == 0` (the Bridge Lemma numerator is
always a multiple of the 4! colour permutations). A failure here would be a
serious anomaly: it is caught per-record (not fatal), logged loudly, and
`p24`/`fiber` are written as `null` for that record.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fourcolor.count4 import count_proper_4colorings  # noqa: E402
from fourcolor.lemma_corpus import load_corpus  # noqa: E402

DEFAULT_OUT = ROOT / "results" / "mass-law" / "p4_measurements.jsonl"
PROGRESS_EVERY = 5000


def sharp_cap(r: int, k: int) -> float:
    return (2 ** r + 2) / 6 * (4 / 3) ** (k - 1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=None, help="only process the first N records (smoke test)")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help=f"output JSONL path (default {DEFAULT_OUT})")
    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    corpus = load_corpus()
    records = corpus.records
    if args.limit is not None:
        records = records[: args.limit]
    total = len(records)
    print(f"loaded corpus: {len(corpus.records)} records; processing {total}")

    t0 = time.time()
    n_written = 0
    n_no_adjacency = 0
    n_mod_failures = 0

    with out_path.open("w") as f:
        for i, rec in enumerate(records, start=1):
            adj = rec.adjacency
            if adj is None:
                n_no_adjacency += 1
                print(f"WARNING: no adjacency for ident={rec.ident}, skipping")
                continue

            p4 = count_proper_4colorings(adj)

            p24: int | None
            fiber: float | None
            try:
                assert p4 % 24 == 0
                p24 = p4 // 24
            except AssertionError:
                n_mod_failures += 1
                p24 = None
                print(f"WARNING: p4 % 24 != 0 for ident={rec.ident} (p4={p4})")

            fiber = (p24 / rec.a) if (p24 is not None and rec.a > 0) else None

            row = {
                "ident": rec.ident,
                "source": rec.source,
                "r": rec.r,
                "n": rec.n,
                "k": rec.k,
                "a": rec.a,
                "d_reducible": bool(rec.d_reducible),
                "p4": p4,
                "p24": p24,
                "fiber": fiber,
                "sharp_cap": sharp_cap(rec.r, rec.k),
            }
            f.write(json.dumps(row) + "\n")
            n_written += 1

            if i % PROGRESS_EVERY == 0:
                print(f"processed {i}/{total} ...")

    dt = time.time() - t0
    try:
        out_display = out_path.relative_to(ROOT)
    except ValueError:
        out_display = out_path
    print(
        f"done: {n_written} records written -> {out_display}; "
        f"{n_no_adjacency} skipped (no adjacency); {n_mod_failures} p4%24 failures; "
        f"{dt:.2f}s elapsed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
