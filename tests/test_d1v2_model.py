"""Forward-shape smoke tests for D1v2DynamicsModel / D1v2VerdictOnlyModel.
Kept tiny (small d_model, 1 encoder layer, tiny n_codes) so this runs in
well under a second on CPU as part of `make test` -- mirrors
tests/test_d1_model.py's style/scope for the v1 model."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import torch  # noqa: E402

from fourcolor.d1_encoding import VOCAB_SIZE  # noqa: E402
from fourcolor.d1v2_model import (  # noqa: E402
    D1v2DynamicsModel,
    D1v2VerdictOnlyModel,
    count_parameters,
)

N_CODES = 17  # tiny fake ring-code vocabulary, unrelated to any real ring size


def tiny_dynamics_model(max_len=64, n_codes=N_CODES):
    return D1v2DynamicsModel(
        n_codes=n_codes, d_model=16, nhead=2, dim_feedforward=32,
        max_len=max_len, num_encoder_layers=1,
    )


def tiny_control_model(max_len=64):
    return D1v2VerdictOnlyModel(
        d_model=16, nhead=2, dim_feedforward=32, max_len=max_len, num_encoder_layers=1,
    )


def random_src(batch, seq_len, vocab=VOCAB_SIZE):
    return torch.randint(0, vocab, (batch, seq_len))


class TestD1v2DynamicsModel(unittest.TestCase):
    def test_teacher_force_shapes(self):
        model = tiny_dynamics_model()
        B, S, T = 3, 12, 5
        src = random_src(B, S)
        true_bitmaps = (torch.rand(B, T, N_CODES) > 0.7).float()
        logits, hiddens = model(src, true_bitmaps=true_bitmaps, mode="teacher_force")
        self.assertEqual(logits.shape, (B, T, N_CODES))
        self.assertEqual(hiddens.shape, (B, T, 16))

    def test_free_run_shapes(self):
        model = tiny_dynamics_model()
        B, S, n_rounds = 2, 10, 4
        src = random_src(B, S)
        logits, hiddens = model(src, n_rounds=n_rounds, mode="free_run")
        self.assertEqual(logits.shape, (B, n_rounds + 1, N_CODES))
        self.assertEqual(hiddens.shape, (B, n_rounds + 1, 16))

    def test_free_run_round0_matches_teacher_force_round0(self):
        # Round 0 depends only on the encoder summary in both modes (no
        # dynamics step has run yet), so with the same src and eval() mode
        # (dropout off) the two should agree exactly.
        model = tiny_dynamics_model()
        model.eval()
        B, S = 2, 8
        src = random_src(B, S)
        true_bitmaps = torch.zeros(B, 3, N_CODES)
        with torch.no_grad():
            tf_logits, _ = model(src, true_bitmaps=true_bitmaps, mode="teacher_force")
            fr_logits, _ = model(src, n_rounds=2, mode="free_run")
        self.assertTrue(torch.allclose(tf_logits[:, 0, :], fr_logits[:, 0, :], atol=1e-6))

    def test_teacher_force_requires_true_bitmaps(self):
        model = tiny_dynamics_model()
        src = random_src(2, 8)
        with self.assertRaises(ValueError):
            model(src, mode="teacher_force")

    def test_free_run_requires_n_rounds(self):
        model = tiny_dynamics_model()
        src = random_src(2, 8)
        with self.assertRaises(ValueError):
            model(src, mode="free_run")

    def test_unknown_mode_raises(self):
        model = tiny_dynamics_model()
        src = random_src(2, 8)
        with self.assertRaises(ValueError):
            model(src, n_rounds=2, mode="bogus")

    def test_verdict_logits_gathers_own_round(self):
        model = tiny_dynamics_model()
        B, S, T = 4, 8, 6
        src = random_src(B, S)
        true_bitmaps = (torch.rand(B, T, N_CODES) > 0.5).float()
        _, hiddens = model(src, true_bitmaps=true_bitmaps, mode="teacher_force")
        round_idx = torch.tensor([0, 2, 5, 1])
        vlogits = model.verdict_logits(hiddens, round_idx)
        self.assertEqual(vlogits.shape, (B,))
        # Manually recompute for one example to confirm the right round's
        # hidden state was gathered (not e.g. always the last one).
        expected = model.verdict_head(hiddens[2, 5]).squeeze(-1)
        self.assertTrue(torch.allclose(vlogits[2], expected))

    def test_param_count_positive_and_scales_with_depth(self):
        small = count_parameters(tiny_dynamics_model())
        bigger = count_parameters(
            D1v2DynamicsModel(
                n_codes=N_CODES, d_model=16, nhead=2, dim_feedforward=32,
                max_len=64, num_encoder_layers=3,
            )
        )
        self.assertGreater(small, 0)
        self.assertGreater(bigger, small)


class TestD1v2VerdictOnlyModel(unittest.TestCase):
    def test_forward_shape(self):
        model = tiny_control_model()
        src = random_src(3, 10)
        out = model(src)
        self.assertEqual(out.shape, (3,))

    def test_no_dynamics_parameters(self):
        model = tiny_control_model()
        names = [n for n, _ in model.named_parameters()]
        self.assertTrue(all("dynamics" not in n for n in names))


if __name__ == "__main__":
    unittest.main()
