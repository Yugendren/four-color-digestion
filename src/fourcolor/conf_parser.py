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


def rotate_ring_starts(adjacency: dict[int, list[int]], r: int) -> dict[int, list[int]]:
    """Return a copy of `adjacency` with every ring vertex 1..r's neighbor
    list cyclically rotated to start at ring-neighbor i+1 (1 if i==r) and
    end at ring-neighbor i-1 (r if i==1) -- the RSST labeling convention
    (`ReadConf` condition (4); see `for_rsst_oracle`'s docstring for the
    full rationale). A pure relabel-invariant rotation: does not change
    the underlying rotation system, the edge set, or any vertex's degree.
    Interior vertices (> r) are left untouched (RSST's convention only
    constrains ring vertices' starting point)."""
    out = {v: list(nbrs) for v, nbrs in adjacency.items()}
    for i in range(1, r + 1):
        nbrs = out[i]
        expected_start = 1 if i == r else i + 1
        start_idx = nbrs.index(expected_start)
        out[i] = nbrs[start_idx:] + nbrs[:start_idx]
    return out


def for_rsst_oracle(cfg: Configuration, *, a: int | None = None,
                     b: int | None = None) -> Configuration:
    """Return a copy of `cfg` normalized so `build/reduce_rsst` (reduce.c's
    ReadConf) will accept it as well-formed.

    Two things `Configuration.validate()` does NOT enforce but ReadConf's
    condition (4) does (`third_party/arxiv-1401.6481/src/anc/reduce.c`
    lines ~988-997, also ported as the "condition (4)" check in
    `fourcolor.mutate.is_legal_configuration`): each ring vertex i's
    neighbor list must be written starting exactly at ring-neighbor i+1
    (or 1 if i==r) and ending exactly at ring-neighbor i-1 (or r if i==1),
    with every entry strictly between them being an interior vertex. Any
    valid rotation system already has this as *some* cyclic rotation of
    vertex i's list (rotation order is only defined up to starting point),
    but graph builders that don't specifically track RSST's ring-labeling
    convention (e.g. `tools/datagen.py`'s plantri relabeling, or ad hoc
    constructions in tests) can produce a list that starts elsewhere --
    reducibility is unaffected (our own checker and `Configuration.
    validate()` are rotation-start-agnostic), but the C oracle's stricter
    parser will reject it with `ReadErr(4, ...)`. This function fixes only
    that (cyclically rotating each ring vertex's list to the required
    start -- a no-op on the underlying rotation system), and additionally
    fills placeholder coordinates if `cfg.coords` is empty (ReadConf
    requires exactly n coordinate numbers to be present, and hangs/errors
    without them -- see `serialize`'s docstring comment on 8-per-line
    wrapping for the concrete failure mode). `a`/`b` override the header
    fields when given (ReadConf's `printstatus` hard-checks `a` against
    its own recomputed |C(K)| and exits nonzero on a mismatch, so callers
    should pass `a=result.n_extendable` from `fourcolor.reduce.check`).
    """
    r, n = cfg.r, cfg.n
    adjacency = rotate_ring_starts(cfg.adjacency, r)
    coords = cfg.coords if cfg.coords else [0] * n
    return Configuration(
        cfg.ident, n, r,
        cfg.a if a is None else a,
        cfg.b if b is None else b,
        list(cfg.contract), adjacency, coords,
    )


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
        # Coordinates must be wrapped at (at most) 8 per line: reduce.c's
        # ReadConf reads coordinates by calling fgets() once per line and
        # sscanf()-ing AT MOST 8 numbers from each resulting string -- any
        # numbers beyond the 8th on a single fgets'd line are silently
        # dropped (not carried over to the next iteration), and a coords
        # line with 0 parseable numbers makes sscanf return -1 (EOF), which
        # ReadConf's `if (k == 0) exit(17)` check does NOT catch (only
        # catches k==0, not k==-1) -- so a too-long or blank coords line
        # sends `i += k` backwards and the read loop free-runs off the end
        # of the file, hanging forever instead of erroring. Emitting >=1
        # coords line only when c.coords is non-empty, and never more than
        # 8 numbers per line, keeps this serializer's output readable by
        # the real reduce.c oracle for every n (round-tripping through our
        # own parse_conf is unaffected either way, since it just accumulates
        # tokens across lines until n coords are seen).
        coords = c.coords if c.coords else [0] * c.n
        for i in range(0, len(coords), 8):
            out.append(" ".join(map(str, coords[i:i + 8])))
        out.append("")  # blank separator line required by reduce.c's ReadConf
    return "\n".join(out) + "\n"
