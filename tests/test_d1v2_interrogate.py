"""Fast unit tests for tools/d1v2_interrogate.py's pure helpers (split
verification, boundary slicing, the pre-registered CI decision rule,
dynamics-diagnosis extraction) plus a small end-to-end smoke test of the
probe/representation pipeline on a tiny slice of real ring-8 v2 data with
tiny untrained models (not the real checkpoints) -- no reliance on the
trained r9/r10 checkpoints, so this stays fast and independent of any
particular training run's outcome."""

import json
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import torch  # noqa: E402

import d1v2_interrogate as di2  # noqa: E402
from fourcolor.d1v2_model import D1v2DynamicsModel, D1v2VerdictOnlyModel  # noqa: E402

TRACES_R8 = ROOT / "data" / "v2" / "traces_r8.jsonl"


class TestVerifySplitAgainstMetrics(unittest.TestCase):
    def _records(self):
        return [{"boundary": True}, {"boundary": False}, {"boundary": True}, {"boundary": False}]

    def test_matching_split_passes(self):
        records = self._records()
        train_idx, val_idx = [0, 1], [2, 3]
        expected = {"train_size": 2, "val_size": 2, "val_boundary_size": 1, "train_boundary_size": 1}
        di2.verify_split_against_metrics(records, train_idx, val_idx, expected)  # no raise

    def test_mismatched_val_size_raises(self):
        records = self._records()
        train_idx, val_idx = [0, 1, 2], [3]
        expected = {"train_size": 2, "val_size": 2, "val_boundary_size": 1, "train_boundary_size": 1}
        with self.assertRaises(AssertionError):
            di2.verify_split_against_metrics(records, train_idx, val_idx, expected)

    def test_mismatched_boundary_count_raises(self):
        records = self._records()
        train_idx, val_idx = [0, 1], [2, 3]
        expected = {"train_size": 2, "val_size": 2, "val_boundary_size": 0, "train_boundary_size": 1}
        with self.assertRaises(AssertionError):
            di2.verify_split_against_metrics(records, train_idx, val_idx, expected)


class TestSliceBoundary(unittest.TestCase):
    def test_slices_correct_positions(self):
        values = np.array([1.0, 0.0, 1.0, 1.0])
        test_idx = [5, 6, 7, 8]  # values[j] corresponds to test_idx[j]
        boundary_by_idx = {5: False, 6: True, 7: False, 8: True}
        boundary_flags_list = [boundary_by_idx.get(i, False) for i in range(9)]
        out = di2.slice_boundary(values, test_idx, boundary_flags_list)
        self.assertEqual(out.tolist(), [0.0, 1.0])  # positions 1,3 -> test_idx 6,8

    def test_empty_when_no_boundary_in_test_idx(self):
        values = np.array([1.0, 1.0])
        test_idx = [0, 1]
        boundary_flags = [False, False]
        out = di2.slice_boundary(values, test_idx, boundary_flags)
        self.assertEqual(len(out), 0)


class TestCiNonOverlapAndHigher(unittest.TestCase):
    def test_non_overlapping_higher_is_true(self):
        challenger = (0.9, 0.85, 0.95)
        baseline = (0.5, 0.4, 0.6)
        self.assertTrue(di2.ci_non_overlap_and_higher(challenger, baseline))

    def test_overlapping_is_false(self):
        challenger = (0.6, 0.5, 0.7)
        baseline = (0.55, 0.45, 0.65)
        self.assertFalse(di2.ci_non_overlap_and_higher(challenger, baseline))

    def test_non_overlapping_but_lower_is_false(self):
        challenger = (0.3, 0.2, 0.35)
        baseline = (0.7, 0.6, 0.8)
        self.assertFalse(di2.ci_non_overlap_and_higher(challenger, baseline))


class TestExtractDynamicsDiagnosis(unittest.TestCase):
    def _fake_metrics(self):
        def epoch(e, tf_f1, fr_f1, tf_v, fr_v, fr_v_b):
            return {
                "epoch": e,
                "teacher_forced_per_round_f1": [{"round": t, "f1": f} for t, f in enumerate(tf_f1)],
                "free_running_per_round_f1": [{"round": t, "f1": f} for t, f in enumerate(fr_f1)],
                "verdict_accuracy_teacher_forced": tf_v,
                "verdict_accuracy_free_running": fr_v,
                "verdict_accuracy_free_running_boundary": fr_v_b,
                "n_val_boundary": 5,
            }

        return {
            "best_epoch": 1,
            "epochs": [
                epoch(1, [0.95, 0.5], [0.95, 0.5], 1.0, 0.8, 1.0),
                epoch(2, [0.96, 0.6], [0.96, 0.1], 1.0, 0.3, 0.0),
            ],
        }

    def test_pulls_best_and_last_epoch_correctly(self):
        d = di2.extract_dynamics_diagnosis(self._fake_metrics())
        self.assertEqual(d["best_epoch"], 1)
        self.assertEqual(d["last_epoch"], 2)
        self.assertEqual(d["best_tf_round_f1"], [0.95, 0.5])
        self.assertEqual(d["last_tf_round_f1"], [0.96, 0.6])
        self.assertEqual(d["best_fr_round_f1"], [0.95, 0.5])
        self.assertEqual(d["last_fr_round_f1"], [0.96, 0.1])
        self.assertEqual(d["best_verdict_acc_fr_boundary"], 1.0)
        self.assertEqual(d["last_verdict_acc_fr_boundary"], 0.0)
        self.assertEqual(d["n_epochs_trained"], 2)


class TestPointEstimateBeatsShallowOnBoundary(unittest.TestCase):
    def _probe_result(self, name, boundary_acc):
        return {"name": name, "boundary_acc": boundary_acc, "boundary_ci_lo": None, "boundary_ci_hi": None}

    def test_tie_does_not_count_as_a_win(self):
        ring_results = {
            9: {"probe_results": {
                "shallow": self._probe_result("shallow", 0.5),
                **{n: self._probe_result(n, 0.5) for n in di2.REPRESENTATION_ORDER if n != "shallow"},
            }}
        }
        wins = di2.point_estimate_beats_shallow_on_boundary(ring_results)
        self.assertTrue(all(v == [] for v in wins.values()))

    def test_strictly_higher_counts_as_a_win_for_that_ring_only(self):
        ring_results = {
            9: {"probe_results": {
                "shallow": self._probe_result("shallow", 0.5),
                **{n: self._probe_result(n, 0.9 if n == "dynamics_h1" else 0.5) for n in di2.REPRESENTATION_ORDER if n != "shallow"},
            }},
            10: {"probe_results": {
                "shallow": self._probe_result("shallow", 0.5),
                **{n: self._probe_result(n, 0.5) for n in di2.REPRESENTATION_ORDER if n != "shallow"},
            }},
        }
        wins = di2.point_estimate_beats_shallow_on_boundary(ring_results)
        self.assertEqual(wins["dynamics_h1"], [9])
        self.assertEqual(wins["dynamics_h0"], [])


class TestAnyRepresentationBeatsShallowOnBoundary(unittest.TestCase):
    def _probe_result(self, name, boundary_acc, lo, hi):
        return {"name": name, "boundary_acc": boundary_acc, "boundary_ci_lo": lo, "boundary_ci_hi": hi}

    def _ring_results(self, extra_boundary):
        probe_results = {"shallow": self._probe_result("shallow", 0.5, 0.3, 0.7)}
        for name in di2.REPRESENTATION_ORDER:
            if name == "shallow":
                continue
            probe_results[name] = self._probe_result(name, 0.5, 0.3, 0.7)
        probe_results.update(extra_boundary)
        return {9: {"probe_results": probe_results}}

    def test_no_hits_when_all_overlap(self):
        hits = di2.any_representation_beats_shallow_on_boundary(self._ring_results({}))
        self.assertEqual(hits, [])

    def test_hit_when_one_representation_clears_the_bar(self):
        extra = {"dynamics_h1": self._probe_result("dynamics_h1", 0.95, 0.85, 1.0)}
        hits = di2.any_representation_beats_shallow_on_boundary(self._ring_results(extra))
        self.assertEqual(hits, [{"ring": 9, "representation": "dynamics_h1"}])

    def test_none_boundary_acc_is_skipped_not_crashed(self):
        extra = {"dynamics_h1": self._probe_result("dynamics_h1", None, None, None)}
        hits = di2.any_representation_beats_shallow_on_boundary(self._ring_results(extra))
        self.assertEqual(hits, [])


R8_DYNAMICS_METRICS = ROOT / "results" / "d1v2" / "r8" / "dynamics_metrics.json"


@unittest.skipUnless(R8_DYNAMICS_METRICS.exists(), "results/d1v2/r8 not present")
class TestLoadRingSplitAdjacencyCoercion(unittest.TestCase):
    """Regression test: tools/d1v2_train.load_records computes an int-keyed
    adjacency dict LOCALLY (only to feed encode_config) but never writes it
    back onto the record -- rec["adjacency"] as returned is still raw-JSON
    string-keyed. load_ring_split must fix this up (shallow/structural
    feature extraction needs int keys), verified here against ring 8's
    already-trained split (fast: no model loading, just data + split)."""

    def test_val_records_have_int_keyed_adjacency(self):
        split = di2.load_ring_split(8, ROOT / "data" / "v2", ROOT / "results" / "d1v2")
        val_records = [split["records"][i] for i in split["val_idx"]]
        self.assertGreater(len(val_records), 0)
        for rec in val_records:
            for key in rec["adjacency"]:
                self.assertIsInstance(key, int)

    def test_shallow_features_do_not_raise_on_loaded_records(self):
        from fourcolor import d1_interp as di

        split = di2.load_ring_split(8, ROOT / "data" / "v2", ROOT / "results" / "d1v2")
        val_records = [split["records"][i] for i in split["val_idx"]]
        for rec in val_records:
            vec = di.shallow_feature_vector(rec["adjacency"], rec["r"], rec["n"])
            self.assertEqual(len(vec), len(di.SHALLOW_FEATURE_NAMES))


class TestShallowPlusStructuralVector(unittest.TestCase):
    def test_length_is_shallow_plus_structural_minus_tautological(self):
        from fourcolor import d1_interp as di

        adj = {1: [2, 3], 2: [3, 1], 3: [1, 2]}
        rec = {"adjacency": adj, "r": 3, "n": 3, "n_extendable": 2, "n_consistent": 0}
        vec = di2.shallow_plus_structural_vector(rec)
        expected_len = len(di.SHALLOW_FEATURE_NAMES) + len(di2.STRUCTURAL_CANDIDATE_NAMES)
        self.assertEqual(len(vec), expected_len)
        self.assertNotIn("n_consistent", di2.STRUCTURAL_CANDIDATE_NAMES)


# ---------------------------------------------------------------------------
# Small end-to-end smoke test: real ring-8 v2 records, tiny untrained
# models, full representation-extraction + probe pipeline. Not the real
# r9/r10 checkpoints -- just confirms the wiring (shapes, batching,
# run_probe) is correct end to end.
# ---------------------------------------------------------------------------


def load_smoke_records(n=40):
    records = []
    with TRACES_R8.open() as f:
        for line in f:
            rec = json.loads(line)
            adjacency = {int(v): nbrs for v, nbrs in rec["adjacency"].items()}
            from fourcolor.d1_encoding import encode_config

            rec["adjacency"] = adjacency
            rec["src_ids"] = encode_config(adjacency, rec["r"], rec["n"])
            records.append(rec)
            if len(records) >= n:
                break
    return records


def tiny_dynamics_model(n_codes, max_len=300):
    return D1v2DynamicsModel(
        n_codes=n_codes, d_model=16, nhead=2, dim_feedforward=32, max_len=max_len, num_encoder_layers=1
    )


def tiny_control_model(max_len=300):
    return D1v2VerdictOnlyModel(d_model=16, nhead=2, dim_feedforward=32, max_len=max_len, num_encoder_layers=1)


@unittest.skipUnless(TRACES_R8.exists(), "data/v2/traces_r8.jsonl not present")
class TestRepresentationPipelineSmoke(unittest.TestCase):
    def setUp(self):
        self.records = load_smoke_records(40)
        # need at least a couple of rounds >= 2 for dynamics_h2 to be real
        self.assertTrue(any(r["rounds"] >= 2 for r in self.records))
        n_codes_index = json.loads((ROOT / "data" / "v2" / "code_index_r8.json").read_text())
        self.n_codes = n_codes_index["n_codes"]
        self.device = torch.device("cpu")

    def test_control_encoder_summary_shape(self):
        model = tiny_control_model()
        summary = di2.control_encoder_summary(model, self.records, self.device)
        self.assertEqual(summary.shape, (len(self.records), 16))

    def test_dynamics_representations_shapes(self):
        model = tiny_dynamics_model(self.n_codes)
        reps = di2.dynamics_representations(model, self.records, self.n_codes, self.device)
        self.assertEqual(set(reps.keys()), {
            "dynamics_encoder_summary", "dynamics_round0_logits", "dynamics_h0", "dynamics_h1", "dynamics_h2",
        })
        self.assertEqual(reps["dynamics_encoder_summary"].shape, (len(self.records), 16))
        self.assertEqual(reps["dynamics_round0_logits"].shape, (len(self.records), self.n_codes))
        for key in ("dynamics_h0", "dynamics_h1", "dynamics_h2"):
            self.assertEqual(reps[key].shape, (len(self.records), 16))

    def test_control_head_correctness_is_binary_array(self):
        model = tiny_control_model()
        correct = di2.control_head_correctness(model, self.records, self.device)
        self.assertEqual(correct.shape, (len(self.records),))
        self.assertTrue(set(np.unique(correct)).issubset({0.0, 1.0}))

    def test_dynamics_free_running_correctness_is_binary_array(self):
        model = tiny_dynamics_model(self.n_codes)
        correct = di2.dynamics_free_running_correctness(model, self.records, self.n_codes, self.device)
        self.assertEqual(correct.shape, (len(self.records),))
        self.assertTrue(set(np.unique(correct)).issubset({0.0, 1.0}))

    def test_run_probe_end_to_end_on_shallow_features(self):
        from fourcolor import d1_interp as di

        labels = [r["d_reducible"] for r in self.records]
        boundary_flags = [bool(r["boundary"]) for r in self.records]
        X = torch.tensor(
            [di.shallow_feature_vector(r["adjacency"], r["r"], r["n"]) for r in self.records], dtype=torch.float32
        )
        train_idx, test_idx = di.stratified_split(labels, test_frac=0.25, seed=0)
        result = di2.run_probe("shallow", X, labels, boundary_flags, train_idx, test_idx, seed=0, n_boot=100, epochs=30)
        self.assertIn("overall_acc", result)
        self.assertGreaterEqual(result["overall_acc"], 0.0)
        self.assertLessEqual(result["overall_acc"], 1.0)
        self.assertEqual(result["n_test"], len(test_idx))
        # boundary_acc may be None if no boundary example lands in test_idx
        if result["n_test_boundary"] > 0:
            self.assertIsNotNone(result["boundary_acc"])


if __name__ == "__main__":
    unittest.main()
