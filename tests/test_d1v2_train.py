"""Fast unit tests for tools/d1v2_train.py's pure data/loss/metric
helpers: batch-bitmap construction + round-masking, masked BCE loss
(confirms padded rounds don't influence the loss), micro-F1 bookkeeping,
and the boundary-stratified train/val split. No model, no real data --
tiny synthetic fixtures only, runs in well under a second."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import torch  # noqa: E402

import d1v2_train  # noqa: E402

N_CODES = 6


def make_record(rounds, set_trace, d_reducible, boundary=False):
    assert len(set_trace) == rounds + 1
    return {"rounds": rounds, "set_trace": set_trace, "d_reducible": d_reducible, "boundary": boundary}


class TestBuildBatchBitmaps(unittest.TestCase):
    def test_shapes_and_round_mask(self):
        records = [
            make_record(1, [[0, 1], [1]], True),
            make_record(3, [[0, 1, 2], [1, 2], [2], []], True),
        ]
        true_bitmaps, round_mask, round_idx, verdict = d1v2_train.build_batch_bitmaps(records, N_CODES)
        T = 4  # max(rounds)+1 = 3+1
        self.assertEqual(true_bitmaps.shape, (2, T, N_CODES))
        self.assertEqual(round_mask.shape, (2, T))
        self.assertEqual(round_idx.tolist(), [1, 3])
        self.assertEqual(verdict.tolist(), [1.0, 1.0])
        # example 0 only has rounds 0,1 valid; rounds 2,3 are padding
        self.assertEqual(round_mask[0].tolist(), [True, True, False, False])
        self.assertEqual(round_mask[1].tolist(), [True, True, True, True])

    def test_bitmap_values_match_set_trace(self):
        records = [make_record(2, [[0], [0, 2], []], False)]
        true_bitmaps, round_mask, round_idx, verdict = d1v2_train.build_batch_bitmaps(records, N_CODES)
        self.assertEqual(true_bitmaps[0, 0].tolist(), [1, 0, 0, 0, 0, 0])
        self.assertEqual(true_bitmaps[0, 1].tolist(), [1, 0, 1, 0, 0, 0])
        self.assertEqual(true_bitmaps[0, 2].tolist(), [0, 0, 0, 0, 0, 0])  # empty round: all zero
        self.assertEqual(round_idx.tolist(), [2])
        self.assertEqual(verdict.tolist(), [0.0])

    def test_padded_rounds_are_zero_filled(self):
        records = [
            make_record(0, [[0, 1, 2]], True),
            make_record(2, [[0], [1], [2]], False),
        ]
        true_bitmaps, round_mask, _, _ = d1v2_train.build_batch_bitmaps(records, N_CODES)
        # example 0's rounds 1,2 are padding -> zero bitmap, mask False
        self.assertFalse(bool(round_mask[0, 1]))
        self.assertFalse(bool(round_mask[0, 2]))
        self.assertEqual(true_bitmaps[0, 1].sum().item(), 0)
        self.assertEqual(true_bitmaps[0, 2].sum().item(), 0)


class TestMaskedStateBCE(unittest.TestCase):
    def test_padded_region_does_not_affect_loss(self):
        torch.manual_seed(0)
        B, T = 2, 3
        logits = torch.randn(B, T, N_CODES, requires_grad=True)
        true_bitmaps = (torch.rand(B, T, N_CODES) > 0.5).float()
        round_mask = torch.tensor([[True, True, False], [True, True, True]])

        loss_a = d1v2_train.masked_state_bce(logits, true_bitmaps, round_mask)

        # Mutate the masked-out slot (example 0, round 2) arbitrarily --
        # loss must be identical since that slot is excluded from the mean.
        logits_b = logits.detach().clone()
        logits_b[0, 2, :] = 999.0
        loss_b = d1v2_train.masked_state_bce(logits_b, true_bitmaps, round_mask)
        self.assertAlmostEqual(loss_a.item(), loss_b.item(), places=5)

    def test_unmasked_region_does_affect_loss(self):
        B, T = 1, 2
        round_mask = torch.tensor([[True, True]])
        true_bitmaps = torch.zeros(B, T, N_CODES)

        logits_good = torch.full((B, T, N_CODES), -10.0)  # confident correct (predicts 0)
        logits_bad = torch.full((B, T, N_CODES), 10.0)  # confident wrong

        loss_good = d1v2_train.masked_state_bce(logits_good, true_bitmaps, round_mask)
        loss_bad = d1v2_train.masked_state_bce(logits_bad, true_bitmaps, round_mask)
        self.assertLess(loss_good.item(), loss_bad.item())

    def test_gradient_does_not_flow_into_padded_slot(self):
        B, T = 1, 2
        logits = torch.zeros(B, T, N_CODES, requires_grad=True)
        true_bitmaps = torch.zeros(B, T, N_CODES)
        round_mask = torch.tensor([[True, False]])
        loss = d1v2_train.masked_state_bce(logits, true_bitmaps, round_mask)
        loss.backward()
        self.assertTrue(torch.all(logits.grad[0, 1] == 0))
        self.assertTrue(torch.any(logits.grad[0, 0] != 0))


class TestMicroF1(unittest.TestCase):
    def test_confusion_counts_and_f1(self):
        pred = torch.tensor([[[True, False, True]]])  # (1,1,3)
        true = torch.tensor([[[True, True, False]]])
        mask = torch.tensor([[True]])
        tp, fp, fn = d1v2_train.micro_confusion(pred, true, mask)
        self.assertEqual((tp, fp, fn), (1, 1, 1))
        stats = d1v2_train.f1_from_confusion(tp, fp, fn)
        self.assertAlmostEqual(stats["precision"], 0.5)
        self.assertAlmostEqual(stats["recall"], 0.5)
        self.assertAlmostEqual(stats["f1"], 0.5)

    def test_mask_excludes_examples_from_confusion(self):
        pred = torch.tensor([[[True, False]], [[False, False]]])
        true = torch.tensor([[[False, False]], [[True, True]]])
        mask_all = torch.tensor([[True], [True]])
        mask_first_only = torch.tensor([[True], [False]])
        tp_all, fp_all, fn_all = d1v2_train.micro_confusion(pred, true, mask_all)
        tp_f, fp_f, fn_f = d1v2_train.micro_confusion(pred, true, mask_first_only)
        self.assertEqual((tp_f, fp_f, fn_f), (0, 1, 0))  # only example 0 counted
        self.assertNotEqual((tp_all, fp_all, fn_all), (tp_f, fp_f, fn_f))

    def test_perfect_prediction_gives_f1_one(self):
        stats = d1v2_train.f1_from_confusion(tp=5, fp=0, fn=0)
        self.assertEqual(stats["f1"], 1.0)

    def test_no_positives_gives_f1_zero(self):
        stats = d1v2_train.f1_from_confusion(tp=0, fp=0, fn=0)
        self.assertEqual(stats["f1"], 0.0)


class TestPerRoundF1(unittest.TestCase):
    def test_support_matches_round_mask_and_f1_correct(self):
        # round 0: both examples valid, perfect prediction -> f1=1
        # round 1: only example 0 valid, prediction wrong -> f1=0
        # Confident-negative baseline everywhere (sigmoid(0)=0.5 would
        # itself threshold to "present", so explicit negative logits are
        # needed for the "should be absent" codes to read as absent).
        logits = torch.full((2, 2, N_CODES), -10.0)
        logits[:, 0, 0] = 10.0  # both predict code 0 present at round 0
        logits[0, 1, 1] = 10.0  # example 0 predicts code 1 present at round 1 (wrong)
        true_bitmaps = torch.zeros(2, 2, N_CODES)
        true_bitmaps[:, 0, 0] = 1.0  # true: code 0 present at round 0 for both
        true_bitmaps[0, 1, 2] = 1.0  # example 0's true round-1 positive is code 2, not 1
        round_mask = torch.tensor([[True, True], [True, False]])

        result = d1v2_train.per_round_f1(logits, true_bitmaps, round_mask)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["support"], 2)
        self.assertEqual(result[0]["f1"], 1.0)
        self.assertEqual(result[1]["support"], 1)
        self.assertEqual(result[1]["f1"], 0.0)


class TestStratifiedSplit(unittest.TestCase):
    def _fake_records(self, n_boundary=10, n_other=90):
        records = [{"boundary": True} for _ in range(n_boundary)]
        records += [{"boundary": False} for _ in range(n_other)]
        return records

    def test_split_covers_all_indices_without_overlap(self):
        records = self._fake_records()
        train_idx, val_idx = d1v2_train.stratified_split(records, 0.15, seed=0, stratify=True)
        self.assertEqual(set(train_idx) | set(val_idx), set(range(len(records))))
        self.assertEqual(set(train_idx) & set(val_idx), set())

    def test_boundary_examples_present_in_val(self):
        records = self._fake_records(n_boundary=10, n_other=90)
        train_idx, val_idx = d1v2_train.stratified_split(records, 0.15, seed=0, stratify=True)
        n_val_boundary = sum(1 for i in val_idx if records[i]["boundary"])
        n_train_boundary = sum(1 for i in train_idx if records[i]["boundary"])
        self.assertGreater(n_val_boundary, 0)
        self.assertGreater(n_train_boundary, 0)

    def test_deterministic_given_seed(self):
        records = self._fake_records()
        a = d1v2_train.stratified_split(records, 0.15, seed=0, stratify=True)
        b = d1v2_train.stratified_split(records, 0.15, seed=0, stratify=True)
        self.assertEqual(a, b)

    def test_unstratified_split_also_covers_all_indices(self):
        records = self._fake_records()
        train_idx, val_idx = d1v2_train.stratified_split(records, 0.15, seed=0, stratify=False)
        self.assertEqual(set(train_idx) | set(val_idx), set(range(len(records))))
        self.assertEqual(set(train_idx) & set(val_idx), set())


if __name__ == "__main__":
    unittest.main()
