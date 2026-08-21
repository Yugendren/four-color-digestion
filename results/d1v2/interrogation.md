# D1-v2 interrogation: boundary-focused probe ladder, rings 9/10

Decisive v2 measurement: on rings 9 and 10 (ring 8 skipped -- too easy, ceiling effects), does ANY learned representation (control model's encoder, dynamics model's encoder / round-0 state / mid-rollout hidden states) beat shallow hand-computed features specifically on BOUNDARY configurations (the near-threshold hard cases `boundary` flags -- see tools/d1v2_datagen.py)?

**Pre-registered decision rule**: a representation only counts as beating shallow on boundary if its boundary-subset 95% bootstrap CI does not overlap shallow's (and is on the correct side) -- `ci_non_overlap_and_higher` in `tools/d1v2_interrogate.py`.

## Ring 9

- Val split (reconstructed exactly per `tools/d1v2_train.py`, verified against its recorded `dynamics_metrics.json` split sizes): 216 configs (164 reducible / 52 not-reducible), 26 boundary.
- Probe split: stratified-by-verdict-label 80/20 of the val set (173 probe-train / 43 probe-test, test_frac=0.2), shared by every representation below.
- Boundary examples landing in the probe-test split: 7 out of 26 total val boundary configs -- SMALL, read the boundary CIs with that in mind.

| representation | dims | overall acc [95% CI] (n) | boundary acc [95% CI] (n) | beats shallow on boundary? |
|---|---|---|---|---|
| `shallow` | 16 | 0.7209 [0.5814,0.8605] (n=43) | 0.5714 [0.2857,0.8571] (n=7) | (baseline) |
| `shallow_plus_structural` | 24 | 0.8140 [0.6977,0.9302] (n=43) | 0.8571 [0.5714,1.0000] (n=7) | no |
| `control_encoder_summary` | 256 | 0.8837 [0.7907,0.9767] (n=43) | 0.5714 [0.1429,0.8571] (n=7) | no |
| `dynamics_encoder_summary` | 256 | 0.7907 [0.6744,0.9070] (n=43) | 0.2857 [0.0000,0.5714] (n=7) | no |
| `dynamics_round0_logits` | 3281 | 0.7209 [0.5814,0.8372] (n=43) | 0.1429 [0.0000,0.4286] (n=7) | no |
| `dynamics_h0` | 256 | 0.7907 [0.6744,0.9070] (n=43) | 0.2857 [0.0000,0.5714] (n=7) | no |
| `dynamics_h1` | 256 | 0.9070 [0.8140,0.9767] (n=43) | 0.7143 [0.4286,1.0000] (n=7) | no |
| `dynamics_h2` | 256 | 0.9070 [0.8140,0.9767] (n=43) | 0.4286 [0.1429,0.8571] (n=7) | no |

### Models' own heads, evaluated directly on the FULL val boundary subset (not a probe)

| head | overall acc [95% CI] (n) | boundary acc [95% CI] (n) |
|---|---|---|
| `control_head` | 0.9491 [0.9167,0.9769] (n=216) | 0.9615 [0.8846,1.0000] (n=26) |
| `dynamics_free_running_head` | 0.7778 [0.7222,0.8333] (n=216) | 1.0000 [1.0000,1.0000] (n=26) |

### Dynamics training-failure diagnosis

Trained for 21 epochs; best free-running-verdict epoch = 1, last trained epoch = 21. Teacher-forced (TF) per-round F1 at best_epoch runs 0.955 (round 0) to 0.354 (round 10); at the last epoch, 0.955 to 0.645 -- TF verdict accuracy is 1.0000 (best_epoch) / 1.0000 (last_epoch), i.e. the per-round MAP is learned to a reasonable degree under teacher forcing throughout training. Free-running (FR) verdict accuracy, by contrast, is 0.7778 (best_epoch) vs 0.2407 (last_epoch), and FR verdict accuracy on the val boundary subset (n=26) is 1.0 (best_epoch) vs 0.0 (last_epoch) -- this is where the failure concentrates: FR per-round F1 (see raw JSON) diverges from TF starting almost immediately (round >=1-2) as thresholded self-predictions replace ground truth, and later-epoch FR precision keeps falling while recall saturates near 1.0 (over-predicting survival, collapsing toward the trivial "nothing gets eliminated" fixed point) -- a compounding-rollout-error failure mode, not evidence the per-round closure map itself was never learned.

## Ring 10

- Val split (reconstructed exactly per `tools/d1v2_train.py`, verified against its recorded `dynamics_metrics.json` split sizes): 262 configs (58 reducible / 204 not-reducible), 55 boundary.
- Probe split: stratified-by-verdict-label 80/20 of the val set (209 probe-train / 53 probe-test, test_frac=0.2), shared by every representation below.
- Boundary examples landing in the probe-test split: 11 out of 55 total val boundary configs -- SMALL, read the boundary CIs with that in mind.

| representation | dims | overall acc [95% CI] (n) | boundary acc [95% CI] (n) | beats shallow on boundary? |
|---|---|---|---|---|
| `shallow` | 16 | 0.7547 [0.6415,0.8679] (n=53) | 0.4545 [0.1818,0.7273] (n=11) | (baseline) |
| `shallow_plus_structural` | 24 | 0.9057 [0.8302,0.9811] (n=53) | 0.7273 [0.4545,1.0000] (n=11) | no |
| `control_encoder_summary` | 256 | 0.9057 [0.8113,0.9811] (n=53) | 0.8182 [0.5455,1.0000] (n=11) | no |
| `dynamics_encoder_summary` | 256 | 0.7736 [0.6604,0.8868] (n=53) | 0.8182 [0.5455,1.0000] (n=11) | no |
| `dynamics_round0_logits` | 9842 | 0.7925 [0.6792,0.8868] (n=53) | 0.6364 [0.3636,0.9091] (n=11) | no |
| `dynamics_h0` | 256 | 0.7736 [0.6604,0.8868] (n=53) | 0.7273 [0.4545,1.0000] (n=11) | no |
| `dynamics_h1` | 256 | 0.8868 [0.7925,0.9623] (n=53) | 0.8182 [0.5455,1.0000] (n=11) | no |
| `dynamics_h2` | 256 | 0.9245 [0.8491,0.9811] (n=53) | 0.7273 [0.4545,1.0000] (n=11) | no |

### Models' own heads, evaluated directly on the FULL val boundary subset (not a probe)

| head | overall acc [95% CI] (n) | boundary acc [95% CI] (n) |
|---|---|---|
| `control_head` | 0.9122 [0.8778,0.9427] (n=262) | 0.8000 [0.6909,0.8909] (n=55) |
| `dynamics_free_running_head` | 0.7786 [0.7252,0.8321] (n=262) | 0.0000 [0.0000,0.0000] (n=55) |

### Dynamics training-failure diagnosis

Trained for 22 epochs; best free-running-verdict epoch = 2, last trained epoch = 22. Teacher-forced (TF) per-round F1 at best_epoch runs 0.973 (round 0) to 0.666 (round 13); at the last epoch, 0.973 to 0.809 -- TF verdict accuracy is 1.0000 (best_epoch) / 1.0000 (last_epoch), i.e. the per-round MAP is learned to a reasonable degree under teacher forcing throughout training. Free-running (FR) verdict accuracy, by contrast, is 0.7786 (best_epoch) vs 0.7786 (last_epoch), and FR verdict accuracy on the val boundary subset (n=55) is 0.0 (best_epoch) vs 0.0 (last_epoch) -- this is where the failure concentrates: FR per-round F1 (see raw JSON) diverges from TF starting almost immediately (round >=1-2) as thresholded self-predictions replace ground truth, and later-epoch FR precision keeps falling while recall saturates near 1.0 (over-predicting survival, collapsing toward the trivial "nothing gets eliminated" fixed point) -- a compounding-rollout-error failure mode, not evidence the per-round closure map itself was never learned.

## Honest bottom line

**Under the pre-registered decision rule (non-overlapping 95% CIs on the boundary subset), NO representation -- not the control model's encoder, not the dynamics model's encoder, round-0 state, or mid-rollout hidden states h0/h1/h2 -- beats shallow hand-computed features on boundary configurations, at either ring 9 or ring 10.** Every boundary-subset CI in both tables above overlaps shallow's. This is not a null result manufactured by an unreasonably strict rule: the boundary-subset sample sizes are simply small (7/43 and 11/53 probe-test examples land in the boundary stratum at r9/r10 respectively, out of 26/55 total val-boundary configs), so 95% CIs on boundary accuracy span roughly half the [0,1] range for every representation -- nothing could clear that bar without an implausibly large true effect.

**Directionally** (point estimates only, not statistically decisive -- see the tables above for exact numbers): representations whose boundary-accuracy POINT ESTIMATE beats shallow's at BOTH rings: `dynamics_h1`, `shallow_plus_structural`. Beats shallow at exactly ONE ring (i.e. inconsistent across rings -- more consistent with small-sample noise than a discovered signal): `control_encoder_summary`, `dynamics_encoder_summary`, `dynamics_h0`, `dynamics_h2`, `dynamics_round0_logits`. Never beats shallow's point estimate at either ring: (none). Note `shallow_plus_structural` -- still hand-engineered, not learned -- is itself one of the consistent winners, which undercuts any claim that a LEARNED representation is doing something shallow feature engineering can't. Separately, the trained models' OWN heads (Section 3, full val-boundary populations n=26/55, not a probe) show the control head doing well on both rings' boundary sets (0.9615 at r9, 0.8000 at r10) while the dynamics free-running head is bimodal -- perfect on r9 boundary (1.0000) but a total collapse on r10 boundary (0.0000) -- which is a DIFFERENT training run / capacity regime from the frozen-representation probes above (an end-to-end-trained nonlinear head, not a ridge logistic probe on frozen features) and is not compared under the pre-registered rule, but the r10 collapse in particular is further evidence against the dynamics model having learned anything boundary-case-reliable via free-running rollout (see the training-failure diagnosis above: FR verdict accuracy on r10's val boundary subset is 0.0000 at BOTH the best epoch and the last epoch).

**Conclusion**: as of this measurement, there is no statistically decisive evidence that any learned representation captures boundary-case structure beyond what shallow + a handful of hand-derived structural counts already captures. The boundary population is just too small (26-55 configs per ring) for any probe comparison at this scale to clear a non-overlapping-CI bar; a genuinely powered test of this question needs either a much larger boundary-enriched corpus or a paired/matched-pairs statistical design rather than independent bootstrap CIs on tiny subsets.
