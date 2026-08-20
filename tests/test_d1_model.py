"""Forward-shape and greedy-decode smoke tests for D1Transformer. Kept
tiny (small d_model, 1 layer, short sequences) so this runs in well under
a second on CPU as part of `make test`."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import torch  # noqa: E402

from fourcolor.d1_encoding import PAD_ID, VOCAB_SIZE, encode_config, encode_trace  # noqa: E402
from fourcolor.d1_model import D1Transformer, count_parameters  # noqa: E402

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


def tiny_model(max_len=128):
    return D1Transformer(
        d_model=16,
        nhead=2,
        dim_feedforward=32,
        max_len=max_len,
        num_encoder_layers=1,
        num_decoder_layers=1,
    )


class TestD1Model(unittest.TestCase):
    def test_forward_shapes(self):
        model = tiny_model()
        src_ids = torch.tensor(encode_config(SAMPLE_ADJ, 6, 8)).unsqueeze(0)
        tgt_ids = torch.tensor(encode_trace([106, 10, 8, 4, 1, 0], True)).unsqueeze(0)
        logits = model(src_ids, tgt_ids[:, :-1])
        self.assertEqual(logits.shape, (1, tgt_ids.size(1) - 1, VOCAB_SIZE))

    def test_forward_batched_with_padding(self):
        model = tiny_model()
        a = encode_config(SAMPLE_ADJ, 6, 8)
        b = a + a[:6]  # a longer, different-length second example
        src = torch.nn.utils.rnn.pad_sequence(
            [torch.tensor(a), torch.tensor(b)], batch_first=True, padding_value=PAD_ID
        )
        tgt = torch.tensor(encode_trace([10, 4, 1, 0], True)).unsqueeze(0).repeat(2, 1)
        logits = model(src, tgt[:, :-1])
        self.assertEqual(logits.shape, (2, tgt.size(1) - 1, VOCAB_SIZE))

    def test_greedy_decode_shape_and_bounds(self):
        model = tiny_model(max_len=128)
        src_ids = torch.tensor(encode_config(SAMPLE_ADJ, 6, 8)).unsqueeze(0)
        gen = model.greedy_decode(src_ids, max_len=20)
        self.assertEqual(gen.dim(), 2)
        self.assertEqual(gen.size(0), 1)
        self.assertLessEqual(gen.size(1), 20)
        self.assertTrue(bool((gen >= 0).all()))
        self.assertTrue(bool((gen < VOCAB_SIZE).all()))

    def test_param_count_positive_and_scales_with_depth(self):
        small = count_parameters(tiny_model())
        bigger = count_parameters(
            D1Transformer(
                d_model=16, nhead=2, dim_feedforward=32, max_len=64,
                num_encoder_layers=3, num_decoder_layers=3,
            )
        )
        self.assertGreater(small, 0)
        self.assertGreater(bigger, small)


if __name__ == "__main__":
    unittest.main()
