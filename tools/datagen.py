#!/usr/bin/env python3
"""Data factory v0: generate labeled configurations with plantri.

Pipeline: plantri -P<r> -c3 -a <n>  (chordless disk triangulations, ascii)
  -> parse rotation systems, trace the distinguished outer face
  -> relabel to RSST convention (ring = 1..r cyclic, interior r+1..n)
  -> filter: interior degrees >= 5, connected interior
  -> label with fourcolor.reduce.check (D-reducible? |C|, |C'|, closure trace)
  -> JSONL to data/, summary stats to stdout.

Usage: .venv/bin/python tools/datagen.py <r> <n_min> <n_max>
"""

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fourcolor.conf_parser import Configuration  # noqa: E402
from fourcolor.reduce import check  # noqa: E402

PLANTRI = ROOT / "third_party" / "plantri" / "plantri55" / "plantri"


def parse_ascii_line(line: str) -> dict[int, list[int]]:
    """plantri -a line: 'n a1a2..,b1b2..,...' with letters a=1,b=2,..."""
    head, lists = line.split(" ", 1)
    n = int(head)
    adj = {}
    for i, part in enumerate(lists.strip().split(","), 1):
        adj[i] = [ord(ch) - ord("a") + 1 for ch in part]
    assert len(adj) == n
    return adj


def trace_outer_face(adj: dict[int, list[int]]) -> list[int] | None:
    """Outer face vertices in order, using plantri's convention: the outer
    face lies to the left of the directed edge (1 -> first neighbor of 1).

    Face tracing over a rotation system: after arriving along v->w, the next
    directed edge of the same face is w->x where x is adjacent to v in w's
    rotation (successor or predecessor depending on orientation handedness).
    We try both and return the trace that closes into a simple cycle.
    """
    def walk(succ_offset: int) -> list[int] | None:
        v, w = 1, adj[1][0]
        start = (v, w)
        face = [v]
        for _ in range(4 * len(adj)):
            rot = adj[w]
            i = rot.index(v)
            x = rot[(i + succ_offset) % len(rot)]
            v, w = w, x
            if (v, w) == start:
                return face
            face.append(v)
        return None

    for off in (1, -1):
        f = walk(off)
        if f is not None and len(f) == len(set(f)):
            return f
    return None


def to_configuration(adj: dict[int, list[int]], ring: list[int],
                     ident: str) -> Configuration | None:
    """Relabel so ring vertices are 1..r cyclically (e_1 = {1, r} convention:
    vertex i is adjacent to i+1 and i-1 on the ring), interior r+1..n."""
    r = len(ring)
    n = len(adj)
    relabel = {}
    for i, v in enumerate(ring):
        relabel[v] = i + 1
    nxt = r + 1
    for v in adj:
        if v not in relabel:
            relabel[v] = nxt
            nxt += 1
    new_adj = {relabel[v]: [relabel[u] for u in nbrs] for v, nbrs in adj.items()}

    # Filters: interior degree >= 5; interior nonempty and connected.
    interior = [v for v in new_adj if v > r]
    if not interior:
        return None
    if any(len(new_adj[v]) < 5 for v in interior):
        return None
    seen = {interior[0]}
    stack = [interior[0]]
    while stack:
        v = stack.pop()
        for u in new_adj[v]:
            if u > r and u not in seen:
                seen.add(u)
                stack.append(u)
    if len(seen) != len(interior):
        return None

    cfg = Configuration(ident, n, r, -1, -1, [], new_adj, [])
    try:
        cfg.validate()
    except ValueError:
        return None
    return cfg


def main() -> int:
    r = int(sys.argv[1])
    n_min = int(sys.argv[2])
    n_max = int(sys.argv[3])
    outdir = ROOT / "data"
    outdir.mkdir(exist_ok=True)
    out = outdir / f"configs_r{r}_n{n_min}-{n_max}.jsonl"

    total = kept = reducible = 0
    t0 = time.time()
    with out.open("w") as f:
        for n in range(n_min, n_max + 1):
            proc = subprocess.run(
                [str(PLANTRI), f"-P{r}", "-c3", "-a", str(n)],
                capture_output=True, text=True)
            lines = [l for l in proc.stdout.splitlines() if l and l[0].isdigit()]
            for k, line in enumerate(lines):
                total += 1
                adj = parse_ascii_line(line)
                ring = trace_outer_face(adj)
                if ring is None or len(ring) != r:
                    continue
                cfg = to_configuration(adj, ring, f"gen-r{r}-n{n}-{k}")
                if cfg is None:
                    continue
                kept += 1
                res = check(cfg)
                reducible += res.d_reducible
                rec = {
                    "ident": cfg.ident, "n": n, "r": r,
                    "adjacency": {str(v): nb for v, nb in cfg.adjacency.items()},
                    "n_extendable": res.n_extendable,
                    "n_consistent": res.n_consistent,
                    "d_reducible": res.d_reducible,
                    "rounds": res.rounds, "trace": res.trace,
                }
                f.write(json.dumps(rec) + "\n")
    dt = time.time() - t0
    frac = reducible / kept if kept else 0.0
    print(f"r={r} n={n_min}..{n_max}: {total} disk triangulations, "
          f"{kept} valid configurations, {reducible} D-reducible "
          f"({frac:.1%}) in {dt:.0f}s -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
