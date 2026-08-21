# Theorem-candidate sufficient conditions for D-reducibility

Mined from a pool of 16794 distinct configurations (deduped by `fourcolor.canonical.canonical_key` from 27283 raw records across 15 source files: `data/d1_corpus.jsonl`, `data/v2/traces_r{8,9,10}.jsonl`, `data/configs_r*.jsonl`; 0 label conflicts found at matching canonical keys), rings 6-16, 11919 D-reducible / 4875 not, via `tools/mine_sound_rules.py`. See `results/theorem/mining_results.json` for the full ranked lists (top-20 reducible-sufficient / top-10 non-reducibility-sufficient rules, both the `structural` and `full` feature variants, 5-fold cross-validation, and the nl4ct_pool honesty check).

**Design decision -- `structural` vs `full` feature variant**: the task's feature pool includes `n_extendable`/`n_extendable_ratio` (`fourcolor.d1_interp.STRUCTURAL_CANDIDATE_NAMES`, used verbatim from `tools/d1v2_interrogate.py`, minus only the tautological `n_consistent`). `n_extendable` is not tautological with the label the way `n_consistent` is, but it IS the output of running most of `fourcolor.reduce`'s own ring-coloring-extension search on the configuration -- a 'sufficient condition' phrased in terms of it is not checkable by graph inspection alone, so it does not read as a genuine theorem candidate. Both variants are mined (see the JSON for `full`); this write-up's top-3 use the **`structural`** variant only (`n_extendable`/`n_extendable_ratio` excluded -- every predicate below is a pure function of the configuration's ring size and adjacency structure).

## Pool composition caveat -- read this before the numbers below

Ring coverage in this pool is NOT uniform between 'exhaustively searched, adversarial' and 'curated, already-known-reducible': rings 8-11 have deep negative-example coverage (plantri-exhaustive generation over both boundary colorings and full configuration search -- see `data/configs_r*.jsonl` / `data/v2/traces_r{8,9,10}.jsonl`), but rings 12-16 are almost entirely the historical CURATED sets (rsst633/steinberger2822/nl4ct_pool -- actual configurations from the published discharging rules, i.e. PRE-SELECTED to be reducible). Rings 15-16 have **zero** non-reducible examples anywhere in the pool. A rule that is zero-FP against the *whole pool* is an honest claim against the data actually assembled, but at rings >= 12 that claim has had essentially no chance to be falsified (there was no adversarial search there to generate a counterexample), so read the top-3 below (which, as their per-ring tables show, cover almost exclusively rings 13-16) with that in mind. See 'Dense-ring supplementary candidates' further down for rules validated specifically against the rings that DO have deep adversarial negative search coverage.

| ring | total | D-reducible | not D-reducible | frac reducible |
|---|---|---|---|---|
| 6 | 30 | 28 | 2 | 0.933 |
| 7 | 43 | 37 | 6 | 0.860 |
| 8 | 1432 | 1219 | 213 | 0.851 |
| 9 | 2411 | 1738 | 673 | 0.721 |
| 10 | 3269 | 1287 | 1982 | 0.394 |
| 11 | 1873 | 209 | 1664 | 0.112 |
| 12 | 849 | 767 | 82 | 0.903 |
| 13 | 2103 | 1961 | 142 | 0.932 |
| 14 | 2765 | 2654 | 111 | 0.960 |
| 15 | 1562 | 1562 | 0 | 1.000 |
| 16 | 457 | 457 | 0 | 1.000 |

## Candidate 1: `n >= 25 AND mean_interior_degree >= 5.733333333333333 AND h5_density <= 0.2857142857142857`

**Statement.** Let K be a configuration (ring size r, n total vertices, degree-5 interior subgraph H5 as defined in `fourcolor.d1_features`) satisfying n >= 25 AND mean_interior_degree >= 5.733333333333333 AND h5_density <= 0.2857142857142857. Then, on the 16794-configuration pool tested (rings 6-16), K is always D-reducible (2313 configurations satisfy this condition; 0 counterexamples).

- **Coverage**: 2313 D-reducible configs overall (of 11919 total D-reducible in the pool).
- **Per-ring coverage** (covered / total-D-reducible-in-that-ring): r=6: 0/28; r=7: 0/37; r=8: 0/1219; r=9: 0/1738; r=10: 0/1287; r=11: 0/209; r=12: 0/767; r=13: 28/1961; r=14: 726/2654; r=15: 1155/1562; r=16: 404/457
- **5-fold CV discoverability**: mining independently on each fold's 4/5 training subset (blind to the held-out 1/5), this exact rule's rank among that fold's own zero-FP minimal reducible-sufficient rules (by training coverage): fold 0: rank #1, fold 1: rank #1, fold 2: subsumed by `n >= 25 AND mean_interior_degree >= 5.733333333333333`, fold 3: rank #38, fold 4: rank #1.
- **Witness configs nearest the boundary** (satisfying the rule with the smallest per-atom slack -- where a proof attempt should focus, and where new data is most likely to break the rule):
  - `1328.1032` (source=rsst633, r=14, n=25, margin=0): n=25, mean_interior_degree=5.81818, h5_density=0.2
  - `2445` (source=steinberger2822, r=14, n=25, margin=0): n=25, mean_interior_degree=5.81818, h5_density=0.266667
  - `2446` (source=steinberger2822, r=14, n=25, margin=0): n=25, mean_interior_degree=5.81818, h5_density=0.266667
  - `2447` (source=steinberger2822, r=14, n=25, margin=0): n=25, mean_interior_degree=5.81818, h5_density=0.266667
  - `2449` (source=steinberger2822, r=14, n=25, margin=0): n=25, mean_interior_degree=5.81818, h5_density=0.2

## Candidate 2: `n >= 25 AND max_run_const_degree_ring <= 4 AND n_deg5_ge3_deg5_neighbors == 0`

**Statement.** Let K be a configuration (ring size r, n total vertices, degree-5 interior subgraph H5 as defined in `fourcolor.d1_features`) satisfying n >= 25 AND max_run_const_degree_ring <= 4 AND n_deg5_ge3_deg5_neighbors == 0. Then, on the 16794-configuration pool tested (rings 6-16), K is always D-reducible (2240 configurations satisfy this condition; 0 counterexamples).

- **Coverage**: 2240 D-reducible configs overall (of 11919 total D-reducible in the pool).
- **Per-ring coverage** (covered / total-D-reducible-in-that-ring): r=6: 0/28; r=7: 0/37; r=8: 0/1219; r=9: 0/1738; r=10: 0/1287; r=11: 0/209; r=12: 0/767; r=13: 6/1961; r=14: 806/2654; r=15: 1067/1562; r=16: 361/457
- **5-fold CV discoverability**: mining independently on each fold's 4/5 training subset (blind to the held-out 1/5), this exact rule's rank among that fold's own zero-FP minimal reducible-sufficient rules (by training coverage): fold 0: rank #2, fold 1: rank #2, fold 2: subsumed by `n >= 25 AND n_deg5_ge3_deg5_neighbors == 0`, fold 3: rank #47, fold 4: rank #7.
- **Witness configs nearest the boundary** (satisfying the rule with the smallest per-atom slack -- where a proof attempt should focus, and where new data is most likely to break the rule):
  - `186.1379460` (source=rsst633, r=14, n=25, margin=0): n=25, max_run_const_degree_ring=4, n_deg5_ge3_deg5_neighbors=0
  - `D4937` (source=nl4ct_pool, r=16, n=28, margin=0): n=28, max_run_const_degree_ring=2, n_deg5_ge3_deg5_neighbors=0
  - `D4936` (source=nl4ct_pool, r=16, n=28, margin=0): n=28, max_run_const_degree_ring=3, n_deg5_ge3_deg5_neighbors=0
  - `D4927` (source=nl4ct_pool, r=16, n=27, margin=0): n=27, max_run_const_degree_ring=3, n_deg5_ge3_deg5_neighbors=0
  - `D4926` (source=nl4ct_pool, r=16, n=27, margin=0): n=27, max_run_const_degree_ring=1, n_deg5_ge3_deg5_neighbors=0

## Candidate 3: `n_interior >= 11 AND h5_density <= 0.2857142857142857 AND n_deg5_ge3_deg5_neighbors == 0`

**Statement.** Let K be a configuration (ring size r, n total vertices, degree-5 interior subgraph H5 as defined in `fourcolor.d1_features`) satisfying n_interior >= 11 AND h5_density <= 0.2857142857142857 AND n_deg5_ge3_deg5_neighbors == 0. Then, on the 16794-configuration pool tested (rings 6-16), K is always D-reducible (2234 configurations satisfy this condition; 0 counterexamples).

- **Coverage**: 2234 D-reducible configs overall (of 11919 total D-reducible in the pool).
- **Per-ring coverage** (covered / total-D-reducible-in-that-ring): r=6: 0/28; r=7: 0/37; r=8: 0/1219; r=9: 0/1738; r=10: 0/1287; r=11: 0/209; r=12: 2/767; r=13: 123/1961; r=14: 821/2654; r=15: 937/1562; r=16: 351/457
- **5-fold CV discoverability**: mining independently on each fold's 4/5 training subset (blind to the held-out 1/5), this exact rule's rank among that fold's own zero-FP minimal reducible-sufficient rules (by training coverage): fold 0: rank #12, fold 1: rank #4, fold 2: subsumed by `n_interior >= 11 AND n_deg5_ge3_deg5_neighbors == 0`, fold 3: rank #43, fold 4: rank #4.
- **Witness configs nearest the boundary** (satisfying the rule with the smallest per-atom slack -- where a proof attempt should focus, and where new data is most likely to break the rule):
  - `1328.1032` (source=rsst633, r=14, n=25, margin=0): n_interior=11, h5_density=0.2, n_deg5_ge3_deg5_neighbors=0
  - `D4098` (source=nl4ct_pool, r=14, n=25, margin=0): n_interior=11, h5_density=0.133333, n_deg5_ge3_deg5_neighbors=0
  - `D4084` (source=nl4ct_pool, r=14, n=25, margin=0): n_interior=11, h5_density=0.0666667, n_deg5_ge3_deg5_neighbors=0
  - `D3943` (source=nl4ct_pool, r=14, n=25, margin=0): n_interior=11, h5_density=0.142857, n_deg5_ge3_deg5_neighbors=0
  - `D3937` (source=nl4ct_pool, r=14, n=25, margin=0): n_interior=11, h5_density=0.142857, n_deg5_ge3_deg5_neighbors=0

## Dense-ring supplementary candidates (r in {8,9,10,11}, the adversarially-searched rings)

Mined with scoring restricted to the 8985 configs at rings 8-11 (4453 D-reducible / 4532 not -- the subset with real exhaustive negative-example coverage, per the caveat above), then each surviving rule is evaluated against the FULL pool for honesty (not guaranteed to stay zero-FP outside its mining subset). These are weaker in headline coverage than the top-3 above but rest on much more adversarially-tested ground.

| rule | dense-subset coverage/FP | full-pool coverage/FP | per-ring (full pool) |
|---|---|---|---|
| `n_interior >= 9 AND max_run_const_degree_ring <= 2 AND h5_max_degree <= 3` | 743/0 | 4198/89 | r=6: 0/28; r=7: 0/37; r=8: 340/1219; r=9: 365/1738; r=10: 1/1287; r=11: 37/209; r=12: 331/767; r=13: 931/1961; r=14: 1197/2654; r=15: 759/1562; r=16: 237/457 |
| `n_interior == 9 AND max_run_const_degree_ring <= 2 AND h5_max_degree <= 3` | 635/0 | 1154/70 | r=6: 0/28; r=7: 0/37; r=8: 235/1219; r=9: 365/1738; r=10: 1/1287; r=11: 34/209; r=12: 199/767; r=13: 298/1961; r=14: 22/2654; r=15: 0/1562; r=16: 0/457 |
| `n_interior >= 9 AND max_run_const_degree_ring == 2 AND h5_max_degree <= 3` | 620/0 | 3612/64 | r=6: 0/28; r=7: 0/37; r=8: 266/1219; r=9: 327/1738; r=10: 1/1287; r=11: 26/209; r=12: 277/767; r=13: 790/1961; r=14: 1049/2654; r=15: 680/1562; r=16: 196/457 |
| `n_interior >= 9 AND max_run_const_degree_ring <= 2 AND h5_max_degree == 3` | 593/0 | 855/2 | r=6: 0/28; r=7: 0/37; r=8: 303/1219; r=9: 278/1738; r=10: 0/1287; r=11: 12/209; r=12: 54/767; r=13: 102/1961; r=14: 82/2654; r=15: 22/1562; r=16: 2/457 |
| `n_interior >= 9 AND max_run_const_degree_ring == 2 AND h5_edge_count <= 7` | 589/0 | 3569/64 | r=6: 0/28; r=7: 0/37; r=8: 241/1219; r=9: 321/1738; r=10: 1/1287; r=11: 26/209; r=12: 275/767; r=13: 786/1961; r=14: 1044/2654; r=15: 679/1562; r=16: 196/457 |

## nl4ct_pool cross-check

All 4828 raw `nl4ct_pool` records (source=='nl4ct_pool' in `data/d1_corpus.jsonl`, loaded independently of the deduped pool above) are D-reducible by construction, so a reducible-sufficient rule firing there is only a coverage data point (cannot be a false positive); a non-reducibility-sufficient rule firing there WOULD be a hard false positive (falsifying that rule) -- checked explicitly, 0 found (see table below).

| rule | direction | hits on nl4ct_pool (n=4828) |
|---|---|---|
| `n >= 25 AND mean_interior_degree >= 5.733333333333333 AND h5_density <= 0.2857142857142857` | reducible-sufficient (coverage only) | 1704 |
| `n >= 25 AND max_run_const_degree_ring <= 4 AND n_deg5_ge3_deg5_neighbors == 0` | reducible-sufficient (coverage only) | 1603 |
| `n_interior >= 11 AND h5_density <= 0.2857142857142857 AND n_deg5_ge3_deg5_neighbors == 0` | reducible-sufficient (coverage only) | 1676 |
| `r == 11 AND n_interior <= 6` | non-reducibility-sufficient (FP if >0) | 0 |
| `n_interior <= 6 AND deg_3 >= 6` | non-reducibility-sufficient (FP if >0) | 0 |
| `n_interior <= 6 AND deg_3 >= 5 AND max_run_const_degree_ring >= 3` | non-reducibility-sufficient (FP if >0) | 0 |

## Bonus: strongest non-reducibility-sufficient dual rule

`r == 11 AND n_interior <= 6` -- 1630 non-reducible configs covered, 0 false positives (no D-reducible config in the pool satisfies it). Per-ring: r=6: 0/2; r=7: 0/6; r=8: 0/213; r=9: 0/673; r=10: 0/1982; r=11: 1630/1664; r=12: 0/82; r=13: 0/142; r=14: 0/111.

