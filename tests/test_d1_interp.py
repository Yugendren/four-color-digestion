"""Fast smoke tests for fourcolor.d1_interp: hook shapes, position-group
bookkeeping, shallow/structural features, and the probe pipeline on a
~100-config slice. Uses a tiny untrained D1Transformer (not the real
checkpoint) so this runs in well under a few seconds, matching the other
test_d1_*.py smoke-test convention."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402
import torch  # noqa: E402

from fourcolor import d1_interp as di  # noqa: E402
from fourcolor.d1_encoding import encode_config  # noqa: E402
from fourcolor.d1_model import D1Transformer  # noqa: E402

CORPUS = ROOT / "data" / "d1_corpus.jsonl"
N_SMOKE = 100


def tiny_model(max_len=300):
    return D1Transformer(
        d_model=16,
        nhead=2,
        dim_feedforward=32,
        max_len=max_len,
        num_encoder_layers=2,
        num_decoder_layers=2,
    )


def load_smoke_records(n=N_SMOKE):
    """First n usable (trace is not None) records straight from the
    corpus, independent of the train/val split machinery under test."""
    records = []
    with CORPUS.open() as f:
        for line in f:
            rec = json.loads(line)
            if rec["trace"] is None:
                continue
            rec["adjacency"] = {int(v): nbrs for v, nbrs in rec["adjacency"].items()}
            records.append(rec)
            if len(records) >= n:
                break
    return records


class TestSplitReconstruction(unittest.TestCase):
    def test_load_split_matches_known_full_v1_counts(self):
        # Cross-check against results/d1/train_metrics_full_v1.json, which
        # trained with the same defaults (seed=0, val_frac=0.1, max_src/tgt
        # len=256) on the same corpus.
        train_recs, val_recs, stats = di.load_split(CORPUS)
        self.assertEqual(stats["corpus_total"], 14036)
        self.assertEqual(stats["no_trace_excluded"], 4828)
        self.assertEqual(stats["too_long_excluded"], 2649)
        self.assertEqual(stats["usable"], 6559)
        self.assertEqual(len(train_recs), 5904)
        self.assertEqual(len(val_recs), 655)

    def test_split_is_disjoint_and_deterministic(self):
        train1, val1, _ = di.load_split(CORPUS)
        train2, val2, _ = di.load_split(CORPUS)
        idents1 = {r["ident"] for r in val1}
        idents2 = {r["ident"] for r in val2}
        self.assertEqual(idents1, idents2)
        self.assertTrue(idents1.isdisjoint({r["ident"] for r in train1}))


class TestPositionGroups(unittest.TestCase):
    def test_matches_encode_config_token_for_token(self):
        for rec in load_smoke_records(20):
            ids_ref = encode_config(rec["adjacency"], rec["r"], rec["n"])
            ids, header, ring, interior = di.encode_config_with_groups(
                rec["adjacency"], rec["r"], rec["n"]
            )
            self.assertEqual(ids, ids_ref)
            all_pos = sorted(header + ring + interior)
            self.assertEqual(all_pos, list(range(len(ids))))

    def test_ring_only_config_has_empty_interior(self):
        # r == n (no interior vertices) is a degenerate but legal input to
        # this bookkeeping; interior_pos should just be empty.
        adj = {1: [2, 3], 2: [3, 1], 3: [1, 2]}
        ids, header, ring, interior = di.encode_config_with_groups(adj, 3, 3)
        self.assertEqual(interior, [])
        self.assertTrue(len(ring) > 0)


class TestEncoderCapture(unittest.TestCase):
    def test_layer_shapes_and_count(self):
        model = tiny_model()
        recs = load_smoke_records(8)
        src = di.pad_batch([encode_config(r["adjacency"], r["r"], r["n"]) for r in recs])
        layers, pad_mask = di.encode_with_layers(model, src)
        self.assertEqual(set(layers.keys()), {0, 1, 2})  # embeddings + 2 encoder layers
        for layer_id, hidden in layers.items():
            self.assertEqual(hidden.shape, (8, src.size(1), 16))
        self.assertEqual(pad_mask.shape, (8, src.size(1)))

    def test_mean_pool_excludes_padding(self):
        model = tiny_model()
        recs = load_smoke_records(8)
        src = di.pad_batch([encode_config(r["adjacency"], r["r"], r["n"]) for r in recs])
        layers, pad_mask = di.encode_with_layers(model, src)
        pooled = di.mean_pool(layers[2], pad_mask)
        self.assertEqual(pooled.shape, (8, 16))
        self.assertTrue(torch.isfinite(pooled).all())

    def test_mean_pool_positions_empty_returns_zeros(self):
        row = torch.randn(10, 16)
        out = di.mean_pool_positions(row, [])
        self.assertTrue(torch.equal(out, torch.zeros(16)))
        out2 = di.mean_pool_positions(row, [2, 5])
        self.assertTrue(torch.allclose(out2, row[[2, 5], :].mean(dim=0)))


class TestDecoderStepHidden(unittest.TestCase):
    def test_shapes(self):
        model = tiny_model()
        recs = load_smoke_records(4)
        src = di.pad_batch([encode_config(r["adjacency"], r["r"], r["n"]) for r in recs])
        step_hidden, generated = di.decode_with_step_hidden(model, src, max_steps=5)
        self.assertEqual(step_hidden.shape, (5, 4, 16))
        self.assertEqual(generated.shape, (4, 6))  # BOS + 5 generated steps


class TestFeatures(unittest.TestCase):
    def test_shallow_feature_vector_length_matches_names(self):
        recs = load_smoke_records(10)
        for rec in recs:
            vec = di.shallow_feature_vector(rec["adjacency"], rec["r"], rec["n"])
            self.assertEqual(len(vec), len(di.SHALLOW_FEATURE_NAMES))

    def test_structural_candidates_keys(self):
        recs = load_smoke_records(10)
        for rec in recs:
            feats = di.structural_candidates(
                rec["adjacency"], rec["r"], rec["n"], rec["n_extendable"], rec["n_consistent"]
            )
            self.assertEqual(set(feats.keys()), set(di.STRUCTURAL_FEATURE_NAMES))
            # n_consistent == 0 iff d_reducible (fourcolor.reduce's own
            # definition); this is a tautological sanity check, not a
            # discovery.
            self.assertEqual(feats["n_consistent"] == 0.0, rec["d_reducible"])


class TestProbePipeline(unittest.TestCase):
    def setUp(self):
        self.recs = load_smoke_records(N_SMOKE)
        self.labels = [r["d_reducible"] for r in self.recs]

    def test_stratified_split_covers_all_indices_no_overlap(self):
        train_idx, test_idx = di.stratified_split(self.labels, test_frac=0.2, seed=0)
        self.assertEqual(set(train_idx).isdisjoint(test_idx), True)
        self.assertEqual(sorted(train_idx + test_idx), list(range(len(self.labels))))
        self.assertGreater(len(test_idx), 0)

    def test_probe_pipeline_shallow_features_runs_end_to_end(self):
        X = torch.tensor(
            [di.shallow_feature_vector(r["adjacency"], r["r"], r["n"]) for r in self.recs],
            dtype=torch.float32,
        )
        y = torch.tensor([1 if lab else 0 for lab in self.labels], dtype=torch.long)
        train_idx, test_idx = di.stratified_split(self.labels, test_frac=0.2, seed=0)
        X_train, X_test, _, _ = di.standardize(X[train_idx], X[test_idx])
        result = di.train_logistic_probe(
            X_train, y[train_idx], X_test, y[test_idx], epochs=50
        )
        self.assertIn("test_acc", result)
        self.assertGreaterEqual(result["test_acc"], 0.0)
        self.assertLessEqual(result["test_acc"], 1.0)
        self.assertEqual(result["n_test"], len(test_idx))
        point, lo, hi = di.bootstrap_ci(result["test_correct"], n_boot=200)
        self.assertLessEqual(lo, point)
        self.assertLessEqual(point, hi)

    def test_probe_pipeline_on_encoder_features(self):
        model = tiny_model()
        src = di.pad_batch(
            [encode_config(r["adjacency"], r["r"], r["n"]) for r in self.recs]
        )
        layers, pad_mask = di.encode_with_layers(model, src)
        pooled = di.mean_pool(layers[2], pad_mask)
        y = torch.tensor([1 if lab else 0 for lab in self.labels], dtype=torch.long)
        train_idx, test_idx = di.stratified_split(self.labels, test_frac=0.2, seed=0)
        X_train, X_test, _, _ = di.standardize(pooled[train_idx], pooled[test_idx])
        result = di.train_logistic_probe(X_train, y[train_idx], X_test, y[test_idx], epochs=50)
        self.assertGreaterEqual(result["test_acc"], 0.0)
        scores = di.probe_direction_scores(result["probe"], X_test)
        self.assertEqual(scores.shape, (len(test_idx),))


class TestCorrelation(unittest.TestCase):
    def test_pearson_perfect_linear(self):
        x = np.arange(20, dtype=float)
        y = 3 * x + 1
        self.assertAlmostEqual(di.pearsonr(x, y), 1.0, places=6)

    def test_pearson_perfect_negative(self):
        x = np.arange(20, dtype=float)
        y = -2 * x + 5
        self.assertAlmostEqual(di.pearsonr(x, y), -1.0, places=6)

    def test_spearman_monotonic_nonlinear(self):
        x = np.arange(1, 21, dtype=float)
        y = x**3  # monotonic but nonlinear -- spearman should still be 1.0
        self.assertAlmostEqual(di.spearmanr(x, y), 1.0, places=6)

    def test_spearman_handles_ties(self):
        x = np.array([1.0, 1.0, 2.0, 3.0, 3.0])
        y = np.array([1.0, 2.0, 2.0, 3.0, 4.0])
        r = di.spearmanr(x, y)
        self.assertGreater(r, 0.0)
        self.assertLessEqual(r, 1.0)


if __name__ == "__main__":
    unittest.main()
