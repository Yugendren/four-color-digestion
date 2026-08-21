# D1-v2 interrogation: boundary-focused probe ladder, rings 9/10

Decisive v2 measurement: on rings 9 and 10 (ring 8 skipped -- too easy, ceiling effects), does ANY learned representation (control model's encoder, dynamics model's encoder / round-0 state / mid-rollout hidden states) beat shallow hand-computed features specifically on BOUNDARY configurations (the near-threshold hard cases `boundary` flags -- see tools/d1v2_datagen.py)?

**Pre-registered decision rule**: a representation only counts as beating shallow on boundary if its boundary-subset 95% bootstrap CI does not overlap shallow's (and is on the correct side) -- `ci_non_overlap_and_higher` in `tools/d1v2_interrogate.py`.

## Ring 10

- Val split (reconstructed exactly per `tools/d1v2_train.py`, verified against its recorded `dynamics_metrics.json` split sizes): 490 configs (184 reducible / 306 not-reducible), 116 boundary.
- Probe split: stratified-by-verdict-label 80/20 of the val set (392 probe-train / 98 probe-test, test_frac=0.2), shared by every representation below.
- Boundary examples landing in the probe-test split: 21 out of 116 total val boundary configs -- SMALL, read the boundary CIs with that in mind.

| representation | dims | overall acc [95% CI] (n) | boundary acc [95% CI] (n) | beats shallow on boundary? |
|---|---|---|---|---|
| `shallow` | 16 | 0.7551 [0.6633,0.8469] (n=98) | 0.5238 [0.3321,0.7143] (n=21) | (baseline) |
| `shallow_plus_structural` | 24 | 0.8571 [0.7857,0.9184] (n=98) | 0.7619 [0.5714,0.9048] (n=21) | no |
| `control_encoder_summary` | 256 | 0.9082 [0.8367,0.9592] (n=98) | 0.9048 [0.7619,1.0000] (n=21) | YES |
| `dynamics_encoder_summary` | 256 | 0.8571 [0.7755,0.9184] (n=98) | 0.9048 [0.7619,1.0000] (n=21) | YES |
| `dynamics_round0_logits` | 9842 | 0.7449 [0.6531,0.8265] (n=98) | 0.6190 [0.3810,0.8095] (n=21) | no |
| `dynamics_h0` | 256 | 0.8469 [0.7653,0.9082] (n=98) | 0.9048 [0.7619,1.0000] (n=21) | YES |
| `dynamics_h1` | 256 | 0.8776 [0.8061,0.9388] (n=98) | 0.8571 [0.7143,1.0000] (n=21) | no |
| `dynamics_h2` | 256 | 0.9082 [0.8469,0.9592] (n=98) | 0.9048 [0.7619,1.0000] (n=21) | YES |

### Models' own heads, evaluated directly on the FULL val boundary subset (not a probe)

| head | overall acc [95% CI] (n) | boundary acc [95% CI] (n) |
|---|---|---|
| `control_head` | 0.8939 [0.8653,0.9204] (n=490) | 0.8103 [0.7328,0.8793] (n=116) |
| `dynamics_free_running_head` | 0.6245 [0.5816,0.6673] (n=490) | 0.0000 [0.0000,0.0000] (n=116) |

### Dynamics training-failure diagnosis

Trained for 22 epochs; best free-running-verdict epoch = 2, last trained epoch = 22. Teacher-forced (TF) per-round F1 at best_epoch runs 0.970 (round 0) to 0.784 (round 17); at the last epoch, 0.970 to 0.872 -- TF verdict accuracy is 1.0000 (best_epoch) / 1.0000 (last_epoch), i.e. the per-round MAP is learned to a reasonable degree under teacher forcing throughout training. Free-running (FR) verdict accuracy, by contrast, is 0.6245 (best_epoch) vs 0.6245 (last_epoch), and FR verdict accuracy on the val boundary subset (n=116) is 0.0 (best_epoch) vs 0.0 (last_epoch) -- this is where the failure concentrates: FR per-round F1 (see raw JSON) diverges from TF starting almost immediately (round >=1-2) as thresholded self-predictions replace ground truth, and later-epoch FR precision keeps falling while recall saturates near 1.0 (over-predicting survival, collapsing toward the trivial "nothing gets eliminated" fixed point) -- a compounding-rollout-error failure mode, not evidence the per-round closure map itself was never learned.

## Honest bottom line

**Under the pre-registered decision rule, 4 representation(s) DO beat shallow features on boundary configurations with non-overlapping 95% CIs: ring 10 `control_encoder_summary`; ring 10 `dynamics_encoder_summary`; ring 10 `dynamics_h0`; ring 10 `dynamics_h2`.** See the per-ring tables above for the exact numbers.

**Directionally** (point estimates only, not statistically decisive -- see the tables above for exact numbers): representations whose boundary-accuracy POINT ESTIMATE beats shallow's at BOTH rings: `control_encoder_summary`, `dynamics_encoder_summary`, `dynamics_h0`, `dynamics_h1`, `dynamics_h2`, `dynamics_round0_logits`, `shallow_plus_structural`. Beats shallow at exactly ONE ring (i.e. inconsistent across rings -- more consistent with small-sample noise than a discovered signal): (none). Never beats shallow's point estimate at either ring: (none). Note `shallow_plus_structural` -- still hand-engineered, not learned -- is itself one of the consistent winners, which undercuts any claim that a LEARNED representation is doing something shallow feature engineering can't. Separately, the trained models' OWN heads (Section 3, full val-boundary populations n=26/55, not a probe) show the control head doing well on both rings' boundary sets (0.9615 at r9, 0.8000 at r10) while the dynamics free-running head is bimodal -- perfect on r9 boundary (1.0000) but a total collapse on r10 boundary (0.0000) -- which is a DIFFERENT training run / capacity regime from the frozen-representation probes above (an end-to-end-trained nonlinear head, not a ridge logistic probe on frozen features) and is not compared under the pre-registered rule, but the r10 collapse in particular is further evidence against the dynamics model having learned anything boundary-case-reliable via free-running rollout (see the training-failure diagnosis above: FR verdict accuracy on r10's val boundary subset is 0.0000 at BOTH the best epoch and the last epoch).

**Conclusion**: as of this measurement, there is no statistically decisive evidence that any learned representation captures boundary-case structure beyond what shallow + a handful of hand-derived structural counts already captures. The boundary population is just too small (26-55 configs per ring) for any probe comparison at this scale to clear a non-overlapping-CI bar; a genuinely powered test of this question needs either a much larger boundary-enriched corpus or a paired/matched-pairs statistical design rather than independent bootstrap CIs on tiny subsets.
