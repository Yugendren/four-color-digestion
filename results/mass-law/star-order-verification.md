# STAR-ORDER computational verification

Verification of the combinatorial fact (STAR-ORDER) underlying the STAR-FIRST ORDERING LEMMA, run against the full 59,142-record corpus (`fourcolor.lemma_corpus.load_corpus()`). Script: `tools/star_order_check.py`, total runtime 14.5s.

## Part 1 -- structural census

- Global interior-degree range across all 59142 records: **[5, 13]**.

Interior-degree distribution (degree -> count of interior vertices at that degree):

| degree | count |
|---|---|
| 5 | 240084 |
| 6 | 113500 |
| 7 | 51653 |
| 8 | 18152 |
| 9 | 5853 |
| 10 | 1561 |
| 11 | 305 |
| 12 | 45 |
| 13 | 6 |

No interior vertex with degree < 5 found anywhere in the corpus: `min interior degree >= 5` HOLDS on the whole corpus (59,142 records, not a proof).

**1b (link(h) is a single cycle):** 1 violations.

- `gen-r8-n18-res74-522145` vertex 9: vertex 4 has within-set degree 3 (expected 2)

(Manually inspected the one offender, `gen-r8-n18-res74-522145`: vertex 9 has degree 11 and its link contains the extra edge 4-5, a chord splitting the wheel into two triangulated regions via the separating triangle 4-9-5 -- i.e. a genuine, planarity-legal configuration where two non-cyclically-adjacent neighbours of h are also directly joined through the rest of the graph. This does not threaten the STAR-FIRST bound: an extra edge among link(h) vertices only removes colourings relative to the pure wheel C_d, so P(C_d,3) remains a valid, if slightly loose, upper bound for that record's star subgraph. It does mean `link(h) is an induced pure cycle with no chords` is not quite a universal invariant -- 1 exception in 431,159 (record,h) pairs.)

**1c (interior induced subgraph connected):** 0 violations.

**1d (ring is an induced cycle):** 0 violations.

**1e (Euler, #edges == 3n-r-3):** 0 violations.

## Part 2 -- STAR-ORDER verification (load-bearing)

Tested **431159** (record, interior vertex) pairs across all 59142 records. Method: monotone closure -- starting from S0 = {h} u link(h), repeatedly add any vertex with an edge fully inside its own neighbourhood-intersect-S (equivalent, by confluence of the monotone bootstrap rule, to checking whether *some* sequential order exists).

**Result: PASS. 0 failures out of 431159 pairs.** STAR-ORDER holds on the entire corpus with no counterexample.

## Part 3 -- numeric consequence

`B_star(rec) = min over interior h of (2^d + 2*(-1)^d) * 2^(n-d-1) / 6`, the Bridge-Lemma-derived cap implied by choosing the max/best interior vertex per record.

**a <= B_star holds on all 59142 records (0 violations).**

- max(a / B_star) = **1.000000** at `fr-r10-n11-0`
- max(a / (11*2^(n-7))) [uniform version] = **0.977273** at `fr-r8-n9-0`

Per-(r,k) table of max(a/B_star), r=8..16, k=1..6 (blank = no records in that cell):

| r | k=1 | k=2 | k=3 | k=4 | k=5 | k=6 |
|---|---|---|---|---|---|---|
| r=8 | 1.0000 | 0.6625 | 0.4188 | 0.2562 | 0.1562 | 0.0938 |
| r=9 | 1.0000 | 0.6625 | 0.4250 | 0.2687 | 0.1648 | 0.1004 |
| r=10 | 1.0000 | 0.6656 | 0.4297 | 0.2750 | 0.1711 | 0.1051 |
| r=11 | 1.0000 | 0.6656 | 0.4344 | 0.2785 | 0.1771 | 0.1102 |
| r=12 | 1.0000 | 0.6664 | 0.4387 | 0.2832 | 0.1812 | 0.1142 |
| r=13 | 1.0000 | 0.6664 | 0.4398 | 0.2863 | 0.1832 | 0.1171 |
| r=14 | -- | -- | -- | -- | -- | -- |
| r=15 | -- | -- | -- | -- | -- | -- |
| r=16 | -- | -- | -- | -- | -- | -- |

## Part 4 -- per-step gain profile (stratified sample)

Sample: 1315 records, every (r,k) cell present in the corpus, cap 20 per cell (seed 20260823).

**Identity check `sum_i (b_i-2), i>=4 == k`:** 0 violations out of 1315.

Histogram of step factor f_i by b_i (# already-placed neighbours):

| b_i | mean f_i | min f_i | max f_i | n steps |
|---|---|---|---|---|
| 2 | 2.0000 | 2.0000 | 2.0000 | 14886 |
| 3 | 1.3155 | 1.1754 | 1.6479 | 6322 |
| 4 | 0.8583 | 0.7273 | 1.0933 | 1165 |
| 5+ | 0.5138 | 0.2148 | 0.6576 | 565 |

b_i==3 steps specifically (empirical `1 + Pr[phi(u)=phi(w)]`): mean f_i = **1.315482**, max f_i = **1.647887**, n=6322.

Implied gamma = 2*(GAINPROD)^(1/k) distribution over the sample: mean=1.394898, min=1.329484, **max=2.015625** at `fr-r8-n9-0` (r=8, k=1).

Per-k table of max implied gamma:

| k | max implied gamma | argmax ident |
|---|---|---|
| 1 | 2.015625 | `fr-r8-n9-0` |
| 2 | 1.690969 | `gen-r8-n10-2` |
| 3 | 1.585331 | `gen-r9-n12-25` |
| 4 | 1.536817 | `gen-r10-n14-359` |
| 5 | 1.486927 | `fr-r13-n18-17117` |
| 6 | 1.435921 | `gen-r9-n15-27489` |
| 7 | 1.438189 | `2.79077966` |
| 8 | 1.416296 | `D3009` |
| 9 | 1.419752 | `gen-r8-n17-11050093` |
| 10 | 1.398275 | `D3077` |
| 11 | 1.384680 | `D3804` |
| 12 | 1.386793 | `D7511` |
| 13 | 1.377598 | `D5458` |
| 14 | 1.375941 | `D5460` |
| 15 | 1.353492 | `D5007` |
| 16 | 1.329915 | `D6936` |

Interpretation: max implied gamma > 4/3: the 4/3 cap CANNOT come from any per-step argument on P.

