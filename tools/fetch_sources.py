#!/usr/bin/env python3
"""Fetch and pin the primary 4CT proof artifacts from arXiv.

Downloads the e-print tarballs for:
  1401.6481  RSST "Reducibility in the Four-Color Theorem"  (reduce.c, unavoidable.conf)
  1401.6485  RSST "Discharging cartwheels"                  (discharge.c, rules, present7-11)
  0905.0043  Steinberger D-only proof                       (U_2822.conf, modified programs)
  2603.24880 Inoue et al. near-linear 4CT (the 2026 paper)  (main__1___1_.tex, tikz/rule.tex)

Each tarball is stored under third_party/<id>/archive.tar.gz, extracted into
third_party/<id>/src/, and its sha256 recorded in third_party/CHECKSUMS.sha256.
Re-running verifies existing archives against recorded hashes instead of
re-downloading.
"""

import hashlib
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THIRD_PARTY = ROOT / "third_party"
CHECKSUMS = THIRD_PARTY / "CHECKSUMS.sha256"

SOURCES = {
    "arxiv-1401.6481": "https://arxiv.org/e-print/1401.6481",
    "arxiv-1401.6485": "https://arxiv.org/e-print/1401.6485",
    "arxiv-0905.0043": "https://arxiv.org/e-print/0905.0043",
    "arxiv-2603.24880": "https://arxiv.org/e-print/2603.24880",
}

UA = {"User-Agent": "Mericanii-fourcolor-digestion/0.1 (research; contact via repo)"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_recorded() -> dict[str, str]:
    recorded = {}
    if CHECKSUMS.exists():
        for line in CHECKSUMS.read_text().splitlines():
            if line.strip():
                digest, name = line.split(None, 1)
                recorded[name.strip()] = digest
    return recorded


def main() -> int:
    THIRD_PARTY.mkdir(exist_ok=True)
    recorded = load_recorded()
    failures = []

    for name, url in SOURCES.items():
        dest_dir = THIRD_PARTY / name
        dest_dir.mkdir(exist_ok=True)
        archive = dest_dir / "archive.tar.gz"
        rel = f"{name}/archive.tar.gz"

        if not archive.exists():
            print(f"fetching {url} -> {archive}")
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as resp, archive.open("wb") as out:
                out.write(resp.read())

        digest = sha256(archive)
        if rel in recorded:
            if recorded[rel] != digest:
                failures.append(f"HASH MISMATCH {rel}: recorded {recorded[rel]}, got {digest}")
                continue
            print(f"verified {rel} {digest[:16]}...")
        else:
            recorded[rel] = digest
            print(f"pinned   {rel} {digest[:16]}...")

        extract_dir = dest_dir / "src"
        if not extract_dir.exists():
            extract_dir.mkdir()
            with tarfile.open(archive, "r:gz") as tf:
                tf.extractall(extract_dir, filter="data")
            print(f"extracted -> {extract_dir}")

    CHECKSUMS.write_text(
        "".join(f"{digest}  {name}\n" for name, digest in sorted(recorded.items()))
    )

    if failures:
        for f in failures:
            print(f, file=sys.stderr)
        return 1
    print("all sources present and pinned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
