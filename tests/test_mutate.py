"""Tests for fourcolor.mutate's diagonal edge-flip operator and legality
gate. Ground truth for the legality gate is the RSST reference oracle's own
well-formedness predicate (ported by hand from `third_party/arxiv-1401.6481/
src/anc/reduce.c`'s `ReadConf`); the flip's own correctness is checked by
round-tripping (flip the new diagonal back and recover the original cyclic
adjacency exactly) and by the near-triangulation edge/triangle-count
invariant, independently derived from Euler's formula."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fourcolor.conf_parser import Configuration  # noqa: E402
from fourcolor.mutate import (  # noqa: E402
    flip_edge,
    flippable_edges,
    is_legal_configuration,
    random_flip_mutants,
    ring_edges,
)
from fourcolor.reduce import _edges_and_triangles  # noqa: E402

D1_CORPUS = ROOT / "data" / "d1_corpus.jsonl"


def _load_records(r_filter=None, n_min=0, limit=5):
    out = []
    with D1_CORPUS.open() as f:
        for line in f:
            rec = json.loads(line)
            if r_filter is not None and rec["r"] != r_filter:
                continue
            if rec["n"] < n_min:
                continue
            out.append(rec)
            if len(out) >= limit:
                break
    return out


class TestRingEdges(unittest.TestCase):
    def test_ring_edges_r6(self):
        self.assertEqual(
            ring_edges(6),
            {frozenset(e) for e in [(1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 1)]},
        )

    def test_ring_edge_not_flippable(self):
        rec = _load_records(r_filter=6, limit=1)[0]
        adj = {int(k): v for k, v in rec["adjacency"].items()}
        self.assertIsNone(flip_edge(adj, 6, 1, 2))


class TestFlipRoundTrip(unittest.TestCase):
    def test_flip_then_flip_back_restores_adjacency(self):
        for rec in _load_records(r_filter=14, n_min=25, limit=2):
            adj = {int(k): v for k, v in rec["adjacency"].items()}
            r, n = rec["r"], rec["n"]
            for (u, v) in flippable_edges(adj, r):
                res = flip_edge(adj, r, u, v)
                if res is None:
                    continue
                back = flip_edge(res.adjacency, r, res.a, res.b)
                self.assertIsNotNone(back, f"round-trip flip failed for {u},{v}")
                self.assertTrue(
                    _same_cyclic_adjacency(adj, back.adjacency),
                    f"round-trip mismatch for edge {u},{v}",
                )

    def test_flip_preserves_edge_triangle_count_invariant(self):
        rec = _load_records(r_filter=13, n_min=24, limit=1)[0]
        adj = {int(k): v for k, v in rec["adjacency"].items()}
        r, n = rec["r"], rec["n"]
        for (u, v) in flippable_edges(adj, r):
            res = flip_edge(adj, r, u, v)
            if res is None:
                continue
            cfg = Configuration("mut", n, r, -1, -1, [], res.adjacency, [])
            cfg.validate()
            edges, triangles = _edges_and_triangles(cfg)
            self.assertEqual(len(edges), 3 * n - r - 3)
            self.assertEqual(len(triangles), 2 * n - r - 2)


def _same_cyclic_adjacency(a1, a2) -> bool:
    if set(a1) != set(a2):
        return False
    for k in a1:
        l1, l2 = a1[k], a2[k]
        if len(l1) != len(l2):
            return False
        if not l1:
            continue
        if l1[0] not in l2:
            return False
        i = l2.index(l1[0])
        if l2[i:] + l2[:i] != l1:
            return False
    return True


class TestLegalityGate(unittest.TestCase):
    def test_pool_configs_are_legal(self):
        for rec in _load_records(limit=200):
            adj = {int(k): v for k, v in rec["adjacency"].items()}
            self.assertTrue(
                is_legal_configuration(adj, rec["r"], rec["n"]),
                f"pool config {rec['ident']} should be legal",
            )

    def test_ring_degree_2_is_illegal(self):
        # Minimal r=6 config with vertex 1's ring-degree artificially
        # dropped to 2 (remove its one interior chord) -- RSST condition
        # (2) requires ring-vertex degree >= 3.
        rec = _load_records(r_filter=6, limit=1)[0]
        adj = {int(k): list(v) for k, v in rec["adjacency"].items()}
        # vertex 1 has neighbors [2, 7, 10, 6] in this record; strip the
        # interior chords to leave only its two ring neighbors.
        r = rec["r"]
        ring_nbrs = [u for u in adj[1] if u <= r]
        if len(ring_nbrs) == 2 and len(adj[1]) > 2:
            adj[1] = ring_nbrs
            self.assertFalse(is_legal_configuration(adj, r, rec["n"]))

    def test_random_flip_mutants_all_pass_or_get_filtered(self):
        import random

        rec = _load_records(r_filter=14, n_min=25, limit=1)[0]
        adj = {int(k): v for k, v in rec["adjacency"].items()}
        r, n = rec["r"], rec["n"]
        rng = random.Random(0)
        mutants = random_flip_mutants(adj, r, n, rng, max_tries=50)
        self.assertGreater(len(mutants), 0)
        legal = [m for m in mutants if is_legal_configuration(m, r, n)]
        self.assertGreater(len(legal), 0)


if __name__ == "__main__":
    unittest.main()
