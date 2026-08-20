"""Encoder-decoder transformer for D1: canonical config encoding ->
process-supervised D-reducibility closure trace + verdict.

Architecture and code structure adapted, with attribution, from the
zeta-map interpretability template:
    /Users/yugendren/experiments/zeta_map_interp/src/zetamap/model.py
(Huang-Jackson-Lee, arXiv:2511.12421 architecture: encoder-decoder
transformer, post-norm residual blocks, learned positional embeddings,
GELU FFN, weight-tied output projection). Copied and adapted rather than
imported across repos (no cross-repo dependency); NOT a verbatim copy --
generalized to configurable depth (1-4 layers per side) and wider
d_model (128-256) per the D1 task spec, and retargeted at the D1
vocabulary (src/fourcolor/d1_encoding.py) instead of the Dyck-word/zeta
vocabulary.

All hyperparameter defaults are the D1 spec's midpoint (2 layers,
d_model=192); exact values used for any given run are recorded in
results/d1/*.json by tools/d1_train.py.
"""

from __future__ import annotations

import torch
from torch import nn

from .d1_encoding import BOS_ID, EOS_ID, PAD_ID, VOCAB_SIZE


class D1Transformer(nn.Module):
    """Tiny encoder-decoder transformer: config tokens -> closure-trace +
    verdict tokens.

    `num_encoder_layers` / `num_decoder_layers` independently configurable
    1-4 (spec range); `d_model` intended 128-256 (spec range). Dropout
    defaults to 0.0 for the same reason as the zeta-map template: this is
    a deterministic-target sequence task graded by exact match /
    verdict accuracy, not held-out perplexity on a noisy distribution, and
    dropout measurably hurts convergence at this scale in that precedent
    (see zeta_map_interp/src/zetamap/model.py docstring).
    """

    def __init__(
        self,
        d_model: int = 192,
        nhead: int = 4,
        dim_feedforward: int = 384,
        max_len: int = 512,
        vocab_size: int = VOCAB_SIZE,
        pad_id: int = PAD_ID,
        num_encoder_layers: int = 2,
        num_decoder_layers: int = 2,
        dropout: float = 0.0,
    ):
        super().__init__()
        self.d_model = d_model
        self.max_len = max_len
        self.pad_id = pad_id
        self.vocab_size = vocab_size

        self.token_embedding = nn.Embedding(vocab_size, d_model, padding_idx=pad_id)
        self.pos_embedding = nn.Embedding(max_len, d_model)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
            norm_first=False,  # post-norm, per the zeta-map template
        )
        # enable_nested_tensor=False: the nested-tensor fast path (taken
        # automatically in eval() with a non-trivial padding mask) hits an
        # unimplemented op on MPS (aten::_nested_tensor_from_mask_left_
        # aligned); disabling it keeps eval-mode encode() working uniformly
        # on CPU/MPS/CUDA at a small, acceptable speed cost for these tiny
        # sequences.
        self.encoder = nn.TransformerEncoder(
            encoder_layer, num_layers=num_encoder_layers, enable_nested_tensor=False
        )

        decoder_layer = nn.TransformerDecoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
            norm_first=False,
        )
        self.decoder = nn.TransformerDecoder(decoder_layer, num_layers=num_decoder_layers)

        # Output logits weight-tied to the token embedding, as in the
        # zeta-map template; only a per-token bias is a free parameter.
        self.output_bias = nn.Parameter(torch.zeros(vocab_size))

    def _embed(self, ids: torch.Tensor) -> torch.Tensor:
        seq_len = ids.size(1)
        positions = torch.arange(seq_len, device=ids.device).unsqueeze(0)
        return self.token_embedding(ids) + self.pos_embedding(positions)

    def encode(self, src_ids: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        src_key_padding_mask = src_ids == self.pad_id
        memory = self.encoder(self._embed(src_ids), src_key_padding_mask=src_key_padding_mask)
        return memory, src_key_padding_mask

    def decode_step(
        self,
        tgt_ids: torch.Tensor,
        memory: torch.Tensor,
        memory_key_padding_mask: torch.Tensor,
    ) -> torch.Tensor:
        seq_len = tgt_ids.size(1)
        causal_mask = torch.triu(
            torch.ones(seq_len, seq_len, dtype=torch.bool, device=tgt_ids.device), diagonal=1
        )
        tgt_key_padding_mask = tgt_ids == self.pad_id
        hidden = self.decoder(
            self._embed(tgt_ids),
            memory,
            tgt_mask=causal_mask,
            tgt_key_padding_mask=tgt_key_padding_mask,
            memory_key_padding_mask=memory_key_padding_mask,
        )
        logits = hidden @ self.token_embedding.weight.T + self.output_bias
        return logits

    def forward(self, src_ids: torch.Tensor, tgt_in_ids: torch.Tensor) -> torch.Tensor:
        """Teacher-forced forward pass. Returns logits (B, T, V)."""
        memory, src_key_padding_mask = self.encode(src_ids)
        return self.decode_step(tgt_in_ids, memory, src_key_padding_mask)

    @torch.no_grad()
    def greedy_decode(self, src_ids: torch.Tensor, max_len: int | None = None) -> torch.Tensor:
        """Autoregressive greedy decoding. src_ids: (B, S). Returns (B, T)
        generated token ids (including the leading BOS), PAD-padded after
        each row's first EOS."""
        self.eval()
        max_len = max_len or self.max_len
        device = src_ids.device
        batch_size = src_ids.size(0)
        memory, src_key_padding_mask = self.encode(src_ids)

        generated = torch.full((batch_size, 1), BOS_ID, dtype=torch.long, device=device)
        finished = torch.zeros(batch_size, dtype=torch.bool, device=device)
        for _ in range(max_len - 1):
            logits = self.decode_step(generated, memory, src_key_padding_mask)
            next_ids = logits[:, -1, :].argmax(dim=-1)
            next_ids = torch.where(finished, torch.full_like(next_ids, PAD_ID), next_ids)
            generated = torch.cat([generated, next_ids.unsqueeze(1)], dim=1)
            finished = finished | (next_ids == EOS_ID)
            if bool(finished.all()):
                break
        return generated


def count_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


if __name__ == "__main__":
    m = D1Transformer()
    print(f"D1Transformer parameter count: {count_parameters(m):,}")
