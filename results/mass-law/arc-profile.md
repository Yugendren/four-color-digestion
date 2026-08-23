# BFS-LINK ORDERING scheme: arc-profile evaluation

Corpus: 59142 records processed. Scheme succeeded (all verification steps passed) on 59141; 1 hit a scheme-integrity failure (see the note below); 0 had no adjacency.

## LEAD: scheme status

**1 record(s) failed a scheme verification step** (H disconnected / a link was not a single cycle / C did not cover all vertices / etc.) -- these are reported, not patched. Breakdown of failure kinds:
  - link(9): 1

First failure examples (up to 50 collected):
  - `gen-r8-n18-res74-522145`: link(9): vertex 4 has 3 neighbours within N(9) (expected 2)

## A. a > BOUND count (scheme validity)

Records with a > BOUND: **0** (must be 0 for the scheme to be valid).

None. (a <= bound holds on all successfully-processed records.)

## B. Arc-length histogram

Over the whole corpus (t -> count):

| t | count |
|---|---|
| 1 | 119705 |
| 2 | 162448 |
| 3 | 57974 |
| 4 | 11032 |
| 5 | 467 |
| 6 | 3 |

Per k (rows = t, columns = k):

| t | k=2 | k=3 | k=4 | k=5 | k=6 | k=7 | k=8 | k=9 | k=10 | k=11 | k=12 | k=13 | k=14 | k=15 | k=16 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0 | 8 | 251 | 2208 | 14342 | 47513 | 12296 | 12076 | 10758 | 10305 | 6670 | 2458 | 667 | 144 | 9 |
| 2 | 8 | 129 | 1026 | 6479 | 30413 | 81888 | 11133 | 9330 | 8436 | 7679 | 4314 | 1303 | 256 | 52 | 2 |
| 3 | 6 | 84 | 626 | 3182 | 12357 | 30965 | 2112 | 2101 | 2403 | 2323 | 1308 | 376 | 101 | 28 | 2 |
| 4 | 4 | 37 | 189 | 614 | 1808 | 4610 | 85 | 282 | 748 | 1152 | 927 | 411 | 138 | 26 | 1 |
| 5 | 2 | 4 | 8 | 26 | 70 | 191 | 3 | 1 | 18 | 49 | 57 | 31 | 6 | 1 | 0 |
| 6 | 0 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## C. gamma_prov (provable gamma)

Max gamma_prov over the corpus: **1.937082** (ident `gen-r8-n18-res61-403328`).

Interpretation: gamma_prov < 2 means the scheme provably beats the current cap 2^(r+k-3); gamma_prov < 1.5 would mean it provably beats 3/2.

Max gamma_prov per (r,k), r=8..16, k=2..8 (blank = no corpus record in that cell):

| r\k | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|
| 8 | 1.5000 | 1.7321 | 1.8171 | 1.8612 | 1.8882 | 1.9064 | 1.9195 |
| 9 | 1.5000 | 1.7321 | 1.8171 | 1.8612 | 1.8882 | 1.9064 | 1.9195 |
| 10 | 1.5000 | 1.7321 | 1.8171 | 1.8612 | 1.8882 | 1.9064 | 1.9195 |
| 11 | 1.5000 | 1.7321 | 1.8171 | 1.8612 | 1.8882 | 1.8171 | 1.9195 |
| 12 | 1.5000 | 1.7321 | 1.8171 | 1.8612 | 1.8882 | 1.7321 | 1.8958 |
| 13 | 1.5000 | 1.7321 | 1.8171 | 1.8612 | 1.8882 | 1.9064 | 1.7680 |
| 14 |  |  |  |  |  |  | 1.6968 |
| 15 |  |  |  |  |  |  |  |
| 16 |  |  |  |  |  |  |  |

## D. |link(h) XOR link(h')| for adjacent interior pairs

Distribution over the whole corpus (value -> count of H-edges with that symmetric-difference size):

| |link^link| | count |
|---|---|
| 6 | 144794 |
| 7 | 168634 |
| 8 | 141632 |
| 9 | 88569 |
| 10 | 45082 |
| 11 | 17267 |
| 12 | 4228 |
| 13 | 573 |
| 14 | 46 |

**610825 H-edge(s) have |link^link| != 2** -- this is the fact that is supposed to guarantee arcs of length >= 2 at the second interior vertex; it does NOT hold universally. Up to 200 examples collected, listing up to 40 here:

| ident | h | h' | xor |
|---|---|---|---|
| 0.7322 | 7 | 8 | 6 |
| 0.7322 | 7 | 9 | 6 |
| 0.7322 | 7 | 10 | 6 |
| 0.7322 | 8 | 9 | 6 |
| 0.7322 | 9 | 10 | 6 |
| 2.122 | 8 | 9 | 7 |
| 2.122 | 8 | 10 | 7 |
| 2.122 | 8 | 11 | 7 |
| 2.122 | 9 | 10 | 6 |
| 2.122 | 10 | 11 | 6 |
| 3.442802 | 9 | 10 | 7 |
| 3.442802 | 9 | 11 | 7 |
| 3.442802 | 9 | 12 | 7 |
| 3.442802 | 9 | 13 | 7 |
| 3.442802 | 10 | 11 | 6 |
| 3.442802 | 10 | 14 | 6 |
| 3.442802 | 11 | 14 | 6 |
| 3.442802 | 12 | 13 | 6 |
| 3.442802 | 12 | 15 | 6 |
| 3.442802 | 13 | 15 | 6 |
| 2.126 | 9 | 10 | 7 |
| 2.126 | 9 | 11 | 8 |
| 2.126 | 9 | 12 | 7 |
| 2.126 | 10 | 11 | 7 |
| 2.126 | 11 | 12 | 7 |
| 0.453962 | 9 | 10 | 6 |
| 0.453962 | 9 | 11 | 7 |
| 0.453962 | 9 | 12 | 7 |
| 0.453962 | 9 | 13 | 6 |
| 0.453962 | 10 | 11 | 7 |
| 0.453962 | 11 | 12 | 8 |
| 0.453962 | 12 | 13 | 7 |
| 3.1306802 | 10 | 11 | 7 |
| 3.1306802 | 10 | 12 | 7 |
| 3.1306802 | 10 | 13 | 7 |
| 3.1306802 | 10 | 14 | 8 |
| 3.1306802 | 11 | 12 | 6 |
| 3.1306802 | 11 | 15 | 6 |
| 3.1306802 | 12 | 15 | 6 |
| 3.1306802 | 13 | 14 | 7 |

## E. Zero-gain BFS steps (j >= 2)

For each j >= 2, the step 'contributes zero arcs' if its entire link was already coloured (link subset of C), and 'contributes only length-1 arcs' if every arc it produced has t=1. These are exactly the steps where the scheme gains nothing beyond a factor of 2.

| k | total steps | zero-arc steps | frac | only-len-1 steps | frac |
|---|---|---|---|---|---|
| 2 | 20 | 0 | 0.0000 | 0 | 0.0000 |
| 3 | 262 | 0 | 0.0000 | 8 | 0.0305 |
| 4 | 2106 | 6 | 0.0028 | 251 | 0.1192 |
| 5 | 12636 | 127 | 0.0101 | 2208 | 0.1747 |
| 6 | 60340 | 1350 | 0.0224 | 14342 | 0.2377 |
| 7 | 171534 | 6364 | 0.0371 | 47513 | 0.2770 |
| 8 | 28945 | 3316 | 0.1146 | 12296 | 0.4248 |
| 9 | 27760 | 3970 | 0.1430 | 12076 | 0.4350 |
| 10 | 24615 | 2252 | 0.0915 | 10758 | 0.4371 |
| 11 | 22800 | 1292 | 0.0567 | 10305 | 0.4520 |
| 12 | 14355 | 1079 | 0.0752 | 6670 | 0.4646 |
| 13 | 5040 | 461 | 0.0915 | 2458 | 0.4877 |
| 14 | 1300 | 132 | 0.1015 | 667 | 0.5131 |
| 15 | 280 | 29 | 0.1036 | 144 | 0.5143 |
| 16 | 15 | 1 | 0.0667 | 9 | 0.6000 |
| all | 372008 | 20379 | 0.0548 | 119705 | 0.3218 |

## F. BOUND vs empirical sharp cap

Max over the cell of BOUND / sharp_cap, sharp_cap = (2^r+2)/6 * (4/3)^(k-1), for r=8..16, k=1..8 (blank = no corpus record in that cell). Larger = the provable bound is looser relative to the empirical sharp cap.

| r\k | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| 8 | 1.0000 | 1.1512 | 1.6483 | 2.4724 | 3.7086 | 5.6953 | 8.7416 | 12.8145 |
| 9 | 0.9922 | 1.1294 | 1.6941 | 2.5411 | 3.8116 | 5.7175 | 8.5762 | 12.8643 |
| 10 | 1.0000 | 1.1316 | 1.6776 | 2.5461 | 3.8191 | 5.7286 | 8.5929 | 12.8894 |
| 11 | 0.9980 | 1.1261 | 1.6891 | 2.5337 | 3.8006 | 5.7009 | 6.4510 | 12.8270 |
| 12 | 1.0000 | 1.1266 | 1.6850 | 2.5350 | 3.8024 | 5.7037 | 4.8406 | 11.6950 |
| 13 | 0.9995 | 1.1253 | 1.6879 | 2.5319 | 3.7978 | 5.6967 | 8.5451 | 7.2627 |
| 14 |  |  |  |  |  |  |  | 5.3843 |
| 15 |  |  |  |  |  |  |  |  |
| 16 |  |  |  |  |  |  |  |  |

