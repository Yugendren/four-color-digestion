#!/usr/bin/env python3
"""Steinberger S1: build the ring-restricted configuration pool.

Steinberger's open question (see ``03-MASS-LAW-PROGRAM.md`` M5) asks whether a
D-reducible-only unavoidable set exists using only configurations of ring size <= 14.
This script builds the candidate pool for that experiment: a directory of symlinks
into ``third_party/reducible-configurations/D`` holding exactly the configurations
whose ring size R (field 2 of the ``N R`` header line -- see
``third_party/computer-checks/FORMAT.md``) satisfies ``R <= max-ring``.

The output layout mirrors ``build/p3-pool-v1/D`` (absolute symlinks, one per .conf) so
that ``tools/p3_pipeline_run.sh <pool-dir>/D <run-name>`` consumes it unchanged.

Usage:
    tools/s1_build_pool.py                       # ring <= 14 -> build/steinberger-pool-r14/D
    tools/s1_build_pool.py --max-ring 15 --out build/steinberger-pool-r15
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONF_DIR = ROOT / "third_party" / "reducible-configurations" / "D"


def read_ring(conf_path: Path) -> int:
    """Ring size R from a .conf file: line 1 is blank, line 2 is ``N R``."""
    lines = conf_path.read_text().splitlines()
    if len(lines) < 2:
        raise ValueError(f"{conf_path}: fewer than 2 lines")
    if lines[0].strip() != "":
        raise ValueError(f"{conf_path}: line 1 is not blank (got {lines[0]!r})")
    fields = lines[1].split()
    if len(fields) != 2:
        raise ValueError(f"{conf_path}: header line is not 'N R' (got {lines[1]!r})")
    return int(fields[1])


def ring_index(conf_dir: Path | None = None) -> dict[str, int]:
    """Map config stem (e.g. ``D1234``) -> ring size, over every .conf in conf_dir."""
    if conf_dir is None:
        conf_dir = CONF_DIR
    return {p.stem: read_ring(p) for p in sorted(conf_dir.glob("*.conf"))}


def ring_distribution(rings: dict[str, int]) -> dict[int, int]:
    dist: dict[int, int] = {}
    for r in rings.values():
        dist[r] = dist.get(r, 0) + 1
    return dict(sorted(dist.items()))


def _rel(path: Path) -> str:
    """Repo-relative path where possible (readable manifests), absolute otherwise."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def build(out_dir: Path, max_ring: int, conf_dir: Path | None = None) -> dict:
    if conf_dir is None:
        conf_dir = CONF_DIR
    rings = ring_index(conf_dir)
    dist = ring_distribution(rings)

    d_dir = out_dir / "D"
    d_dir.mkdir(parents=True, exist_ok=True)
    for stale in d_dir.glob("*.conf"):
        stale.unlink()

    kept = sorted(name for name, r in rings.items() if r <= max_ring)
    for name in kept:
        (d_dir / f"{name}.conf").symlink_to((conf_dir / f"{name}.conf").resolve())

    return {
        "conf_dir": _rel(conf_dir),
        "pool_dir": _rel(d_dir),
        "max_ring": max_ring,
        "n_source_total": len(rings),
        "n_pool": len(kept),
        "n_excluded": len(rings) - len(kept),
        "ring_distribution": {str(r): n for r, n in dist.items()},
        "ring_distribution_kept": {str(r): n for r, n in dist.items() if r <= max_ring},
        "ring_distribution_excluded": {str(r): n for r, n in dist.items() if r > max_ring},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-ring", type=int, default=14)
    ap.add_argument("--out", type=Path, default=ROOT / "build" / "steinberger-pool-r14")
    ap.add_argument(
        "--summary",
        type=Path,
        default=ROOT / "results" / "steinberger-s1" / "pool_ring_distribution.json",
    )
    args = ap.parse_args()

    summary = build(args.out, args.max_ring)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, indent=2) + "\n")

    print(f"pool: {summary['n_pool']} / {summary['n_source_total']} configs "
          f"(ring <= {args.max_ring}); {summary['n_excluded']} excluded")
    for r, n in summary["ring_distribution"].items():
        mark = "keep" if int(r) <= args.max_ring else "DROP"
        print(f"  ring {r:>2}: {n:>5}  {mark}")
    print(f"wrote {args.summary}")


if __name__ == "__main__":
    main()
