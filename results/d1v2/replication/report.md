# Ring-10 boundary result: seed replication + error-set digestion

Two follow-ups to the positive ring-10 finding in
`results/d1v2/v2run/interrogation.json` / `interrogation.md`: on the
enlarged corpus `data/v2/traces_r10.jsonl` (3,269 configs, 776 boundary),
`control_encoder_summary` (D1v2VerdictOnlyModel's frozen encoder,
mean-pool summary, linear probe) beats `shallow` hand-computed features on
BOUNDARY configs with non-overlapping 95% bootstrap CIs at probe seed 0
(boundary_acc 0.9048 [0.7619, 1.0000] vs 0.5238 [0.3321, 0.7143], n=21
boundary probe-test examples).

1. **Seed replication** -- is that seed-0 result contingent on one lucky
   train/val split + model init, or does it hold up across seeds?
2. **Error-set digestion** -- which specific boundary configs does the
   encoder probe get right that `shallow_plus_structural` (still
   hand-engineered, the stronger of the two shallow baselines) gets
   wrong, and what distinguishes them numerically?

## Part 1: Seed replication

`tools/d1v2_train.py --seed` drives BOTH the train/val split (via
`stratified_split`, which shuffles with that seed) AND model
init/minibatch order -- so a seed-0-only result could in principle be an
artifact of one lucky split+init pairing. Retrained the CONTROL model only
(fast: `--model control`, ~2-4 min/seed on this machine, no dynamics
model needed for this probe ladder) at ring 10 for seeds 1, 2, 3 (seed 0
reuses the existing `results/d1v2/r10v2` control model), reconstructed
each seed's own val split from its own `control_metrics.json`
hyperparameters (verified against that file's recorded split sizes via
`tools/d1v2_interrogate.py`'s own `verify_split_against_metrics`), and
reran the shallow / shallow_plus_structural / control_encoder_summary
probe ladder (same probe methodology as the original interrogation:
stratified 80/20 probe-train/probe-test split of that seed's val set,
probe_seed=0, n_boot=2000) against each seed's own control model.

Script: `results/d1v2/replication/collect_seed_replication.py`. Raw
output: `results/d1v2/replication/seed_replication.json`,
`seed_replication_summary.txt`, per-seed training logs
`train_seed{1,2,3}.log`. New model checkpoints:
`results/d1v2/r10s{1,2,3}/control_best.pt` (+ `control_metrics.json`,
`summary.json`).

### Per-seed boundary accuracy

| seed | val boundary (n=116 total) probe-test n | `shallow` boundary acc [95% CI] | `shallow_plus_structural` boundary acc [95% CI] | `control_encoder_summary` boundary acc [95% CI] | beats shallow? (non-overlapping CI, pre-registered rule) |
|---|---|---|---|---|---|
| 0 | 21 | 0.5238 [0.3321, 0.7143] | 0.7619 [0.5714, 0.9048] | **0.9048 [0.7619, 1.0000]** | **YES** |
| 1 | 23 | 0.4348 [0.2174, 0.6522] | 0.7826 [0.6087, 0.9565] | 0.7826 [0.6087, 0.9130] | no (CIs overlap) |
| 2 | 24 | 0.5417 [0.3333, 0.7500] | 0.7083 [0.5000, 0.8750] | 0.7500 [0.5833, 0.9167] | no (CIs overlap) |
| 3 | 25 | 0.5200 [0.3200, 0.7200] | 0.7600 [0.6000, 0.9200] | **0.9200 [0.8000, 1.0000]** | **YES** |

(Overall, non-boundary-restricted, probe-test accuracy for context: seed
0 `control_encoder_summary` overall=0.9082; seed 1 overall=0.8571; seed 2
overall=0.8265; seed 3 overall=0.9184 -- all n=98. Full numbers including
`train_acc`, `d_features`, etc. in `seed_replication.json`.)

### Does the result replicate across all seeds?

**Directionally: yes, at all 4/4 seeds** -- `control_encoder_summary`'s
boundary-accuracy POINT ESTIMATE beats `shallow`'s point estimate at
every seed (0.9048 > 0.5238; 0.7826 > 0.4348; 0.7500 > 0.5417; 0.9200 >
0.5200 -- gaps of +0.38, +0.35, +0.21, +0.40 respectively), and beats
`shallow_plus_structural`'s point estimate at 3/4 seeds (seed 1 is a tie
at 0.7826 for both).

**Under the pre-registered non-overlapping-CI decision rule
(`ci_non_overlap_and_higher`): only 2/4 seeds (0 and 3) clear the bar**
against plain `shallow`; seeds 1 and 2 do not, because the boundary
probe-test population is small (21-25 examples) and both distributions'
CIs are ~0.2-0.35 wide, so the same underlying effect can straddle the
strict non-overlap threshold seed to seed. None of the 4 seeds' CI clears
the bar against `shallow_plus_structural` specifically (the stronger,
also hand-engineered baseline) -- `shallow_plus_structural`'s own CI
already overlaps `control_encoder_summary`'s at every seed.

**Bottom line**: the direction of the effect (learned encoder > plain
shallow features on boundary configs) is consistent across all 4 tested
seeds -- this is NOT an artifact of one lucky seed-0 split+init. But the
MAGNITUDE is seed-dependent enough (point-estimate gap ranges from +0.21
to +0.40) that statistical significance under the strict pre-registered
rule is itself seed-dependent (2/4 seeds), and the encoder's advantage
specifically over `shallow_plus_structural` (rather than plain
`shallow`) is directional-only at every seed, never CI-decisive. A
mechanism-contingency read: the qualitative finding survives seed
resampling; the "beats shallow with a non-overlapping CI" headline number
specifically was somewhat fortunate at seed 0 (tied for the best of the 4
seeds' gaps, alongside seed 3).

## Part 2: Error-set digestion

Reconstructed the EXACT seed-0 probe split
`results/d1v2/v2run/interrogation.json` used (via
`tools/d1v2_interrogate.py`'s own `load_ring_split`, `results_dir=results/
d1v2/v2run`), retrained the `control_encoder_summary` and
`shallow_plus_structural` probes with the same seed/hyperparameters used
there (torch is deterministic given a fixed seed for these full-batch
Adam runs), and confirmed the reproduction is exact: boundary_acc
0.9047619104385376 / 0.761904776096344, matching the recorded JSON to
full float precision. Then partitioned the 21 boundary probe-test
examples by the two probes' per-example correctness.

Script: `results/d1v2/digestion/find_error_set.py`. Outputs:
`results/d1v2/digestion/cases.md` (readable case dumps + feature table),
`error_set.json` (idents + feature means), `error_set_full.json` (the
complete raw records, including full per-round `set_trace`, for every
config dumped in `cases.md`).

### Confusion breakdown (n=21 boundary probe-test examples)

| group | n | idents |
|---|---|---|
| `encoder_right_struct_wrong` (target set) | 4 | gen-r10-n18-res125-21693, gen-r10-n18-res62-30377, gen-r10-n18-res161-25540, gen-r10-n18-res125-21698 |
| `struct_right_encoder_wrong` | 1 | gen-r10-n17-527317 |
| `both_right` | 15 | (see `cases.md`) |
| `both_wrong` | 1 | gen-r10-n16-29491 |

4 configs land in the target set (`encoder_right_struct_wrong`) -- "a
handful" as expected. Full data (ident, n, adjacency, degree sequence,
n_extendable, n_consistent, rounds, survivor-count trace shape, and a
pointer to the full raw `set_trace`) for all 4, plus 3 `both_right` and
the single available `both_wrong` case for contrast (there is only 1
`both_wrong` example in this probe-test split, not 2-3 -- reported
honestly rather than padded), are in `results/d1v2/digestion/cases.md`.

Notable structural fact visible directly in the dumps (not a computed
statistic, just an observation of the raw data): all 4
`encoder_right_struct_wrong` configs have `n=18` (the largest ring-10
config size in this corpus) and `source=plantri_new`; all 4 are
`d_reducible=True` with `rounds` in {6, 6, 7, 6}.

### Feature means: encoder_right_struct_wrong vs rest of boundary

`rest-of-val-boundary` = the other 112 of the 116 val-boundary configs (excludes
the 4-config target set). `rest-of-full-corpus-boundary` = the other 772 of
all 776 boundary configs in `data/v2/traces_r10.jsonl` (same exclusion, larger
population for more stable means).

| feature | encoder_right_struct_wrong (n=4) | rest-of-val-boundary (n=112) | rest-of-full-corpus-boundary (n=772) |
|---|---|---|---|
| `n_deg5_interior` | 6.2500 | 4.8214 | 4.9534 |
| `n_deg5_total` | 8.7500 | 6.2500 | 6.3938 |
| `max_run_deg5_ring` | 1.2500 | 0.8929 | 0.9184 |
| `max_run_const_degree_ring` | 2.5000 | 2.3393 | 2.3044 |
| `n_triangles_deg5` | 4.0000 | 1.6607 | 1.8199 |
| `n_diamonds_deg5` | 2.7500 | 0.8750 | 0.9663 |
| `n_extendable` | 617.0000 | 632.5625 | 630.0518 |
| `n_extendable_ratio` | 0.0313 | 0.0321 | 0.0320 |
| `rounds` | 6.2500 | 6.7143 | 6.7008 |
| `monotonic_nonincreasing_frac` | 1.0000 | 1.0000 | 1.0000 |
| `first_round_drop_ratio` | 0.8449 | 0.8434 | 0.8437 |
| `final_survivors` | 0.0000 | 0.0000 | 0.0000 |

(`n_consistent` omitted -- tautological with `d_reducible`, per
`tools/d1_interrogate.py`'s `TAUTOLOGICAL_CANDIDATES` / `tools/
d1v2_interrogate.py`'s `STRUCTURAL_CANDIDATE_NAMES`.)

The largest relative gaps between the 4-config target set and the rest of
boundary are in the degree-5-cluster counts: `n_deg5_total` (8.75 vs
~6.3-6.4), `n_triangles_deg5` (4.0 vs ~1.7-1.8), and especially
`n_diamonds_deg5` (2.75 vs ~0.88-0.97, roughly 3x the rest-of-boundary
mean). `n_extendable`, `n_extendable_ratio`, `rounds`,
`first_round_drop_ratio`, and `final_survivors` are all close to the
rest-of-boundary means. `monotonic_nonincreasing_frac` is 1.0 in every
group (survivor counts never increase round-to-round for ANY boundary
config in this corpus, target set or not).

n=4 is far too small to draw any statistical conclusion from these gaps
(no significance test is reported here, deliberately -- this is evidence
collection, not a claim). The full per-config data is in `cases.md` /
`error_set_full.json` for direct human (or Claude-at-the-membrane)
inspection.

## Files

- `results/d1v2/replication/collect_seed_replication.py` -- seed
  replication driver (trains missing seeds, reprobes, writes JSON +
  summary table).
- `results/d1v2/replication/seed_replication.json`,
  `seed_replication_summary.txt`, `train_seed{1,2,3}.log` -- raw outputs.
- `results/d1v2/r10s{1,2,3}/` -- new control-model checkpoints +
  `control_metrics.json` + `summary.json` for seeds 1-3.
- `results/d1v2/digestion/find_error_set.py` -- error-set digestion
  driver.
- `results/d1v2/digestion/cases.md` -- readable case dumps + feature
  table (the human-facing deliverable for part 2).
- `results/d1v2/digestion/error_set.json`,
  `error_set_full.json` -- raw idents/feature-means and full per-config
  records (including complete `set_trace`) for reproducibility.

No files under `src/` were touched, so no test changes were needed; both
new scripts live under `results/d1v2/` as one-off analysis drivers (per
the task's own framing: "a small script ... is fine"), not reusable
library code.
