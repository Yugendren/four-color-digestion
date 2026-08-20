"""Converter: near-linear-4ct .conf format -> fourcolor Configuration.

Their format (see third_party/computer-checks/FORMAT.md and the authoritative
loader Configuration::from_file in src/configuration.cpp):
  line 1: header (skipped by the C++ via getline; empty in practice)
  line 2: N R
  then one line per INTERNAL vertex u = R+1..N (1-indexed):
      u deg n1 n2 ... ndeg     (clockwise rotation)
Ring vertices 1..R are implicit; their clockwise rotations are reconstructed
exactly as the C++ does: for ring vertex v the rotation starts at the next
ring vertex (v+1 cyclically), follows the successor chain derived from the
internal vertices' rotations, and must end at the previous ring vertex
(v-1 cyclically). This matches the RSST convention our Configuration uses
(condition (4): a_{i,1} = i+1, a_{i,d_i} = i-1).

Configs with cut vertices (the C++ expands these into 2^|P| degree variants)
may fail the chain reconstruction or our structural validation; such configs
are reported as CONVERSION_FLAGGED rather than silently skipped.
"""

from __future__ import annotations

from pathlib import Path

from .conf_parser import Configuration


class ConversionError(Exception):
    pass


def parse_nl4ct_conf(path: str | Path) -> Configuration:
    lines = Path(path).read_text().splitlines()
    # C++ skips the first line unconditionally (getline into dummy).
    body = lines[1:]
    header = body[0].split()
    n, r = int(header[0]), int(header[1])

    rotations: dict[int, list[int]] = {}
    idx = 1
    for u in range(r + 1, n + 1):
        parts = body[idx].split()
        idx += 1
        if int(parts[0]) != u:
            raise ConversionError(f"{path}: expected vertex {u}, got {parts[0]}")
        deg = int(parts[1])
        nbrs = [int(x) for x in parts[2:2 + deg]]
        if len(nbrs) != deg:
            raise ConversionError(f"{path}: vertex {u} degree mismatch")
        rotations[u] = nbrs

    # successor maps for ring vertices, mirroring configuration.cpp:
    # for internal u with consecutive (pre, v, nxt) in its rotation and v a
    # ring vertex: in v's rotation, u follows nxt and pre follows u.
    suc: dict[int, dict[int, int]] = {v: {} for v in range(1, r + 1)}
    for u, rot in rotations.items():
        d = len(rot)
        for j in range(d):
            v = rot[j]
            pre = rot[(j - 1) % d]
            nxt = rot[(j + 1) % d]
            if v <= r:
                suc[v][nxt] = u
                suc[v][u] = pre

    for v in range(1, r + 1):
        start = v % r + 1              # next ring vertex, cyclic, 1-indexed
        end = (v - 2) % r + 1          # previous ring vertex
        rot = [start]
        curr = start
        while curr in suc[v]:
            curr = suc[v][curr]
            rot.append(curr)
            if len(rot) > n + 2:
                raise ConversionError(f"{path}: rotation cycle at ring vertex {v}")
        if rot[-1] != end:
            raise ConversionError(
                f"{path}: ring vertex {v} chain ends at {rot[-1]}, expected {end}"
            )
        rotations[v] = rot

    ident = Path(path).stem
    cfg = Configuration(ident, n, r, -1, -1, [], rotations, [])
    cfg.validate()
    return cfg
