"""D1-v2 ring specialist: encoder (same token encoding as v1, see
`d1_encoding.py`) + an ITERATED-MAP dynamics head over the per-ring
survivor-set bitmap, instead of a token-sequence decoder.

Why an iterated map, not a seq2seq decoder (interrogatability is the
design driver here, per the D1-v2 task spec):

  The actual computation this model approximates (fourcolor.reduce.check,
  see that module's docstring) is a fixed-point iteration: round 0 is the
  extendable-code-filtered live set; round t+1 = a deterministic function
  of round t's live set (Kempe-closure marking) applied to the WHOLE ring;
  iterate until the set stops shrinking. A seq2seq decoder autoregressing
  over an arbitrary token vocabulary (v1's approach) has no structural
  correspondence to that process -- "round t" is just token position t,
  and the model is free to use its capacity however it likes.

  Here instead:
    state_t  in [0,1]^n_codes  -- a probability per canonical ring-coloring
                                   code, "does this code survive to round t"
    h_t      in R^d_model      -- the model's internal round-t summary,
                                   the natural probe target for
                                   "what does the model believe the live
                                   set looks like at round t"
    f(state_t, encoder_summary) -> state_{t+1}
                                -- ONE shared block, reused every round
                                   (weight-tied across rounds by
                                   construction, not by training trick),
                                   exactly mirroring "apply the same
                                   round-update rule repeatedly."

  Concretely `f` is a GRUCell: the encoder summary seeds the initial
  hidden h_{-1} (there is no round -1 survivor set to condition on, so
  round-0 logits are read directly off h_{-1}); for round t >= 1 the
  round-(t-1) bitmap (teacher-forced ground truth during training, or the
  model's own thresholded prediction during free-running rollout) is
  embedded and advanced through the SAME cell to produce h_t, and round-t
  logits are a linear readout of h_t. This gives four clean probe
  surfaces per round: the bitmap logits themselves, the pre-readout hidden
  h_t, the GRU's reset/update gates (inspectable via a forward hook), and
  -- since the verdict head is a small linear/MLP head off exactly one
  h_t (the example's own final round) -- a single injection point to test
  "does the verdict follow deterministically from the round-T dynamics
  state, or does the model use some other shortcut."

Encoder: identical token vocabulary/serialization to v1
(`d1_encoding.encode_config`); 2-layer TransformerEncoder, d_model=256,
4 heads, post-norm (matching the v1 `D1Transformer` encoder half; see
that module's docstring for the architecture-template attribution). The
"encoder summary" fed to the dynamics head is a masked mean-pool of the
per-token encoder output over non-PAD positions (no artificial CLS token
-- keeps every encoder output position doing the same job, i.e. still
individually probeable per input token).

Two models are defined here:
  D1v2DynamicsModel   -- encoder + DynamicsHead + verdict head off h_T.
  D1v2VerdictOnlyModel -- CONTROL: identical encoder, verdict head reads
                          the encoder summary directly (no dynamics head,
                          no per-round supervision at all). Same budget
                          (same encoder hyperparameters) as the dynamics
                          model, trained on the same verdict labels, so
                          the two models' verdict accuracy is a clean
                          measurement of what round-by-round dynamics
                          supervision adds over a plain classifier.

Both models are generic over ring size: `n_codes` (size of the
ring's canonical-code index, see data/v2/code_index_r{r}.json) is a
constructor argument, not hardcoded, so the same classes serve r=8, 9, 10
(and beyond) -- only the training data and n_codes differ.
"""

from __future__ import annotations

import torch
from torch import nn

from .d1_encoding import PAD_ID, VOCAB_SIZE


class D1v2Encoder(nn.Module):
    """Token encoder shared by the dynamics model and the verdict-only
    control. Same input serialization as v1 (`d1_encoding.encode_config`);
    a plain post-norm TransformerEncoder over token+position embeddings.
    Produces both the full per-token hidden sequence (for token-level
    probing) and a fixed-size "encoder summary" vector per configuration
    (masked mean-pool over non-PAD positions) that downstream heads
    condition on.
    """

    def __init__(
        self,
        d_model: int = 256,
        nhead: int = 4,
        dim_feedforward: int | None = None,
        max_len: int = 512,
        vocab_size: int = VOCAB_SIZE,
        pad_id: int = PAD_ID,
        num_layers: int = 2,
        dropout: float = 0.0,
    ):
        super().__init__()
        dim_feedforward = dim_feedforward or (2 * d_model)
        self.d_model = d_model
        self.max_len = max_len
        self.pad_id = pad_id
        self.vocab_size = vocab_size

        self.token_embedding = nn.Embedding(vocab_size, d_model, padding_idx=pad_id)
        self.pos_embedding = nn.Embedding(max_len, d_model)

        layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
            norm_first=False,  # post-norm, matching the v1 D1Transformer encoder
        )
        # enable_nested_tensor=False: see D1Transformer.__init__ in d1_model.py
        # for why (MPS eval-mode nested-tensor fast path is unimplemented).
        self.encoder = nn.TransformerEncoder(layer, num_layers=num_layers, enable_nested_tensor=False)

    def _embed(self, ids: torch.Tensor) -> torch.Tensor:
        seq_len = ids.size(1)
        positions = torch.arange(seq_len, device=ids.device).unsqueeze(0)
        return self.token_embedding(ids) + self.pos_embedding(positions)

    def forward(self, src_ids: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """src_ids: (B, S). Returns (tokens (B,S,d_model), summary
        (B,d_model), pad_mask (B,S) bool, True at PAD positions)."""
        pad_mask = src_ids == self.pad_id
        tokens = self.encoder(self._embed(src_ids), src_key_padding_mask=pad_mask)
        keep = (~pad_mask).unsqueeze(-1).to(tokens.dtype)
        summary = (tokens * keep).sum(dim=1) / keep.sum(dim=1).clamp(min=1.0)
        return tokens, summary, pad_mask


class DynamicsHead(nn.Module):
    """Shared iterated-map block: f(state_t, encoder_summary) -> h_t ->
    state_{t+1} logits. See module docstring for the round-0/round-t>=1
    split rationale. The GRUCell and readout are the SAME parameters at
    every round (no per-round weights), matching the underlying
    round-to-round closure map being a single fixed rule applied
    repeatedly."""

    def __init__(self, n_codes: int, d_model: int, dropout: float = 0.0):
        super().__init__()
        self.n_codes = n_codes
        self.d_model = d_model
        self.init_hidden = nn.Sequential(nn.Linear(d_model, d_model), nn.Tanh())
        self.state_in = nn.Linear(n_codes, d_model)
        self.cell = nn.GRUCell(d_model, d_model)
        self.readout = nn.Linear(d_model, n_codes)
        self.dropout = nn.Dropout(dropout)

    def init_state(self, encoder_summary: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """encoder_summary: (B, d_model). Returns (h_{-1}, round-0 logits),
        both derived directly from the encoder summary (there is no prior
        round to condition on)."""
        h = self.init_hidden(encoder_summary)
        logits0 = self.readout(self.dropout(h))
        return h, logits0

    def step(self, prev_bitmap: torch.Tensor, h: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """prev_bitmap: (B, n_codes) float in [0,1] -- either the true
        round-(t-1) bitmap (teacher forcing) or the model's own
        thresholded round-(t-1) prediction (free-running rollout). h:
        (B, d_model) previous hidden. Returns (round-t logits, h_t)."""
        inp = self.state_in(prev_bitmap)
        h_next = self.cell(inp, h)
        logits = self.readout(self.dropout(h_next))
        return logits, h_next


class D1v2DynamicsModel(nn.Module):
    """Encoder + DynamicsHead + a verdict head reading off exactly one
    dynamics hidden state per example: its own final round's h_t (index
    supplied by the caller, since different configurations in a batch
    converge after different numbers of rounds)."""

    def __init__(
        self,
        n_codes: int,
        d_model: int = 256,
        nhead: int = 4,
        dim_feedforward: int | None = None,
        max_len: int = 512,
        vocab_size: int = VOCAB_SIZE,
        pad_id: int = PAD_ID,
        num_encoder_layers: int = 2,
        dropout: float = 0.0,
    ):
        super().__init__()
        self.n_codes = n_codes
        self.d_model = d_model
        self.encoder = D1v2Encoder(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            max_len=max_len,
            vocab_size=vocab_size,
            pad_id=pad_id,
            num_layers=num_encoder_layers,
            dropout=dropout,
        )
        self.dynamics = DynamicsHead(n_codes, d_model, dropout=dropout)
        self.verdict_head = nn.Linear(d_model, 1)

    def forward(
        self,
        src_ids: torch.Tensor,
        true_bitmaps: torch.Tensor | None = None,
        n_rounds: int | None = None,
        mode: str = "teacher_force",
        threshold: float = 0.5,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Unrolls the dynamics head for T rounds (round 0 .. round T-1).

        mode="teacher_force": T = true_bitmaps.size(1); at each step t>=1
            the TRUE round-(t-1) bitmap (true_bitmaps[:, t-1, :]) is fed
            forward, regardless of the model's own predictions ("teacher
            forcing", no scheduled sampling -- see tools/d1v2_train.py
            module docstring for why plain teacher forcing was judged
            sufficient at this corpus size).
        mode="free_run": T = n_rounds + 1; at each step t>=1 the model's
            OWN round-(t-1) prediction, thresholded to a hard bitmap, is
            fed forward instead of ground truth.

        Returns (state_logits (B,T,n_codes), hiddens (B,T,d_model)), where
        index t along dim 1 is round t (t=0 is the initial round-0
        prediction, no dynamics step taken yet).
        """
        _, summary, _ = self.encoder(src_ids)
        h, logits0 = self.dynamics.init_state(summary)
        all_logits = [logits0]
        all_hidden = [h]

        if mode == "teacher_force":
            if true_bitmaps is None:
                raise ValueError("teacher_force mode requires true_bitmaps")
            T = true_bitmaps.size(1)
            for t in range(1, T):
                prev = true_bitmaps[:, t - 1, :]
                logits, h = self.dynamics.step(prev, h)
                all_logits.append(logits)
                all_hidden.append(h)
        elif mode == "free_run":
            if n_rounds is None:
                raise ValueError("free_run mode requires n_rounds")
            prev_prob = torch.sigmoid(logits0)
            for _ in range(n_rounds):
                prev_bitmap = (prev_prob >= threshold).to(prev_prob.dtype)
                logits, h = self.dynamics.step(prev_bitmap, h)
                all_logits.append(logits)
                all_hidden.append(h)
                prev_prob = torch.sigmoid(logits)
        else:
            raise ValueError(f"unknown mode: {mode!r}")

        state_logits = torch.stack(all_logits, dim=1)
        hiddens = torch.stack(all_hidden, dim=1)
        return state_logits, hiddens

    def verdict_logits(self, hiddens: torch.Tensor, round_idx: torch.Tensor) -> torch.Tensor:
        """hiddens: (B,T,d_model) from `forward`. round_idx: (B,) int64,
        each example's own final-round index (0-indexed into dim 1;
        typically the example's `rounds` field, since set_trace has
        `rounds+1` entries). Gathers per-example h_{round_idx} and reads
        off a scalar d_reducible logit -- "a verdict head off the final
        state," per the D1-v2 spec."""
        batch = torch.arange(hiddens.size(0), device=hiddens.device)
        gathered = hiddens[batch, round_idx]
        return self.verdict_head(gathered).squeeze(-1)


class D1v2VerdictOnlyModel(nn.Module):
    """CONTROL model: same encoder hyperparameters/budget as
    D1v2DynamicsModel, but NO dynamics head and NO per-round supervision
    -- the verdict head reads the encoder summary directly. Trained on the
    same verdict labels as the dynamics model; the accuracy gap between
    the two isolates what round-by-round survivor-set supervision adds
    over a plain encoder+classifier baseline."""

    def __init__(
        self,
        d_model: int = 256,
        nhead: int = 4,
        dim_feedforward: int | None = None,
        max_len: int = 512,
        vocab_size: int = VOCAB_SIZE,
        pad_id: int = PAD_ID,
        num_encoder_layers: int = 2,
        dropout: float = 0.0,
    ):
        super().__init__()
        self.d_model = d_model
        self.encoder = D1v2Encoder(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            max_len=max_len,
            vocab_size=vocab_size,
            pad_id=pad_id,
            num_layers=num_encoder_layers,
            dropout=dropout,
        )
        self.verdict_head = nn.Sequential(
            nn.Linear(d_model, d_model), nn.GELU(), nn.Linear(d_model, 1)
        )

    def forward(self, src_ids: torch.Tensor) -> torch.Tensor:
        """Returns (B,) d_reducible logits."""
        _, summary, _ = self.encoder(src_ids)
        return self.verdict_head(summary).squeeze(-1)


def count_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


if __name__ == "__main__":
    dyn = D1v2DynamicsModel(n_codes=1094)
    ctrl = D1v2VerdictOnlyModel()
    print(f"D1v2DynamicsModel parameter count:    {count_parameters(dyn):,}")
    print(f"D1v2VerdictOnlyModel parameter count: {count_parameters(ctrl):,}")
