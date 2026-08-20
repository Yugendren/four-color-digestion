"""Tests for fourcolor.canonical and fourcolor.d1_encoding: canonicalization
invariance, encoding determinism/round-trip, vocabulary size, bucketing."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fourcolor.canonical import canonical_key, canonical_labeling  # noqa: E402
from fourcolor.d1_encoding import (  # noqa: E402
    MAG_CAP,
    STOI,
    VOCAB_SIZE,
    decode_verdict,
    encode_config,
    encode_trace,
    surv_bucket,
)

# A small ring-6 configuration (RSST-style numbering: ring 1..6 cyclic,
# interior 7..8), taken from data/configs_r6_n8-12.jsonl gen-r6-n8-1.
SAMPLE_ADJ = {
    1: [2, 7, 8, 6],
    2: [1, 3, 7],
    7: [1, 2, 3, 4, 8],
    8: [1, 7, 4, 5, 6],
    6: [1, 8, 5],
    3: [2, 4, 7],
    4: [7, 3, 5, 8],
    5: [8, 4, 6],
}
SAMPLE_R, SAMPLE_N = 6, 8


def relabel(adjacency, r, n, start, direction):
    """Build an equivalent adjacency dict under a ring rotation-start +
    reflection, independently of fourcolor.canonical (a hand-rolled
    reference relabeling for the invariance test)."""
    ring_new = {v: ((direction * (v - start)) % r) + 1 for v in range(1, r + 1)}
    # Interior vertices: just shift labels by a constant offset and mark
    # with a different (but still valid, since only relative structure
    # matters to canonicalization) permutation -- reuse canonical.py's own
    # BFS labeling machinery is circular, so instead we simply keep interior
    # labels unchanged (still a valid, merely differently-numbered adjacency
    # dict for the purpose of this invariance check: only ring relabeling +
    # optional reflection is exercised here).
    label = dict(ring_new)
    for v in range(r + 1, n + 1):
        label[v] = v
    inv = {new: old for old, new in label.items()}
    new_adj = {}
    for new_v in range(1, n + 1):
        old_v = inv[new_v]
        nbrs = adjacency[old_v]
        if direction == -1:
            nbrs = list(reversed(nbrs))
        new_adj[new_v] = [label[u] for u in nbrs]
    return new_adj


class TestCanonical(unittest.TestCase):
    def test_invariant_under_rotation_and_reflection(self):
        base_key = canonical_key(SAMPLE_ADJ, SAMPLE_R, SAMPLE_N)
        for start in range(1, SAMPLE_R + 1):
            for direction in (1, -1):
                variant = relabel(SAMPLE_ADJ, SAMPLE_R, SAMPLE_N, start, direction)
                self.assertEqual(
                    canonical_key(variant, SAMPLE_R, SAMPLE_N),
                    base_key,
                    f"start={start} direction={direction}",
                )

    def test_different_configs_different_keys(self):
        other_adj = {
            1: [2, 7, 6],
            2: [1, 3, 8, 7],
            7: [1, 2, 8, 9, 6],
            6: [1, 7, 9, 5],
            3: [2, 4, 8],
            8: [2, 3, 4, 9, 7],
            9: [7, 8, 4, 5, 6],
            5: [6, 9, 4],
            4: [3, 5, 9, 8],
        }
        key_a = canonical_key(SAMPLE_ADJ, SAMPLE_R, SAMPLE_N)
        key_b = canonical_key(other_adj, 6, 9)
        self.assertNotEqual(key_a, key_b)

    def test_canonical_labeling_self_consistent(self):
        label, start, direction = canonical_labeling(SAMPLE_ADJ, SAMPLE_R, SAMPLE_N)
        self.assertEqual(set(label.keys()), set(range(1, SAMPLE_N + 1)))
        self.assertEqual(set(label.values()), set(range(1, SAMPLE_N + 1)))


class TestEncoding(unittest.TestCase):
    def test_vocab_size_under_64(self):
        self.assertLess(VOCAB_SIZE, 64)

    def test_encode_config_deterministic_under_relabeling(self):
        base_ids = encode_config(SAMPLE_ADJ, SAMPLE_R, SAMPLE_N)
        variant = relabel(SAMPLE_ADJ, SAMPLE_R, SAMPLE_N, start=3, direction=-1)
        variant_ids = encode_config(variant, SAMPLE_R, SAMPLE_N)
        self.assertEqual(base_ids, variant_ids)

    def test_encode_config_starts_with_ring_n_header(self):
        ids = encode_config(SAMPLE_ADJ, SAMPLE_R, SAMPLE_N)
        self.assertEqual(ids[0], STOI["RING"])
        self.assertEqual(ids[1], STOI[f"MAG_{SAMPLE_R}"])
        self.assertEqual(ids[2], STOI["N"])
        self.assertEqual(ids[3], STOI[f"MAG_{SAMPLE_N}"])

    def test_encode_config_all_ids_in_vocab_range(self):
        ids = encode_config(SAMPLE_ADJ, SAMPLE_R, SAMPLE_N)
        for i in ids:
            self.assertGreaterEqual(i, 0)
            self.assertLess(i, VOCAB_SIZE)

    def test_surv_bucket_matches_spec_doubling_scheme(self):
        expected = {0: 0, 1: 1, 2: 2, 3: 2, 4: 3, 7: 3, 8: 4, 15: 4, 16: 5}
        for count, bucket in expected.items():
            self.assertEqual(surv_bucket(count), bucket, count)

    def test_surv_bucket_clamped_at_cap(self):
        self.assertLessEqual(surv_bucket(10**9), MAG_CAP)

    def test_encode_trace_and_decode_verdict_round_trip(self):
        trace = [106, 10, 8, 4, 1, 0]
        ids_true = encode_trace(trace, d_reducible=True)
        self.assertTrue(ids_true[0] == STOI["BOS"] and ids_true[-1] == STOI["EOS"])
        self.assertEqual(decode_verdict(ids_true), True)

        ids_false = encode_trace([50, 40, 40], d_reducible=False)
        self.assertEqual(decode_verdict(ids_false), False)

    def test_decode_verdict_missing_returns_none(self):
        self.assertIsNone(decode_verdict([STOI["BOS"], STOI["ROUND"], STOI["EOS"]]))

    def test_encode_trace_round_count_matches_trace_length(self):
        trace = [10, 5, 0]
        ids = encode_trace(trace, d_reducible=True)
        n_round = sum(1 for i in ids if i == STOI["ROUND"])
        self.assertEqual(n_round, len(trace))


if __name__ == "__main__":
    unittest.main()
