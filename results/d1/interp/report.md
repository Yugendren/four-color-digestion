# D1 interrogation: early-verdict structure in the encoder

Probes the trained D1Transformer checkpoint (`checkpoints/d1_full_v1.pt`, 93% held-out verdict accuracy) for whether its ENCODER -- which only ever sees the config, before any trajectory decoding -- already knows the final D-reducibility verdict, and whether that knowledge is deeper than shallow hand-computed features.

## Setup

- Checkpoint: `/Users/yugendren/experiments/four_color_digestion/checkpoints/d1_full_v1.pt`
- Held-out val split reconstructed EXACTLY per `tools/d1_train.py` (seed=0, val_frac=0.1, max_src/tgt_len=256): train=5904, val=655. `load_stats`: {'corpus_total': 14036, 'no_trace_excluded': 4828, 'too_long_excluded': 2649, 'usable': 6559}
- Val label balance: 288 reducible / 367 not-reducible (majority-class baseline = 0.5603)
- All probes are ridge-regularized (`weight_decay`) torch logistic regressions (single linear layer, standardized inputs), trained/evaluated on the SAME stratified 80/20 split of this val set (524 probe-train / 131 probe-test, seed=0), with 95% bootstrap CIs (n_boot=2000).
- Encoder-state capture ran over the entire corpus subject to the checkpoint's fixed positional-embedding capacity (`model.max_len=259`): 7021/14036 configs are encodable by this checkpoint at all (7015 exceed its learned positional range and cannot be forward-passed through it, full stop -- this is the checkpoint's own hard limit, not a filtering choice made for this analysis).

## 2. The early-verdict probe ladder

| representation | dims | test accuracy [95% CI] | train acc |
|---|---|---|---|
| `baseline_shallow` | 16 | 0.8779 [0.8168, 0.9313] (n=131) | 0.8626 |
| `encoder_layer0_mean` | 192 | 0.9008 [0.8473, 0.9466] (n=131) **<- best encoder repr** | 0.8817 |
| `encoder_layer1_mean` | 192 | 0.8855 [0.8321, 0.9389] (n=131) | 0.9599 |
| `encoder_layer2_mean` | 192 | 0.8855 [0.8321, 0.9389] (n=131) | 0.9866 |
| `encoder_layer2_ring_only` | 192 | 0.8855 [0.8321, 0.9389] (n=131) | 0.9847 |
| `encoder_layer2_interior_only` | 192 | 0.8931 [0.8397, 0.9466] (n=131) | 0.9847 |
| `combined_shallow_plus_encoder_final` | 208 | 0.9084 [0.8626, 0.9542] (n=131) | 0.9905 |

Best PURE-ENCODER representation (excludes the combined control, which trivially contains the shallow features): **`encoder_layer0_mean`** at 0.9008 vs BASELINE-SHALLOW at 0.8779 (delta = +0.0229). CIs OVERLAP (shallow 95% CI = [0.8168,0.9313], encoder_layer0_mean 95% CI = [0.8473,0.9466]).
Additive-signal check: COMBINED (shallow+encoder) reaches 0.9084, +0.0076 over the best pure-encoder representation alone -- essentially no additive gain, consistent with the encoder's verdict-relevant information being largely redundant with the shallow features once both are available to a linear probe.

Notably, the single best pure-encoder representation here is `encoder_layer0_mean` -- the raw token+positional EMBEDDING, mean-pooled, before any self-attention has run at all. The post-attention layers (`encoder_layer1_mean`, `encoder_layer2_mean`) do *not* improve on it for this linear probe (see table), despite fitting the training data far more tightly (compare `train_acc` columns). That is itself a finding: whatever extra verdict-signal the encoder carries beyond BASELINE-SHALLOW looks like it is present already in a `bag-of-input-tokens` sense (e.g. the DEG/MAG magnitude tokens the shallow degree histogram also reads), not something that requires multi-hop self-attention to construct.

### Per-ring-size breakdown (probe-test split)

| ring size r | n (test) | baseline_shallow acc | encoder_layer0_mean acc |
|---|---|---|---|
| 6 | 1 | 1.000 | 1.000 |
| 7 | 1 | 1.000 | 1.000 |
| 8 | 20 | 0.950 | 0.900 |
| 9 | 30 | 0.833 | 0.867 |
| 10 | 30 | 0.733 | 0.867 |
| 11 | 41 | 1.000 | 0.951 |
| 12 | 6 | 1.000 | 0.833 |
| 13 | 2 | 0.000 | 1.000 |

## 3. Early-decision-in-decoding

Decoder hidden state at greedy-decode step t, probed for the final verdict (t=0 is the state right after BOS -- using ONLY encoder cross-attention, no trajectory tokens decoded yet). Reference: full greedy-decode verdict accuracy on this exact split = 0.9298 (source: results/d1/train_metrics_full_v1.json epoch 120's eval, which uses the identical reconstructed val split; independently re-confirmed during this tool's development by running a full (max_len=259-step) greedy decode over exactly this split, which reproduced 0.9297709923664123 exactly.). Partial (40-step) greedy-decode verdict accuracy here = 0.9053 (verdict token present in 96.0% of rows by that step).

| t | probe test acc | 95% CI | n_test |
|---|---|---|---|
| 0 | 0.8473 | [0.7863, 0.9084] | 131 |
| 1 | 0.8473 | [0.7863, 0.9084] | 131 |
| 2 | 0.9160 | [0.8702, 0.9618] | 131 |
| 3 | 0.8550 | [0.7939, 0.9084] | 131 |
| 4 | 0.8244 | [0.7557, 0.8855] | 131 |
| 5 | 0.8931 | [0.8397, 0.9466] | 131 |
| 6 | 0.8626 | [0.8015, 0.9160] | 131 |
| 7 | 0.8626 | [0.8015, 0.9160] | 131 |
| 8 | 0.9160 | [0.8702, 0.9618] | 131 |
| 9 | 0.9389 | [0.9008, 0.9771] | 131 |
| 10 | 0.8779 | [0.8244, 0.9313] | 131 |
| 11 | 0.9313 | [0.8855, 0.9695] | 131 |
| 12 | 0.9237 | [0.8779, 0.9618] | 131 |
| 13 | 0.8702 | [0.8092, 0.9237] | 131 |
| 14 | 0.9084 | [0.8626, 0.9542] | 131 |
| 15 | 0.9084 | [0.8550, 0.9542] | 131 |
| 16 | 0.8626 | [0.8015, 0.9160] | 131 |
| 17 | 0.9008 | [0.8473, 0.9466] | 131 |
| 18 | 0.8855 | [0.8321, 0.9389] | 131 |
| 19 | 0.8855 | [0.8321, 0.9389] | 131 |
| 20 | 0.8855 | [0.8321, 0.9389] | 131 |
| 21 | 0.8855 | [0.8321, 0.9389] | 131 |
| 22 | 0.8626 | [0.8015, 0.9160] | 131 |
| 23 | 0.8626 | [0.8015, 0.9160] | 131 |
| 24 | 0.9160 | [0.8702, 0.9618] | 131 |
| 25 | 0.8550 | [0.7939, 0.9084] | 131 |
| 26 | 0.9008 | [0.8473, 0.9542] | 131 |
| 27 | 0.8550 | [0.7939, 0.9084] | 131 |
| 28 | 0.8702 | [0.8092, 0.9237] | 131 |
| 29 | 0.9160 | [0.8702, 0.9618] | 131 |
| 30 | 0.9160 | [0.8626, 0.9618] | 131 |
| 31 | 0.8702 | [0.8168, 0.9237] | 131 |
| 32 | 0.8779 | [0.8168, 0.9313] | 131 |
| 33 | 0.9008 | [0.8473, 0.9466] | 131 |
| 34 | 0.8855 | [0.8321, 0.9389] | 131 |
| 35 | 0.8244 | [0.7557, 0.8855] | 131 |
| 36 | 0.9008 | [0.8473, 0.9466] | 131 |
| 37 | 0.8473 | [0.7863, 0.9084] | 131 |
| 38 | 0.8855 | [0.8321, 0.9389] | 131 |
| 39 | 0.8702 | [0.8092, 0.9237] | 131 |

t=0 probe accuracy = 0.8473 [0.7863,0.9084] -- well above the majority-class baseline (0.5603) and in the same range as BASELINE-SHALLOW (0.8779). Averaged over t=0-2 (0.8702) vs the last 5 steps t=35-39 (0.8656): no meaningful improvement. 
Every later step's 95% CI overlaps t=0's -- the curve is statistically FLAT within bootstrap noise across all 40 steps sampled. This IS the early-decision signature: whatever the decoder linearly knows about the verdict from a linear probe's perspective, it already knows at t=0, from cross-attention into the encoder memory alone, before a single closure-trace token has been decoded -- decoding the rest of the trajectory does not measurably add linearly-probable verdict information on top of that (caveat: n_test=131 per step gives fairly wide CIs, so this is 'no detected improvement', not proof of exactly zero improvement).

## 4. Extraction attempt (exploratory)

Scored the `encoder_layer0_mean` probe's decision direction (logit[reducible] - logit[not-reducible]) over 7021 configs (the full corpus, subject to the checkpoint positional-length limit above), then correlated that scalar against a library of candidate interpretable quantities (Pearson + Spearman). For genuinely NEW candidates (not already inside the shallow baseline), also retrained shallow+candidate and report whether it closes the gap to the best encoder probe (n_test=131, so shallow+candidate test accuracy is quantized in steps of 1/131 = 0.0076; small deltas/gap-closed percentages should be read as noisy, not precise). **Correlational only -- no causal claim.**

| candidate | pearson r | spearman r | shallow+cand acc | delta vs shallow | gap closed | note |
|---|---|---|---|---|---|---|
| `n_interior` | +0.802 | +0.811 | - | - | - | already in shallow baseline |
| `deg_3` | -0.762 | -0.767 | - | - | - | already in shallow baseline |
| `n_extendable_ratio` | +0.692 | +0.763 | 0.8931 | +0.0153 | 67% |  |
| `n_deg5_interior` | +0.614 | +0.609 | 0.8702 | -0.0076 | -33% |  |
| `n_consistent` | -0.580 | -0.850 | 0.9160 | +0.0382 | 167% | TAUTOLOGICAL (== label by definition) |
| `deg_5` | +0.499 | +0.479 | - | - | - | already in shallow baseline |
| `n_deg5_total` | +0.499 | +0.479 | 0.8779 | +0.0000 | 0% |  |
| `r` | -0.449 | -0.481 | - | - | - | already in shallow baseline |
| `mean_interior_degree` | -0.413 | -0.365 | - | - | - | already in shallow baseline |
| `n` | +0.315 | +0.302 | - | - | - | already in shallow baseline |
| `n_triangles_deg5` | +0.250 | +0.268 | 0.9008 | +0.0229 | 100% |  |
| `deg_6` | +0.249 | +0.249 | - | - | - | already in shallow baseline |
| `max_interior_degree` | -0.202 | -0.189 | - | - | - | already in shallow baseline |
| `n_diamonds_deg5` | +0.182 | +0.216 | 0.9008 | +0.0229 | 100% |  |
| `deg_4` | +0.170 | +0.164 | - | - | - | already in shallow baseline |
| `max_run_const_degree_ring` | -0.166 | -0.190 | 0.8855 | +0.0076 | 33% |  |
| `min_interior_degree` | -0.119 | -0.082 | - | - | - | already in shallow baseline |
| `deg_9` | -0.111 | -0.103 | - | - | - | already in shallow baseline |
| `deg_8` | -0.101 | -0.106 | - | - | - | already in shallow baseline |
| `deg_10` | -0.081 | -0.062 | - | - | - | already in shallow baseline |
| `max_run_deg5_ring` | +0.077 | +0.059 | 0.8779 | +0.0000 | 0% |  |
| `deg_11` | -0.014 | -0.007 | - | - | - | already in shallow baseline |
| `deg_7` | -0.010 | -0.014 | - | - | - | already in shallow baseline |
| `n_extendable` | -0.009 | -0.366 | 0.8779 | +0.0000 | 0% |  |
| `deg_12p` | +0.000 | +0.000 | - | - | - | already in shallow baseline |

**shallow + ALL new structural candidates combined**: test acc = 0.9237 [0.8779,0.9695] (delta vs shallow = +0.0458, gap closed = 200%).

## 5. Honest verdict

- **Does the encoder know more than shallow features?** MARGINALLY, by a modest margin with overlapping CIs: `encoder_layer0_mean` beats BASELINE-SHALLOW by +0.0229 absolute test accuracy (0.8779 -> 0.9008, 95% CIs [0.8168,0.9313] vs [0.8473,0.9466]). At n_test=131 this is directionally consistent but not a statistically decisive win.
- **Is it deeper than shallow features, or just a repackaging of them?** Mostly repackaging: the winning pure-encoder representation is `encoder_layer0_mean` -- the pre-attention embedding bag -- and the post-attention layers 1/2 do NOT improve on it (0.8855 / 0.8855 vs 0.9008). Combining shallow+encoder barely beats either alone (0.9084, +0.0076 over best-pure-encoder). And most tellingly: shallow features PLUS the hand-derived structural candidates from Section 4 reach 0.9237 -- *higher* than the encoder's own best pure representation (0.9008). Whatever the encoder is doing, a handful of hand-computed structural counts (interior degree-5 counts, degree-5 triangles/diamonds, extendable-coloring ratio) matches or beats it on this probe-test set. That is evidence AGAINST the encoder having discovered meaningfully deeper structure than what a modest amount of graph-theoretic feature engineering already captures -- at least, deeper structure that is linearly decodable from a mean-pooled representation.
- **Where does the (modest) extra knowledge live?** `encoder_layer2_interior_only` (0.8931) vs `encoder_layer2_ring_only` (0.8855): interior-only pooling is +0.0076 over ring-only, a small lean toward the interior patch mattering slightly more than the ring boundary alone for this linear probe -- but both are within each other's CIs, so this is a weak lead, not a finding.
- **Early-decision-in-decoding:** the probe-test-accuracy curve is statistically flat from t=0 onward (every later step's CI overlaps t=0's) -- the decoder's hidden state right after BOS, using only cross-attention into the encoder memory, is already about as verdict-informative (linearly) as any later decoding step. The nominal 'closure trace' tokens the model also learns to produce look like they ride along rather than build up verdict evidence step by step.
- **What does the encoder seem to be computing?** The extraction pass's top overall correlates of the `encoder_layer0_mean` probe direction are `n_interior` (r=+0.802), `deg_3` (r=-0.762), `n_extendable_ratio` (r=+0.692) -- mostly quantities already inside the shallow baseline. Restricting to genuinely NEW structural candidates (not already in the shallow baseline), the top-correlating ones here are `n_extendable_ratio`, `n_deg5_interior`; `n_extendable_ratio` (|C(K)|/3^(r-1), the extendable-coloring fraction from `fourcolor.reduce`) and `n_deg5_interior` are real reducibility-theory quantities, but their shallow+candidate retrain gains are small and within the ~1/131=0.0076 test-accuracy quantization noise -- suggestive, not established. Report correlations honestly as correlations, not mechanism.

