"""Unified view over every LABELED configuration this repo holds -- the
corpus the lemma-testing harness (`fourcolor.lemma_harness`, `tools/
test_lemma.py`) machine-checks candidate mass-law statements against.

Four families of JSONL feed it (see 03-MASS-LAW-PROGRAM.md):

  * `data/d1_corpus.jsonl`            -- the D1 pool: catalog configurations
    (rsst633, stein2822, nl4ct_pool, ...) plus generated ones. Carries
    `trace`, `canonical_key`, and a per-record `source` tag. This is where
    the D-REDUCIBLE population lives (rings 6-16).
  * `data/v2/traces_r{8,9,10}.jsonl`  -- the D1-v2 per-round SET traces.
    Same configurations re-run with the full surviving-set recorded each
    round (`set_trace`); ~90KB per line, so this loader never json-parses
    them unless a predicate actually asks for adjacency/trace.
  * `results/theorem/fr_table/configs_r*.jsonl` -- the f(r) theorem's
    exhaustive BELOW-THRESHOLD enumerations (every valid configuration with
    interior < f(r), rings 8-13; all non-reducible, that is the theorem).
  * `data/configs_r*.jsonl`           -- the older generator's pools.

Dedup is by `fourcolor.canonical.canonical_key` (ring-dihedral canonical
form), using the precomputed `canonical_key` field when a source carries
one and computing it otherwise; the first file in `SOURCE_SPECS` order
wins and later duplicates are recorded in `dup_sources`. Records sharing a
canonical key but disagreeing on `d_reducible` are collected as
`conflicts` (a data-integrity alarm, not expected).

Two design points that matter for the harness:

  * SCALAR FIELDS ARE EAGER, STRUCTURE IS LAZY. Building the index scans
    each line with regexes for the header scalars (ident/source/r/n/
    n_extendable/n_consistent/rounds/d_reducible/canonical_key) and stores
    the line's byte offset. `rec.adjacency` / `rec.trace` / `rec.features`
    seek back into the file and json-parse that one line on first access.
    So a purely scalar predicate over ~60k configs never touches the
    ~460MB of v2 trace payload.
  * THE INDEX IS CACHED. Per source file, keyed by (size, mtime_ns), under
    `.cache/lemma_corpus/`. First build pays the canonicalization cost for
    the ~45k records whose file has no `canonical_key` (~30s); later loads
    are ~1s. `load_corpus(rebuild=True)` forces a rescan.

Field naming follows the mass-law write-up rather than the JSONL headers:
`a` = n_extendable = |Phi(K)|, `b` = n_consistent (0 iff D-reducible),
`k` = n - r = interior vertex count.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

from fourcolor.canonical import canonical_key

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / ".cache" / "lemma_corpus"

# (group tag, path-or-glob relative to ROOT). Order is dedup priority:
# richer / more authoritative sources first.
SOURCE_SPECS: list[tuple[str, str]] = [
    ("d1_corpus", "data/d1_corpus.jsonl"),
    ("v2_traces", "data/v2/traces_r*.jsonl"),
    ("fr_table", "results/theorem/fr_table/configs_r*.jsonl"),
    ("gen_configs", "data/configs_r*.jsonl"),
]

# Scalar fields exposed to vectorized predicates (see lemma_harness).
SCALAR_FIELDS = ("r", "n", "k", "a", "b", "d_reducible", "rounds")

# Header scalars live at the front of every record; the v2 trace lines put
# their ~90KB `set_trace` after them and `canonical_key` at the very end.
_HEAD_BYTES = 8192

_PATTERNS = {
    "ident": re.compile(r'"ident"\s*:\s*"([^"]*)"'),
    "source": re.compile(r'"source"\s*:\s*"([^"]*)"'),
    "r": re.compile(r'"r"\s*:\s*(-?\d+)'),
    "n": re.compile(r'"n"\s*:\s*(-?\d+)'),
    "a": re.compile(r'"n_extendable"\s*:\s*(-?\d+)'),
    "b": re.compile(r'"n_consistent"\s*:\s*(-?\d+)'),
    "rounds": re.compile(r'"rounds"\s*:\s*(-?\d+)'),
    "d_reducible": re.compile(r'"d_reducible"\s*:\s*(true|false)'),
}
_CK_PATTERN = re.compile(r'"canonical_key"\s*:\s*"([^"]*)"')
_ADJ_PATTERN = re.compile(r'[,{]\s*"adjacency"\s*:')
_TRACE_PATTERN = re.compile(r'[,{]\s*"(set_trace|trace)"\s*:')

INDEX_VERSION = 1

# Above this line length, `ConfigRecord.raw()` re-parses instead of caching.
RAW_CACHE_MAX_BYTES = 65536


def _canon_hash(key: str) -> str:
    return hashlib.blake2b(key.encode(), digest_size=10).hexdigest()


@dataclass(slots=True)
class ConfigRecord:
    """One labeled configuration. Scalars are eager; `adjacency`, `trace`,
    `raw` and `features` lazily re-read and parse the source line."""

    ident: str
    source: str
    group: str
    source_file: str
    r: int
    n: int
    a: int
    b: int
    d_reducible: bool
    rounds: int
    canonical_hash: str
    has_adjacency: bool
    has_trace: bool
    path: Path
    offset: int
    dup_sources: list[str] = field(default_factory=list)
    _raw: dict[str, Any] | None = None
    _features: dict[str, float] | None = None

    @property
    def k(self) -> int:
        """Interior vertex count."""
        return self.n - self.r

    def raw(self) -> dict[str, Any]:
        """The full JSON record, parsed on demand.

        Cached on the instance only for lines under `RAW_CACHE_MAX_BYTES`: the
        v2 trace lines are ~90KB each, and caching all 4.6k of them while a
        structure-dependent predicate sweeps the corpus would cost GBs for no
        benefit (a sweep visits each record once)."""
        if self._raw is not None:
            return self._raw
        with self.path.open("rb") as f:
            f.seek(self.offset)
            line = f.readline()
        parsed = json.loads(line.decode())
        if len(line) <= RAW_CACHE_MAX_BYTES:
            self._raw = parsed
        return parsed

    @property
    def adjacency(self) -> dict[int, list[int]] | None:
        """Rotation-system adjacency with int keys, or None if absent."""
        adj = self.raw().get("adjacency")
        if adj is None:
            return None
        return {int(v): list(nbrs) for v, nbrs in adj.items()}

    @property
    def trace(self) -> list[int] | None:
        """Per-round surviving-consistent-set SIZES (last entry == b).
        Derived from `set_trace` lengths on the v2 sources, which record
        the sets themselves rather than the counts."""
        raw = self.raw()
        if "trace" in raw:
            return list(raw["trace"])
        if "set_trace" in raw:
            return [len(s) for s in raw["set_trace"]]
        return None

    @property
    def set_trace(self) -> list[list[int]] | None:
        """The v2 sources' full per-round surviving colour-index sets."""
        st = self.raw().get("set_trace")
        return None if st is None else [list(s) for s in st]

    @property
    def canonical_key(self) -> str:
        """Full canonical form (recomputed from adjacency; the index only
        keeps a 20-hex-digit hash of it)."""
        raw = self.raw()
        ck = raw.get("canonical_key")
        if ck:
            return str(ck)
        adj = self.adjacency
        if adj is None:
            raise ValueError(f"{self.ident}: no adjacency, cannot canonicalize")
        return canonical_key(adj, self.r, self.n)

    @property
    def features(self) -> dict[str, float]:
        """Shallow + structural + arrangement hand-features (lazily imports
        `fourcolor.d1_interp`, which pulls in torch, and
        `fourcolor.d1_features`). Cached per record."""
        if self._features is None:
            from fourcolor import d1_features as dfeat
            from fourcolor import d1_interp as di

            adj = self.adjacency
            if adj is None:
                raise ValueError(f"{self.ident}: no adjacency, cannot featurize")
            feats: dict[str, float] = {}
            feats.update(di.shallow_features(adj, self.r, self.n))
            feats.update(di.structural_candidates(adj, self.r, self.n, self.a, self.b))
            feats.update(dfeat.arrangement_features(adj, self.r, self.n))
            self._features = feats
        return self._features

    def f(self, name: str) -> float:
        """Shorthand for `rec.features[name]`, for use inside predicates."""
        return self.features[name]

    def label(self) -> str:
        return f"{self.ident} [{self.group}/{self.source}]"


def _scan_file(path: Path, group: str) -> list[dict[str, Any]]:
    """Regex-scan one JSONL into index rows, falling back to a full JSON
    parse for any line whose header scalars aren't all in the first
    `_HEAD_BYTES`."""
    rows: list[dict[str, Any]] = []
    offset = 0
    with path.open("rb") as fh:
        for raw_line in fh:
            start = offset
            offset += len(raw_line)
            if not raw_line.strip():
                continue
            line = raw_line.decode()
            head = line[:_HEAD_BYTES]
            row: dict[str, Any] = {"o": start}
            ok = True
            for name, pat in _PATTERNS.items():
                m = pat.search(head)
                if m is None:
                    if name in ("ident", "source"):
                        row[name] = None
                        continue
                    ok = False
                    break
                row[name] = m.group(1)
            if not ok:
                rows.append(_row_from_json(json.loads(line), start, path, group))
                continue
            row["adj"] = bool(_ADJ_PATTERN.search(head))
            row["tr"] = bool(_TRACE_PATTERN.search(head))
            pos = line.rfind('"canonical_key"')
            ck = None
            if pos >= 0:
                m = _CK_PATTERN.search(line, pos)
                if m is not None:
                    ck = m.group(1)
            if ck is None:
                rec = json.loads(line)
                adj = {int(v): nbrs for v, nbrs in rec["adjacency"].items()}
                ck = canonical_key(adj, int(rec["r"]), int(rec["n"]))
            rows.append(
                {
                    "ident": row["ident"],
                    "source": row["source"],
                    "r": int(row["r"]),
                    "n": int(row["n"]),
                    "a": int(row["a"]),
                    "b": int(row["b"]),
                    "rounds": int(row["rounds"]),
                    "d": row["d_reducible"] == "true",
                    "ck": _canon_hash(ck),
                    "adj": row["adj"],
                    "tr": row["tr"],
                    "o": start,
                }
            )
    return rows


def _row_from_json(rec: dict[str, Any], offset: int, path: Path, group: str) -> dict[str, Any]:
    ck = rec.get("canonical_key")
    if not ck:
        adj = {int(v): nbrs for v, nbrs in rec["adjacency"].items()}
        ck = canonical_key(adj, int(rec["r"]), int(rec["n"]))
    return {
        "ident": rec.get("ident"),
        "source": rec.get("source"),
        "r": int(rec["r"]),
        "n": int(rec["n"]),
        "a": int(rec["n_extendable"]),
        "b": int(rec["n_consistent"]),
        "rounds": int(rec["rounds"]),
        "d": bool(rec["d_reducible"]),
        "ck": _canon_hash(str(ck)),
        "adj": "adjacency" in rec,
        "tr": ("trace" in rec) or ("set_trace" in rec),
        "o": offset,
    }


def _cache_path(path: Path) -> Path:
    tag = hashlib.blake2b(str(path).encode(), digest_size=8).hexdigest()
    return CACHE_DIR / f"{path.stem}.{tag}.json"


def index_file(path: Path, group: str, use_cache: bool = True, rebuild: bool = False) -> list[dict[str, Any]]:
    """Index rows for one source file, memoized on disk by (size, mtime)."""
    st = path.stat()
    cache = _cache_path(path)
    if use_cache and not rebuild and cache.exists():
        try:
            blob = json.loads(cache.read_text())
            if (
                blob.get("version") == INDEX_VERSION
                and blob.get("size") == st.st_size
                and blob.get("mtime_ns") == st.st_mtime_ns
            ):
                return blob["rows"]
        except (json.JSONDecodeError, KeyError):
            pass
    rows = _scan_file(path, group)
    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = cache.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {
                    "version": INDEX_VERSION,
                    "path": str(path),
                    "size": st.st_size,
                    "mtime_ns": st.st_mtime_ns,
                    "rows": rows,
                }
            )
        )
        tmp.replace(cache)
    return rows


def source_files(specs: Iterable[tuple[str, str]] | None = None) -> list[tuple[str, Path]]:
    """Resolve SOURCE_SPECS to existing (group, path) pairs, in priority order."""
    out: list[tuple[str, Path]] = []
    for group, spec in specs if specs is not None else SOURCE_SPECS:
        if any(ch in spec for ch in "*?["):
            base = ROOT
            for p in sorted(base.glob(spec)):
                out.append((group, p))
        else:
            p = ROOT / spec
            if p.exists():
                out.append((group, p))
    return out


class Corpus:
    """Deduped collection of `ConfigRecord`s plus numpy columns for the
    scalar fields (so scalar predicates evaluate vectorized)."""

    def __init__(self, records: list[ConfigRecord], stats: dict[str, Any]):
        import numpy as np

        self.records = records
        self.stats = stats
        self.r = np.array([rec.r for rec in records], dtype=np.int64)
        self.n = np.array([rec.n for rec in records], dtype=np.int64)
        self.k = self.n - self.r
        self.a = np.array([rec.a for rec in records], dtype=np.int64)
        self.b = np.array([rec.b for rec in records], dtype=np.int64)
        self.rounds = np.array([rec.rounds for rec in records], dtype=np.int64)
        self.d_reducible = np.array([rec.d_reducible for rec in records], dtype=bool)

    def __len__(self) -> int:
        return len(self.records)

    def __iter__(self) -> Iterator[ConfigRecord]:
        return iter(self.records)

    def columns(self) -> dict[str, Any]:
        return {
            "r": self.r,
            "n": self.n,
            "k": self.k,
            "a": self.a,
            "b": self.b,
            "rounds": self.rounds,
            "d_reducible": self.d_reducible,
        }

    def subset(self, mask) -> "Corpus":
        recs = [rec for rec, m in zip(self.records, mask) if m]
        stats = dict(self.stats)
        stats["filtered_from"] = len(self.records)
        return Corpus(recs, stats)

    def summary(self) -> dict[str, Any]:
        """Per-source and per-ring counts + adjacency/trace coverage."""
        per_group: dict[str, dict[str, int]] = {}
        per_source: dict[str, int] = {}
        per_ring: dict[int, dict[str, int]] = {}
        for rec in self.records:
            g = per_group.setdefault(rec.group, {"kept": 0, "d_reducible": 0})
            g["kept"] += 1
            g["d_reducible"] += int(rec.d_reducible)
            per_source[f"{rec.group}/{rec.source}"] = per_source.get(f"{rec.group}/{rec.source}", 0) + 1
            ring = per_ring.setdefault(
                rec.r, {"n": 0, "d_reducible": 0, "with_adjacency": 0, "with_trace": 0, "k_min": rec.k, "k_max": rec.k}
            )
            ring["n"] += 1
            ring["d_reducible"] += int(rec.d_reducible)
            ring["with_adjacency"] += int(rec.has_adjacency)
            ring["with_trace"] += int(rec.has_trace)
            ring["k_min"] = min(ring["k_min"], rec.k)
            ring["k_max"] = max(ring["k_max"], rec.k)
        for group, raw in self.stats.get("raw_per_group", {}).items():
            per_group.setdefault(group, {"kept": 0, "d_reducible": 0})["raw"] = raw
        return {
            "n_records": len(self.records),
            "n_raw": self.stats.get("n_raw"),
            "n_duplicates": self.stats.get("n_duplicates"),
            "n_files": self.stats.get("n_files"),
            "n_conflicts": len(self.stats.get("conflicts", [])),
            "with_adjacency": sum(rec.has_adjacency for rec in self.records),
            "with_trace": sum(rec.has_trace for rec in self.records),
            "n_d_reducible": int(self.d_reducible.sum()) if len(self.records) else 0,
            "per_group": per_group,
            "per_source": dict(sorted(per_source.items())),
            "per_ring": {r: per_ring[r] for r in sorted(per_ring)},
        }

    def signature(self) -> str:
        """Stable content hash of the corpus (which configs, which labels) --
        the 'coverage' half of a lemma_log receipt."""
        h = hashlib.blake2b(digest_size=10)
        for rec in sorted(self.records, key=lambda x: x.canonical_hash):
            h.update(f"{rec.canonical_hash}:{rec.r}:{rec.n}:{rec.a}:{rec.b}:{int(rec.d_reducible)}|".encode())
        return h.hexdigest()


def load_corpus(
    specs: Iterable[tuple[str, str]] | None = None,
    use_cache: bool = True,
    rebuild: bool = False,
) -> Corpus:
    """Load every labeled configuration, deduped by canonical form."""
    files = source_files(specs)
    seen: dict[str, ConfigRecord] = {}
    records: list[ConfigRecord] = []
    conflicts: list[dict[str, Any]] = []
    raw_per_group: dict[str, int] = {}
    n_raw = 0
    for group, path in files:
        rows = index_file(path, group, use_cache=use_cache, rebuild=rebuild)
        raw_per_group[group] = raw_per_group.get(group, 0) + len(rows)
        n_raw += len(rows)
        for row in rows:
            ck = row["ck"]
            prev = seen.get(ck)
            if prev is not None:
                if prev.d_reducible != row["d"]:
                    conflicts.append(
                        {
                            "canonical_hash": ck,
                            "kept": prev.label(),
                            "kept_d_reducible": prev.d_reducible,
                            "other": f"{row['ident']} [{group}/{path.name}]",
                            "other_d_reducible": row["d"],
                        }
                    )
                prev.dup_sources.append(f"{path.name}:{row['source'] or group}")
                continue
            rec = ConfigRecord(
                ident=row["ident"] or f"{path.stem}:{row['o']}",
                source=row["source"] or group,
                group=group,
                source_file=path.name,
                r=row["r"],
                n=row["n"],
                a=row["a"],
                b=row["b"],
                d_reducible=row["d"],
                rounds=row["rounds"],
                canonical_hash=ck,
                has_adjacency=row["adj"],
                has_trace=row["tr"],
                path=path,
                offset=row["o"],
            )
            seen[ck] = rec
            records.append(rec)
    stats = {
        "n_raw": n_raw,
        "n_duplicates": n_raw - len(records),
        "n_files": len(files),
        "raw_per_group": raw_per_group,
        "conflicts": conflicts,
        "files": [str(p.relative_to(ROOT)) for _, p in files],
    }
    return Corpus(records, stats)
