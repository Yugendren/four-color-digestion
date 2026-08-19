#!/usr/bin/env python3
"""P3 M2: usage ranking table.

Merges three usage counts per pool configuration (8,200 ``.conf`` source files under
``third_party/computer-checks/reducible-configurations/D``):

  - ``combo_count``: number of BLOCKED combined rules (``combo_blockers.jsonl``,
    ``blocked: true``) that list the config in their full attribution set
    (``all_blockers`` -- appears in >=1 representative-degree concretization's blocker
    set). Only blocked combos are counted: for a combo that is not blocked, some
    concretization has ZERO blockers regardless, so no config's presence in another
    concretization's (non-empty) blocker set can be "the reason" it's unblocked or
    blocked -- deleting such a config changes nothing about that combo's status.
  - ``wheel_count``: same idea, over ``results/p2-coverage/wheel_survivors_d{7..11}.jsonl``
    (``blocked: true`` records, full attribution already computed there by
    ``fourcolor.nl4ct.wheel_block_attribution``).
  - ``cartwheel_first_count``: raw occurrence count of the config's name across every
    ``*.blocklog.tsv`` line's matched-names field under
    ``third_party/computer-checks/wheels/zero_blocklog/`` (2.25M blocking events). This
    is a FIRST-MATCH count (the C++ patch logs only the first matching config per
    representative-degree concretization, mirroring the original short-circuit boolean
    check -- see ``results/p2-coverage/report.md``), i.e. a LOWER bound on true
    cartwheel-level attribution, not full attribution -- named accordingly.

Output: ``results/p3/usage_table.csv`` (one row per pool config, all 8,200, zero-filled
where a config never appears in a role) plus a JSON summary including the zero-usage
count -- deletion batch #1's size.

Usage:
    tools/p3_usage_table.py
"""

from __future__ import annotations

import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fourcolor import nl4ct as m  # noqa: E402

RESULTS_DIR = ROOT / "results" / "p3"
P2_DIR = ROOT / "results" / "p2-coverage"
BLOCKLOG_DIR = ROOT / "third_party" / "computer-checks" / "wheels" / "zero_blocklog"
WHEEL_DEGREES = (7, 8, 9, 10, 11)


def all_pool_config_names() -> list[str]:
    return sorted(p.stem for p in m.default_conf_dir().glob("*.conf"))


def combo_counts(path: Path | None = None) -> Counter:
    if path is None:
        path = RESULTS_DIR / "combo_blockers.jsonl"
    counts: Counter = Counter()
    n_blocked = 0
    with path.open() as f:
        for line in f:
            r = json.loads(line)
            if not r["blocked"]:
                continue
            n_blocked += 1
            for name in r["all_blockers"]:
                counts[name] += 1
    print(f"combo_counts: {n_blocked} blocked combos, {len(counts)} distinct configs referenced")
    return counts


def wheel_counts(degrees: Sequence[int] = WHEEL_DEGREES, p2_dir: Path | None = None) -> Counter:
    if p2_dir is None:
        p2_dir = P2_DIR
    counts: Counter = Counter()
    n_blocked = 0
    for d in degrees:
        path = p2_dir / f"wheel_survivors_d{d}.jsonl"
        with path.open() as f:
            for line in f:
                r = json.loads(line)
                if not r["blocked"]:
                    continue
                n_blocked += 1
                seen_this_wheel: set[str] = set()
                for blockers in r["blockers_per_concretization"]:
                    seen_this_wheel.update(blockers)
                for name in seen_this_wheel:
                    counts[name] += 1
    print(f"wheel_counts: {n_blocked} blocked wheels (all degrees), "
          f"{len(counts)} distinct configs referenced")
    return counts


def cartwheel_first_counts(blocklog_dir: Path | None = None) -> Counter:
    if blocklog_dir is None:
        blocklog_dir = BLOCKLOG_DIR
    counts: Counter = Counter()
    n_events = 0
    n_files = 0
    t0 = time.time()
    paths = sorted(blocklog_dir.glob("*.blocklog.tsv"))
    for i, path in enumerate(paths):
        n_files += 1
        with path.open() as f:
            for line in f:
                line = line.rstrip("\n")
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) < 3:
                    continue
                matched = parts[2]
                if not matched:
                    continue
                n_events += 1
                for name in matched.split(","):
                    name = name.strip()
                    if name:
                        counts[name] += 1
        if (i + 1) % 2000 == 0:
            print(f"  blocklog files {i + 1}/{len(paths)} elapsed={time.time() - t0:.0f}s", flush=True)
    print(f"cartwheel_first_counts: {n_files} files, {n_events} blocking events, "
          f"{len(counts)} distinct configs referenced, elapsed={time.time() - t0:.0f}s")
    return counts


def run() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    pool = all_pool_config_names()
    print(f"pool: {len(pool)} configs")

    cc = combo_counts()
    wc = wheel_counts()
    cw = cartwheel_first_counts()

    out_path = RESULTS_DIR / "usage_table.csv"
    n_zero = 0
    n_zero_combo = 0
    n_zero_wheel = 0
    n_zero_cartwheel = 0
    with out_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["config", "combo_count", "wheel_count", "cartwheel_first_count"])
        for name in pool:
            c, w, k = cc.get(name, 0), wc.get(name, 0), cw.get(name, 0)
            writer.writerow([name, c, w, k])
            if c == 0:
                n_zero_combo += 1
            if w == 0:
                n_zero_wheel += 1
            if k == 0:
                n_zero_cartwheel += 1
            if c == 0 and w == 0 and k == 0:
                n_zero += 1

    # Sanity: every config referenced in any role must be a member of the pool (no
    # stray/typo'd names slipping through the merge).
    stray = (set(cc) | set(wc) | set(cw)) - set(pool)
    assert not stray, f"usage counts reference {len(stray)} names outside the pool: {sorted(stray)[:10]}"

    summary = {
        "n_pool_configs": len(pool),
        "n_zero_combo_count": n_zero_combo,
        "n_zero_wheel_count": n_zero_wheel,
        "n_zero_cartwheel_first_count": n_zero_cartwheel,
        "n_zero_usage_all_three_roles": n_zero,
        "csv": str(out_path.relative_to(ROOT)),
    }
    summary_path = RESULTS_DIR / "usage_table_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    run()
