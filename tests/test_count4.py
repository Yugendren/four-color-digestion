"""Validation of the exact 4-colouring counter used by the sharp-cap program.

`fourcolor.count4.count_proper_4colorings` underwrites every numeric claim in
`results/mass-law/PROOF-SHARP-CAP.md` (the Bridge-Lemma measurements, the
Proposition-4 barrier witness, the per-step gain profiles).  If it is wrong,
all of those are worthless -- hence three independent checks: closed forms,
brute force, and deletion-contraction.
"""

from __future__ import annotations

import itertools
import random
import unittest

from fourcolor.count4 import count_proper_4colorings, max_frontier


def _undirected(adj):
    g = {int(v): set() for v in adj}
    for v, nbrs in adj.items():
        for u in nbrs:
            g.setdefault(int(u), set()).add(int(v))
            g[int(v)].add(int(u))
    for v in g:
        g[v].discard(v)
    return g


def _brute(adj, q=4):
    g = _undirected(adj)
    vs = sorted(g)
    count = 0
    for asg in itertools.product(range(q), repeat=len(vs)):
        c = dict(zip(vs, asg))
        if all(c[u] != c[v] for u in g for v in g[u]):
            count += 1
    return count


def _chromatic_at(adj, q):
    """Deletion-contraction P(G,q), independent of the frontier DP."""
    g = _undirected(adj)
    edges = sorted({(min(u, v), max(u, v)) for u in g for v in g[u]})
    if not edges:
        return q ** len(g)
    u, v = edges[0]
    deleted = {x: set(n) for x, n in g.items()}
    deleted[u].discard(v)
    deleted[v].discard(u)
    contracted = {x: set(n) for x, n in g.items() if x != v}
    for w in g[v]:
        if w == u:
            continue
        contracted[w].discard(v)
        contracted[w].add(u)
        contracted[u].add(w)
    contracted[u].discard(v)
    return _chromatic_at(deleted, q) - _chromatic_at(contracted, q)


def _wheel(r):
    adj = {i: [(i % r) + 1, ((i - 2) % r) + 1, r + 1] for i in range(1, r + 1)}
    adj[r + 1] = list(range(1, r + 1))
    return adj


def _cycle(r):
    return {i: [(i % r) + 1, ((i - 2) % r) + 1] for i in range(1, r + 1)}


class TestCount4(unittest.TestCase):
    def test_wheel_closed_form(self):
        # P(W_r, 4) = 4 * P(C_r, 3) = 4 (2^r + 2(-1)^r) -- the sharp cap's base case
        for r in range(3, 13):
            with self.subTest(r=r):
                self.assertEqual(
                    count_proper_4colorings(_wheel(r)), 4 * (2 ** r + 2 * (-1) ** r)
                )

    def test_cycle_closed_form(self):
        for r in range(3, 13):
            with self.subTest(r=r):
                self.assertEqual(
                    count_proper_4colorings(_cycle(r)), 3 ** r + 3 * (-1) ** r
                )

    def test_complete_graph(self):
        for m in range(1, 5):
            adj = {i: [j for j in range(1, m + 1) if j != i] for i in range(1, m + 1)}
            expected = 1
            for t in range(m):
                expected *= 4 - t
            with self.subTest(m=m):
                self.assertEqual(count_proper_4colorings(adj), expected)

    def test_against_brute_force_random(self):
        rng = random.Random(20260823)
        for trial in range(25):
            n = rng.randint(3, 8)
            adj = {i: [] for i in range(1, n + 1)}
            for i in range(1, n + 1):
                for j in range(i + 1, n + 1):
                    if rng.random() < 0.5:
                        adj[i].append(j)
            with self.subTest(trial=trial):
                self.assertEqual(count_proper_4colorings(adj), _brute(adj))

    def test_against_deletion_contraction_random(self):
        rng = random.Random(4)
        for trial in range(12):
            n = rng.randint(4, 7)
            adj = {i: [] for i in range(1, n + 1)}
            for i in range(1, n + 1):
                for j in range(i + 1, n + 1):
                    if rng.random() < 0.6:
                        adj[i].append(j)
            with self.subTest(trial=trial):
                self.assertEqual(count_proper_4colorings(adj), _chromatic_at(adj, 4))

    def test_other_q_values(self):
        self.assertEqual(count_proper_4colorings(_cycle(6), q=3), 2 ** 6 + 2)
        self.assertEqual(count_proper_4colorings(_cycle(6), q=5), 4 ** 6 + 4)

    def test_max_frontier_is_sane(self):
        self.assertLessEqual(max_frontier(_cycle(9)), 2)
        self.assertLessEqual(max_frontier(_wheel(9)), 3)


if __name__ == "__main__":
    unittest.main()
