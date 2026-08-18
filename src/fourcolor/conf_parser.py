"""Parser for RSST/Steinberger configuration files (unavoidable.conf format).

Record layout (whitespace-separated, records separated by blank lines):

    <identifier>                 e.g. "0.7322"  (an arbitrary name string)
    n r a b                      n = vertices of free completion, r = ring size,
                                 a, b = cardinalities of precomputed coloring sets
    k p1 q1 ... pk qk            the contract: k edges as endpoint pairs (k=0 -> none)
    v deg u1 ... u_deg           n adjacency rows; ring vertices are 1..r,
                                 configuration vertices r+1..n
    c1 c2 ... cn                 n packed drawing coordinates (1024*x + y),
                                 wrapped over multiple lines

Reference: RSST arXiv:1401.6481 ancillary files; format described in
sources/4ct-proof-dossier.md §1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Configuration:
    ident: str
    n: int          # vertices in the free completion
    r: int          # ring size
    a: int          # |C| cardinality used by reduce.c
    b: int          # |C'| cardinality used by reduce.c
    contract: list[tuple[int, int]]
    adjacency: dict[int, list[int]]   # vertex -> ordered neighbor list
    coords: list[int] = field(default_factory=list)

    @property
    def interior_vertices(self) -> range:
        return range(self.r + 1, self.n + 1)

    @property
    def ring_vertices(self) -> range:
        return range(1, self.r + 1)

    def validate(self) -> None:
        """Structural sanity checks; raises ValueError on violation."""
        if not (0 < self.r < self.n):
            raise ValueError(f"{self.ident}: bad n={self.n}, r={self.r}")
        if set(self.adjacency) != set(range(1, self.n + 1)):
            raise ValueError(f"{self.ident}: adjacency keys != 1..n")
        for v, nbrs in self.adjacency.items():
            if len(nbrs) != len(set(nbrs)):
                raise ValueError(f"{self.ident}: repeated neighbor at vertex {v}")
            for u in nbrs:
                if not 1 <= u <= self.n:
                    raise ValueError(f"{self.ident}: neighbor {u} out of range at {v}")
                if v not in self.adjacency[u]:
                    raise ValueError(f"{self.ident}: asymmetric edge {v}->{u}")
        for p, q in self.contract:
            if q not in self.adjacency[p]:
                raise ValueError(f"{self.ident}: contract edge {p}-{q} not an edge")
        if self.coords and len(self.coords) != self.n:
            raise ValueError(
                f"{self.ident}: {len(self.coords)} coords for n={self.n}"
            )

    def to_networkx(self):
        """Free completion as a networkx Graph with ring/interior labels."""
        import networkx as nx

        g = nx.Graph()
        for v, nbrs in self.adjacency.items():
            g.add_node(v, ring=(v <= self.r))
            for u in nbrs:
                g.add_edge(v, u)
        return g


def _tokens(text: str):
    """Yield (line_number, token_list) for non-empty lines."""
    for i, line in enumerate(text.splitlines(), 1):
        parts = line.split()
        yield i, parts


def parse_conf(path: str | Path) -> list[Configuration]:
    """Parse a full .conf file into validated Configuration records."""
    text = Path(path).read_text()
    lines = [(i, parts) for i, parts in _tokens(text) if parts]
    configs: list[Configuration] = []
    pos = 0

    while pos < len(lines):
        # Skip blank lines (already filtered out) — pos points at an identifier.
        lineno, parts = lines[pos]
        ident = " ".join(parts)
        pos += 1

        lineno, parts = lines[pos]
        if len(parts) != 4:
            raise ValueError(f"line {lineno}: expected 'n r a b', got {parts!r}")
        n, r, a, b = map(int, parts)
        pos += 1

        # Contract: k followed by 2k endpoints, possibly wrapped.
        nums: list[int] = []
        lineno, parts = lines[pos]
        nums.extend(int(t) for t in parts)
        pos += 1
        k = nums[0]
        while len(nums) < 1 + 2 * k:
            _, parts = lines[pos]
            nums.extend(int(t) for t in parts)
            pos += 1
        if len(nums) != 1 + 2 * k:
            raise ValueError(f"{ident}: contract token count mismatch")
        contract = [(nums[1 + 2 * i], nums[2 + 2 * i]) for i in range(k)]

        # n adjacency rows.
        adjacency: dict[int, list[int]] = {}
        for _ in range(n):
            lineno, parts = lines[pos]
            v, deg = int(parts[0]), int(parts[1])
            nbrs = [int(t) for t in parts[2:]]
            if len(nbrs) != deg:
                raise ValueError(f"{ident} line {lineno}: degree {deg} != {len(nbrs)}")
            adjacency[v] = nbrs
            pos += 1

        # n coordinates, wrapped over several lines.
        coords: list[int] = []
        while len(coords) < n and pos < len(lines):
            _, parts = lines[pos]
            coords.extend(int(t) for t in parts)
            pos += 1
        if len(coords) != n:
            raise ValueError(f"{ident}: expected {n} coords, got {len(coords)}")

        cfg = Configuration(ident, n, r, a, b, contract, adjacency, coords)
        cfg.validate()
        configs.append(cfg)

    return configs


def serialize(configs: list[Configuration]) -> str:
    """Serialize records back to the .conf token stream (normalized whitespace).

    Round-trips through parse_conf: parse(serialize(cs)) == cs. Not byte-identical
    to the originals (original files use tabs/column alignment).
    """
    out: list[str] = []
    for c in configs:
        out.append(c.ident)
        out.append(f"{c.n} {c.r} {c.a} {c.b}")
        contract_nums = [len(c.contract)] + [x for e in c.contract for x in e]
        out.append(" ".join(map(str, contract_nums)))
        for v in range(1, c.n + 1):
            nbrs = c.adjacency[v]
            out.append(f"{v} {len(nbrs)} " + " ".join(map(str, nbrs)))
        out.append(" ".join(map(str, c.coords)))
        out.append("")  # blank separator line required by reduce.c's ReadConf
    return "\n".join(out) + "\n"
