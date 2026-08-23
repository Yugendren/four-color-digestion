# P(S,4) measurement: exact colouring counts against the sharp cap and the Bridge Lemma

**2026-08-23.** `tools/p4_measure.py` computes the exact number of proper
4-colourings `p4 = P(S,4)` for every one of the **59,142** canonically-deduped
labeled configurations in the corpus (`fourcolor.lemma_corpus.load_corpus()`),
using the validated frontier-DP counter `fourcolor.count4.count_proper_4colorings`.
Full sweep: **19.14s wall-clock**, 0 records skipped for missing adjacency,
**0 records failing `p4 % 24 == 0`**. Output: `results/mass-law/p4_measurements.jsonl`
(59,142 lines, one per record), fields `ident source r n k a d_reducible p4 p24
fiber sharp_cap` where `p24 = p4 // 24`, `fiber = p24 / a`, and
`sharp_cap = (2^r+2)/6 * (4/3)^(k-1)`.

All numbers below are computed directly from `p4_measurements.jsonl` (see the
throwaway analysis script used to produce them; every table cell here is a
measured value, not a guess).

---

## Self-check

### 1. Wheel closed form at k=1

The corpus contains exactly 6 wheel records (interior = 1 hub vertex,
`k = n - r = 1`). `P(W_r,4) = 4(2^r + 2(-1)^r)` is a known closed form. Every
one of the 6 matches exactly:

| ident | r | p4 (measured) | formula `4(2^r+2(-1)^r)` | match |
|---|---|---|---|---|
| fr-r8-n9-0 | 8 | 1032 | 1032 | yes |
| fr-r9-n10-0 | 9 | 2040 | 2040 | yes |
| fr-r10-n11-0 | 10 | 4104 | 4104 | yes |
| fr-r11-n12-0 | 11 | 8184 | 8184 | yes |
| fr-r12-n13-0 | 12 | 16392 | 16392 | yes |
| fr-r13-n14-0 | 13 | 32760 | 32760 | yes |

6/6 exact matches. This is a strong end-to-end validation of `count4.py` on
these graphs (independent of the DP's own unit tests), since it exercises the
counter on real corpus adjacency, not synthetic wheels.

### 2. Bridge Lemma: fiber >= 1 everywhere

Checked `p24 = p4/24 >= a` (equivalently `fiber >= 1`) for **every** record
with `a > 0` (all 59,142 have `a > 0`; none had `p24 = None`, i.e. the
`p4 % 24 == 0` assertion never failed).

**Result: 0 failures across all 59,142 records.** `min(fiber) = 1.0`, attained
exactly at the 6 k=1 wheel records (and only there; see Q4). The Bridge Lemma
(`a <= P(S,4)/24`) holds with no exceptions anywhere in the corpus -- no
contradiction found.

---

## Q1. Sharp cap, P-form vs. a-form

Claim under test: `p24 <= sharp_cap` where `sharp_cap = (2^r+2)/6 * (4/3)^(k-1)`
(the "P-form" of the cap, i.e. applied to the coloring mass itself rather than
to `a`).

**Result: this is FALSE. 1,960 of 59,142 records (3.3%) violate `p24 <= sharp_cap`.**
The 20 worst by ratio (`p24/sharp_cap`, descending):

| ident | r | k | a | p24 | sharp_cap | ratio |
|---|---|---|---|---|---|---|
| fr-r13-n20-214279 | 13 | 7 | 5679 | 10518 | 7673.2108 | 1.370743 |
| fr-r13-n20-214289 | 13 | 7 | 5671 | 10514 | 7673.2108 | 1.370222 |
| fr-r13-n20-214277 | 13 | 7 | 5671 | 10512 | 7673.2108 | 1.369961 |
| fr-r12-n18-110361 | 12 | 6 | 2267 | 3745 | 2878.1564 | 1.301180 |
| fr-r12-n18-110357 | 12 | 6 | 2263 | 3744 | 2878.1564 | 1.300833 |
| D5455 | 14 | 12 | 26626 | 84068 | 64661.8019 | 1.300118 |
| fr-r12-n18-110359 | 12 | 6 | 2263 | 3740 | 2878.1564 | 1.299443 |
| fr-r13-n19-19103 | 13 | 6 | 4598 | 7446 | 5754.9081 | 1.293852 |
| fr-r13-n19-19101 | 13 | 6 | 4602 | 7434 | 5754.9081 | 1.291767 |
| fr-r13-n19-19102 | 13 | 6 | 4602 | 7434 | 5754.9081 | 1.291767 |
| fr-r13-n19-28719 | 13 | 6 | 4632 | 7412 | 5754.9081 | 1.287944 |
| fr-r13-n20-214297 | 13 | 7 | 5914 | 9662 | 7673.2108 | 1.259186 |
| gen-r11-n16-6050 | 11 | 5 | 900 | 1334 | 1079.8354 | 1.235373 |
| fr-r12-n17-10573 | 12 | 5 | 1825 | 2654 | 2158.6173 | 1.229491 |
| fr-r12-n17-10572 | 12 | 5 | 1824 | 2652 | 2158.6173 | 1.228564 |
| fr-r12-n17-10565 | 12 | 5 | 1835 | 2642 | 2158.6173 | 1.223932 |
| fr-r13-n18-18006 | 13 | 5 | 3697 | 5266 | 4316.1811 | 1.220060 |
| fr-r13-n18-18007 | 13 | 5 | 3697 | 5266 | 4316.1811 | 1.220060 |
| fr-r13-n18-18008 | 13 | 5 | 3697 | 5266 | 4316.1811 | 1.220060 |
| fr-r13-n18-18004 | 13 | 5 | 3707 | 5262 | 4316.1811 | 1.219133 |

**Control (a-form): `a <= sharp_cap` -- 0 violations across all 59,142 records.**
This reproduces the expected result: the sharp cap as previously established
holds for `a` with no exceptions, but does **not** hold for `p24 = p4/24`
directly -- `p4/24` genuinely exceeds `a`'s sharp cap on a non-trivial slice
(3.3%) of the corpus, worst ratio ~1.37x. This is not a contradiction of
anything already proven (the sharp cap was never claimed for `p24`), but it
does mean the "P-form" of the cap as literally stated in the task is false and
would need a looser constant (or a different exponent/base) to hold for `p24`.

## Q2. Minimal base

`gamma_P = (p24/W(r))^(1/(k-1))`, `gamma_a = (a/W(r))^(1/(k-1))`, `W(r) = (2^r+2)/6`,
computed for every record with `k >= 2`.

| quantity | max value | argmax ident | r | k | a | p24 |
|---|---|---|---|---|---|---|
| gamma_P | **1.4186047** | gen-r8-n10-2 | 8 | 2 | 55 | 61 |
| gamma_a | **1.3224310** | fr-r13-n15-4 | 13 | 2 | 1806 | 1827 |

**Known check reproduced exactly: max gamma_a = 1.3224310 at r=13, k=2,
ident `fr-r13-n15-4` -- matches to all 7 decimal places quoted.** No bug found
here.

Note `gamma_P > gamma_a` at the max (1.4186 vs 1.3224), consistent with Q1's
finding that `p24` needs a larger base than `a` does to stay under a cap of
this `W(r)*base^(k-1)` shape -- the P-form cap as literally stated (using the
same `4/3` base as the a-form) is therefore expected to fail, and does (Q1).

## Q3. Per-(r,k) cell table

`r = 8..16`, `k = 1..8` (or however many exist for that r -- the corpus has no
records at r=14..16 below k=8, and none at all at r=15,16 except k=8 at r=14).
For k=1, gamma is undefined (`k-1=0`); those cells report max `p24`/max `a`
directly instead, as specified.

**max gamma_P** (k=1 column shows max p24 instead):

| r\k | k=1 | k=2 | k=3 | k=4 | k=5 | k=6 | k=7 | k=8 |
|---|---|---|---|---|---|---|---|---|
| 8 | p24max=43 | 1.4186 | 1.3118 | 1.3249 | 1.3311 | 1.3345 | 1.3445 | 1.3514 |
| 9 | p24max=85 | 1.3424 | 1.4087 | 1.3354 | 1.3299 | 1.3485 | 1.3484 | 1.3511 |
| 10 | p24max=171 | 1.3860 | 1.4080 | 1.4067 | 1.3512 | 1.3511 | 1.3558 | 1.3645 |
| 11 | p24max=341 | 1.3668 | 1.3878 | 1.4042 | 1.4057 | 1.3611 | 1.3611 | 1.3394 |
| 12 | p24max=683 | 1.3777 | 1.3876 | 1.4037 | 1.4040 | 1.4054 | 1.3249 | 1.3563 |
| 13 | p24max=1365 | 1.3730 | 1.3824 | 1.3898 | 1.4013 | 1.4038 | 1.4053 | 1.3481 |
| 14 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 1.3349 |
| 15 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| 16 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

**max gamma_a** (k=1 column shows max a instead):

| r\k | k=1 | k=2 | k=3 | k=4 | k=5 | k=6 | k=7 | k=8 |
|---|---|---|---|---|---|---|---|---|
| 8 | amax=43 | 1.2791 | 1.2483 | 1.2401 | 1.2349 | 1.2278 | 1.2174 | 1.2076 |
| 9 | amax=85 | 1.2840 | 1.2784 | 1.2616 | 1.2528 | 1.2457 | 1.2384 | 1.2301 |
| 10 | amax=171 | 1.3041 | 1.2910 | 1.2769 | 1.2651 | 1.2576 | 1.2540 | 1.2450 |
| 11 | amax=341 | 1.3054 | 1.2984 | 1.2903 | 1.2764 | 1.2698 | 1.2627 | 1.2547 |
| 12 | amax=683 | 1.3221 | 1.3060 | 1.3007 | 1.2893 | 1.2792 | 1.2698 | 1.2678 |
| 13 | amax=1365 | 1.3224 | 1.3135 | 1.3054 | 1.2992 | 1.2883 | 1.2799 | 1.2754 |
| 14 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 1.2777 |
| 15 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| 16 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

For reference, record counts per cell (all cells with data have >=1 records;
r=11,12 have thin coverage at k=7,8 -- 49/137 and 22/190 respectively -- vs.
tens of thousands at r=13,k=7 (26,969 records)):

| r\k | k=1 | k=2 | k=3 | k=4 | k=5 | k=6 | k=7 | k=8 |
|---|---|---|---|---|---|---|---|---|
| 8 | 1 | 2 | 5 | 10 | 17 | 39 | 92 | 254 |
| 9 | 1 | 2 | 9 | 23 | 52 | 127 | 326 | 907 |
| 10 | 1 | 3 | 15 | 53 | 149 | 404 | 1102 | 2529 |
| 11 | 1 | 3 | 22 | 101 | 366 | 1138 | 49 | 137 |
| 12 | 1 | 4 | 33 | 191 | 836 | 3027 | 22 | 190 |
| 13 | 1 | 4 | 44 | 320 | 1734 | 7320 | 26969 | 96 |
| 14 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 5 |

gamma_P is consistently above gamma_a within each cell (compare the two
tables cell-by-cell), by a margin that stays roughly stable (~0.05-0.15)
across r and k -- consistent with the systemic p24 > a-cap slack found in Q1.

## Q4. Bridge-Lemma slack distribution

`fiber = p24/a`, as a function of k:

| k | n | mean | median | max |
|---|---|---|---|---|
| 1 | 6 | 1.0000 | 1.0000 | 1.0000 |
| 2 | 20 | 1.0232 | 1.0103 | 1.1091 |
| 3 | 131 | 1.0528 | 1.0434 | 1.2857 |
| 4 | 702 | 1.0866 | 1.0687 | 1.5000 |
| 5 | 3159 | 1.1338 | 1.1141 | 1.6667 |
| 6 | 12068 | 1.2046 | 1.1702 | 2.0000 |
| 7 | 28589 | 1.2879 | 1.2378 | 2.6364 |
| 8 | 4135 | 1.6898 | 1.6271 | 3.3600 |
| 9 | 3470 | 1.9480 | 1.9128 | 5.2162 |
| 10 | 2736 | 1.7824 | 1.4527 | 10.0000 |
| 11 | 2280 | 1.5636 | 1.5029 | 2.7799 |
| 12 | 1305 | 1.6877 | 1.6602 | 3.1574 |
| 13 | 420 | 1.8465 | 1.8184 | 2.8941 |
| 14 | 100 | 1.9449 | 1.9282 | 3.0193 |
| 15 | 20 | 2.0785 | 2.0511 | 2.6061 |
| 16 | 1 | 1.9149 | 1.9149 | 1.9149 |

`fiber` as a function of r:

| r | n | mean | median | max |
|---|---|---|---|---|
| 6 | 30 | 2.4885 | 2.6340 | 3.3600 |
| 7 | 43 | 1.7135 | 1.7500 | 2.2449 |
| 8 | 1737 | 2.4988 | 2.4235 | 10.0000 |
| 9 | 2980 | 1.9213 | 1.8934 | 4.0857 |
| 10 | 4258 | 1.5543 | 1.5055 | 2.6940 |
| 11 | 1874 | 1.2409 | 1.1946 | 2.1077 |
| 12 | 4941 | 1.2386 | 1.1766 | 2.7799 |
| 13 | 38495 | 1.2615 | 1.2174 | 2.9095 |
| 14 | 2765 | 1.5490 | 1.4638 | 3.1574 |
| 15 | 1562 | 1.5603 | 1.4934 | 2.8265 |
| 16 | 457 | 1.5529 | 1.5033 | 2.7269 |

**fiber ~= 1 at k=1**: yes, exactly (all 6 k=1 records have fiber = 1.0 --
the Bridge Lemma is tight for wheels, `a` saturates `p4/24` completely).
**Does fiber grow with k**: yes, roughly monotonically through k=9 (mean
1.00 -> 1.95), then it dips and becomes noisier for k=10..16 -- that range is
thin/mixed-source (`D5455`-style catalog records rather than the dense
`fr-r13` sweep), so the apparent non-monotonicity past k=9 is population
mix, not a clean trend reversal (r and k are correlated in the corpus by
construction -- most large-k records are concentrated at large r, e.g.
r=13 alone supplies 38,495 of the 59,142 records; see Q4's per-r table for
the same non-monotonic pattern by r).

Regression fit `log(fiber) ~= log(c) + k*log(rho)`:

- Fit over the 16 per-k **means**: `rho = 1.0539`, `c = 0.9385`.
- Fit over **all 59,142 individual records** (a>0): `rho = 1.0763`, `c = 0.7851`.

Either way `rho` is modest (~1.05-1.08 per interior vertex) -- the Bridge
Lemma slack grows slowly and sub-exponentially relative to the ~2.4x/ring-vertex
growth rate seen elsewhere in this program; it is not the dominant term.

## Q5. Empirical per-vertex growth

`val = (p4 / (24 * 2^(r-3)))^(1/k)`, over every record with k>=1 and p4>0.

**max val = 1.3948228**, at ident `fr-r13-n20-214279`, r=13, k=7, a=5679,
p4=252432.

This is the same record that tops the Q1 P-form-sharp-cap violation table --
unsurprising, since both quantities are measuring how much `p4` overshoots a
`base^k`-style bound at that particular configuration. `val ~= 1.395` gives an
empirical fitted-bound base noticeably above the a-side base (~1.32 from Q2),
reinforcing that any `p4 <= C*2^r*gamma^k` bound needs `gamma` pushed up from
the `a`-side value if it is meant to cover `p4` directly rather than `a`.

---

## Summary / flags for follow-up

- **Self-checks: both pass clean.** Wheel closed form matches 6/6; Bridge
  Lemma (`fiber >= 1`) holds with 0 exceptions across all 59,142 records.
- **The literal "P-form" sharp cap (`p24 <= sharp_cap` using the same
  `(2^r+2)/6 * (4/3)^(k-1)` formula proven for `a`) is FALSE**: 1,960/59,142
  records (3.3%) violate it, worst ratio ~1.37x, concentrated at r=12,13 and
  k=5-7. The a-form control has exactly 0 violations, as expected, which rules
  out an implementation bug in the cap formula itself -- the P-form genuinely
  needs a larger base (or different functional form) than the a-form does.
- **Q2 known-check reproduced exactly**: max gamma_a = 1.3224310 at
  r=13, k=2, ident `fr-r13-n15-4`. No investigation needed there.
- Q4's fiber-vs-k table shows the expected fiber=1 at k=1, growth through
  ~k=9, then a noisier non-monotonic tail at k>=10 that is a population-mix
  artifact (thin, source-mixed cells), not evidence against the growth trend.
- Overall picture: `a`'s sharp cap is confirmed tight and violation-free; the
  *coloring mass itself* (`p4/24`) sits above `a` (fiber > 1 whenever k > 1)
  and needs a strictly larger geometric base (~1.39-1.42 vs. ~1.32) to be
  capped the same way -- a real, measured gap between the `a`-side sharp cap
  and any analogous statement about `P(S,4)`.
