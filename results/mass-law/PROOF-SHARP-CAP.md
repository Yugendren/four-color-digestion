# The Sharp Cap: what is proven, what is not, and exactly where 4/3 dies

## 2026-08-23. Target: `a(K) <= ((2^r + 2)/6) * (4/3)^(k-1)`.
## Result: **NOT PROVEN — and provably not reachable by the route the program was on.**
## Proven instead: an exact base case, and a cap with the sharp wheel constant at γ = 2
## (`a <= 11·2^(r+k-7)`, tight at every wheel), γ = 3/2 at k = 2, and a
## per-configuration certificate whose realised base is <= 1.9371 corpus-wide.

Companion documents: `results/theorem/mass-law/PROOF-CAP.md` (the weak cap
`a <= 2^(r+k-3)`, its Bridge Lemma and Shelling Lemma — assumed here),
`results/mass-law/threshold-candidates.md` (the threshold half and the
corollary arithmetic), `results/theorem/mass-law/M2-groundwork-raw.txt`
(literature survey). Machine receipts: `results/mass-law/lemma_log.jsonl`.
Measurement scripts and outputs written for this document:
`tools/p4_measure.py` → `results/mass-law/p4_measurements.jsonl`,
`results/mass-law/p4-summary.md`; `tools/star_order_check.py` →
`results/mass-law/star-order-verification.md`; `tools/arc_profile.py` →
`results/mass-law/arc_profile.jsonl`, `results/mass-law/arc-profile.md`;
`tools/lattice_disk_entropy.py` → `results/mass-law/lattice-disk-entropy.md`;
exact colouring kernel `src/fourcolor/count4.py`.

---

## 0. Setting and notation

`K` is an RSST configuration; `S = S(K)` its free completion: a simple plane
near-triangulation of the closed disk whose outer face is bounded by an
**induced** cycle `R` (the ring) of length `r`, with `k` interior vertices, all
of degree `>= 5`; `n = r + k`. A **tri-colouring** of `S` assigns one of three
colours to each edge so that the three edges of every internal (triangular)
face receive three distinct colours. `Phi(K)` is the set of restrictions to
`E(R)` of tri-colourings of `S`, taken up to the `S_3` action on colours;
`a = |Phi(K)|` is the classical RSST header quantity. `P(G,q)` is the chromatic
polynomial. `W(r) := (2^r + 2)/6`.

Assumed from `PROOF-CAP.md` (proved there, re-verified here):

> **Bridge Lemma.** `#tri-colourings(S) = P(S,4)/4`; the `S_3` action on
> tri-colourings is free; hence the number of tri-colouring classes is
> `P(S,4)/24` and **`a <= P(S,4)/24`**.

Corpus invariants used, each machine-checked over all **59,142** canonically
deduped labeled configurations (signature `a2b1feba331bf2962b2b`):

| statement | verdict | receipt |
|---|---|---|
| `min interior degree >= 5` | HOLDS (59,142) | `cfd1d7a2eba82b50` |
| `a <= P(S,4)/24` (Bridge Lemma, measured) | HOLDS, 0 failures | `p4-summary.md` §Self-check 2 |
| `a <= ((2^r+2)/6)·(4/3)^(k-1)` (the target) | HOLDS, 0 violations | `7976235be48b5cde` |
| `a <= ((2^r+2)/6)·1.3224311^(k-1)` (exact minimal base) | HOLDS | `a01bd82ac1b588a8` |
| `a <= ((2^r+2)/6)·1.5^(k-1)` | HOLDS | `8f36fa12642d793f` |

---

## 1. Theorem (what is proven)

**Theorem 1 (Base case, exact).** If `k = 1` then `S` is the wheel `W_r` and

        a = (2^r + 2(-1)^r)/6 = P(W_r,4)/24 ,

so the Bridge Lemma is *tight* at every wheel. In particular
`a = (2^r+2)/6 = W(r)` for even `r` and `a = (2^r-2)/6 = floor(W(r))` for odd `r`:
**the sharp cap is exactly attained at every even wheel and misses by `2/3` at
every odd wheel.** (Proof in §2.)

**Theorem 2 (Star-first cap).** For every configuration `K` with `k >= 1`,

        a  <=  min over interior h of   (2^d + 2(-1)^d) · 2^(n-d-1) / 6 ,   d = deg(h),

and since every interior degree is `>= 5`, uniformly

        **a <= 11 · 2^(r+k-7) = (11/16) · 2^(r+k-3).**

The bound is **exactly attained at every wheel** (`d = r`, `n = r+1`, both sides
`(2^r+2(-1)^r)/6`). (Proof in §3.) Machine receipts: the min-over-`h` form HOLDS
on all 59,142 with `max lhs/rhs = 1` attained exactly at the six wheel records
(`4db503ddffcef7ee`); `a <= 11·2^(r+k-7)` HOLDS (`e8beefcd5e56f5c5`); the
sharper `a <= 5·2^(r+k-6)` (the `d = 5` instance) is KILLED by exactly the six
wheels (`9977aea202daca71`), which is what the `min over h` form predicts.

**Theorem 3 (Certified per-configuration cap).** With the BFS-link ordering of
§4, every configuration carries a computable certificate

        a  <=  (1 + 2(-1)^{d_1} 2^{-d_1}) · (2/3) · 2^(n-3) · PROD_{arcs} g(t) ,

`g(1) = 1, g(2) = g(3) = 3/4, g(4) = g(5) = 11/16, g(6) = 43/64, ... -> 2/3`.
This is `<=` Theorem 2 always and strictly better whenever any arc has length
`>= 2`. (Proof in §4; corpus evaluation in `results/mass-law/arc-profile.md`.)

**Theorem 3' (γ = 3/2 for the second interior vertex — unconditional).** For
`k = 2`,

        a  <=  (1 + 2(-1)^{d_1} 2^{-d_1}) · (2^r/6) · (3/2)  <=  (33/32)·(2^r/6)·(3/2) ,

the `γ = 3/2` cap with the sharp wheel constant to within 3%. The proof (§4.3)
rests on: *every edge of `S` joining two interior vertices has exactly two
common neighbours* — verified on all **610,846** interior–interior edges of the
corpus with zero exceptions, and *proved* outright when `k = 2` (a third common
neighbour would make a separating triangle with nothing inside it).

**The natural generalisation of Theorem 3' to all `k` is FALSE as a hypothesis.**
The condition "every interior vertex after the first contributes an arc of
length `>= 2`" (H2) fails on the corpus: 32.2% of the 372,008 BFS steps
contribute only length-1 arcs (which gain nothing) and a further 5.5%
contribute no arc at all; the length-1-only fraction rises from ~3% at `k = 3`
to ~60% at `k = 16` (`results/mass-law/arc-profile.md` §E). **So this route
yields no uniform `γ < 2` beyond `k = 2`** — only the per-configuration
certificate of Theorem 3, whose realised effective base
`gamma_prov = 2·(PROD g)^{1/(k-1)}` is `<= 1.937082` over the whole corpus
(argmax `gen-r8-n18-res61-403328`), i.e. strictly better than the weak cap on
every configuration tested but tending to 2 as `k` grows.

**Proposition 4 (the Bridge barrier — why 4/3 is out of reach).** Let
`S_0` be the free completion of the corpus configuration `gen-r8-n10-2`
(`r = 8`, `k = 2`, two interior vertices of degree 6). Then exactly

        P(S_0,4) = 1464,  P(S_0,4)/24 = 61,  a(S_0) = 55,  W(8)·(4/3) = 172/3 = 57.33... .

Hence `P(S_0,4)/24 > W(8)·(4/3) > a(S_0)`. **Any upper bound on `a` that factors
through the Bridge Lemma — i.e. any proof of the form `a <= P(S,4)/24 <= B(r,k)`
— cannot prove the sharp cap**, and more precisely cannot prove
`a <= W(r)·γ^(k-1)` for any `γ < 61/43 = 1.4186046...`. (Proof: exhibit; the
count is an exact integer computation, cross-checked in §6.) Over the whole
corpus the smallest `γ` for which the `P/24` form survives is
`max γ_P = 1.4186047` at exactly this record, versus `max γ_a = 1.3224310` at
`fr-r13-n15-4`; and the `P`-form of the sharp cap is **KILLED** — 1,960 of
59,142 records violate `P(S,4)/24 <= W(r)(4/3)^(k-1)`, worst ratio 1.3707 at
`fr-r13-n20-214279`. See `results/mass-law/p4-summary.md` Q1–Q2.

**Consequence for the programme.** The interval is now pinned:

| route | best `γ` it can possibly give | implied f-slope (with threshold T1) |
|---|---|---|
| Shelling only (`PROOF-CAP.md`) | 2 | 0.263 |
| **Star-first (Theorem 2) — PROVEN** | **2** (constant improved 16→11) | **0.263, offset +0.54** |
| BFS-link certificate (Theorem 3) — PROVEN, per-instance | `<= 1.9371` on the corpus, `-> 2` as `k` grows | n/a (not uniform) |
| Second interior vertex (Theorem 3') — PROVEN at `k = 2` | 3/2 | 0.4496 (if it generalised) |
| Bridge Lemma, best conceivable | `>= 61/43 = 1.4186` | `<= 0.5215` |
| **The sharp cap (target)** | **4/3** | **0.6337** |
| empirical minimum base | 1.3224310 | 0.6473 |

**To reach 4/3 one must abandon `P(S,4)` and bound `|Phi(K)|` directly.** That
is the single most important thing this investigation established.

**The sharp cap itself came out of the session stronger, not weaker.** It was
attacked out-of-sample on adversarially chosen bulk families — triangular-lattice
disks up to `r = 18, k = 15` (and, in the `P` proxy, up to `n = 169`), where the
`P`-form fails by four orders of magnitude — and `a` was computed exactly there:
the cap holds every time, with the margin *improving* (0.92 → 0.35) and the
realised base `gamma_a` *decreasing* (1.278 → 1.2365) as the disks grow (§5.3).
What is dead is the route, not the statement.

---

## 2. Proof of Theorem 1 (base case, with the equality case)

*(i) `k = 1` forces `S = W_r`.* The unique interior vertex `h` lies on every
internal face; each internal face is a triangle; so the internal faces are
exactly `h x_i x_{i+1}`, `i = 1..r`, where `x_1 ... x_r` is the ring in cyclic
order. Interior degree `>= 5` forces `r >= 5`.

*(ii) Tri-colourings of `W_r` <-> proper 3-colourings of `C_r`.* Write `e_i` for
the colour of the rim edge `x_i x_{i+1}` and `s_i` for the colour of the spoke
`h x_i` (indices mod `r`). The face condition on `h x_i x_{i+1}` says
`{s_i, e_i, s_{i+1}}` is all three colours; equivalently `s_i != s_{i+1}` and
`e_i` is the third colour, *determined* by `(s_i, s_{i+1})`. Conversely every
`(s_1,...,s_r)` with `s_i != s_{i+1}` gives a tri-colouring. Hence

        #TriCol(W_r) = P(C_r,3) = 2^r + 2(-1)^r ,

which also re-derives `P(W_r,4) = 4(2^r + 2(-1)^r)` through the Bridge Lemma.

*(iii) The restriction map.* Let `rho : TriCol(W_r) -> {rim colourings}`,
`t |-> (e_1,...,e_r)`. It is `S_3`-equivariant and `Phi(K) = rho(TriCol)/S_3`,
so `a` is the number of `S_3`-orbits in the image.

*Fibres.* Given `(e_i)` and `s_i`, the face condition forces
`s_{i+1} = tau_{e_i}(s_i)`, where `tau_c` transposes the two colours `!= c`
(and requires `s_i != e_i`). So the spoke vector is determined by `s_1`, and
`s_1` must avoid both `e_r` and `e_1`. Consequently:

* if `e_i != e_{i+1}` for some `i`, then `s_{i+1}` avoids two *distinct* colours,
  is therefore unique, and the whole fibre has size `<= 1`;
* if `(e_i)` is monochromatic (`e_i = c` for all `i`), the spokes alternate
  between the two colours `!= c`, which closes up around the cycle **iff `r` is
  even**; then the fibre has size exactly `2`, and for odd `r` it is empty.

*Stabilisers.* `sigma in S_3` fixes `(e_i)` iff it fixes every `e_i`. A 3-cycle
fixes no colour; the transposition `(xy)` fixes only `z`. So the rim colourings
with nontrivial stabiliser are exactly the 3 monochromatic ones.

*Conclusion.*

* **`r` odd.** No monochromatic rim colouring is in the image, every fibre is a
  singleton, and `S_3` acts freely on the image. Hence
  `a = |image|/6 = |TriCol|/6 = (2^r - 2)/6`.
* **`r` even.** The image is (non-monochromatic part) `u` (3 monochromatic
  colourings). Above the 3 monochromatic rim colourings sit exactly `3·2 = 6`
  tri-colourings; since `S_3` acts *freely* on `TriCol` these 6 form a single
  orbit — one tri-colouring class — while the 3 rim colourings also form a
  single orbit — one element of `Phi`. The remaining part has singleton fibres
  and free action. Hence
  `a = (|TriCol| - 6)/6 + 1 = |TriCol|/6 = (2^r + 2)/6`.

Both cases give `a = |TriCol|/6 = P(W_r,4)/24`: the Bridge Lemma is tight at
every wheel, and the sharp cap's constant `W(r) = (2^r+2)/6` is exactly the
truth at even `r`. **QED**

Machine receipts: `rec.k == 1 implies rec.a == (2**rec.r + 2*(-1)**rec.r)//6`
HOLDS, support 6 (`b2fb2220ca3e6953`); the six wheel records have measured
`P(S,4) = 4(2^r+2(-1)^r)` exactly and measured `P/24 / a = 1.000` exactly
(`p4-summary.md` §Self-check 1–2).

*Remark (the coincidence that is not one).* The wheel value is
`P(C_r,3)/6`, the count of proper 3-colourings of a cycle modulo colour
symmetry. Everything in the sharp cap's constant is this one classical number.

---

## 3. Proof of Theorem 2 (star-first ordering)

**Lemma S.** Let `S` be a near-triangulation of the disk with `n` vertices and
let `h` be an interior vertex of degree `d`. Then

        P(S,4) <= 4 · (2^d + 2(-1)^d) · 2^(n-d-1).

*Proof.* `L := N(h)` carries a cycle `x_1 x_2 ... x_d x_1` — the boundary of the
star of `h` in the near-triangulation. **`L` need not be an induced cycle**: the
corpus contains one interior vertex whose link has a chord (§4.3), coming from a
separating triangle. Nothing below uses chordlessness; a chord only removes
colourings, so `P(C_d,3)` remains a valid (slightly loose) bound there. Let `A`
be the subcomplex of all triangles of `S` not incident with `h`.

*Ordering claim.* The vertices of `S` can be ordered
`h, x_1, ..., x_d, w_1, ..., w_{n-d-1}` so that every `w_j` has two predecessors
that are **adjacent to each other**.

Grow greedily: start with the built region equal to the closed star of `h`, and
repeatedly attach any triangle of `A` sharing an *edge* with the built region.
Such a triangle introduces at most one new vertex, and when it does, that vertex
is adjacent to both endpoints of the shared edge — which are adjacent. It
remains to show the greedy exhausts `A`. The dual graph of `S` (triangles,
adjacent iff sharing an edge) is connected, `S` being a triangulated disk. Let
`T` be any triangle of `A` and take a dual path from `T` to a triangle
containing `h`; let `T'` be the last triangle of that path lying in `A`. `T'`
shares an edge with some star triangle `h x_i x_{i+1}`; that edge cannot be
`h x_i` or `h x_{i+1}` (those lie only in star triangles), so it is the link edge
`x_i x_{i+1}`. Hence every dual component of `A` contains a triangle sharing an
edge with `L`, the greedy can start in each component, and within a component
dual connectivity finishes the job. Every vertex of `S` lies on a triangle, so
all `n` vertices get ordered. (If `A` is empty then `S = W_r`, `d = r = n-1`, and
the claim is vacuous.)

*Counting.* Along this order: `h` has 4 choices; the cycle `L` must be properly
coloured avoiding `phi(h)`, i.e. with the remaining 3 colours, giving at most
`P(C_d,3) = 2^d + 2(-1)^d` (chords of `L`, if any, only reduce this); each `w_j`
has two adjacent — hence differently coloured — predecessors, so at most 2
choices. Multiplying gives the bound. **QED**

**Theorem 2** follows by the Bridge Lemma, minimising over interior `h`. For the
uniform form, put `B(d,n) := (2^d + 2(-1)^d)·2^(n-d-1)/6` and note
`B(d,n)/2^(n-7) = 2^{6-d}(2^d + 2(-1)^d)/6` equals `10, 11, 10.5, 10.75, 10.625,
10.6875, ...` for `d = 5, 6, 7, 8, 9, 10` and tends to `32/3 = 10.667`; the
maximum over `d >= 5` is `11` (at `d = 6`). Hence `a <= 11·2^(n-7)`.

**Corollary 2a.** If `S` has an interior vertex of degree exactly 5 — 58,977 of
the 59,142 corpus configurations do — then `a <= 5·2^(r+k-6) = (5/8)·2^(r+k-3)`.
Machine receipt `9fc08fe3083374d8` (HOLDS, support 58,977). The 165 exceptions
are all-degree-`>=6` interiors, including the six wheels, which is exactly why
the unconditional statement has to carry `11` rather than `10`. Note the
counter-intuitive shape: **odd interior degrees give the better bound**
(`P(C_d,3) = 2^d − 2` for odd `d` versus `2^d + 2` for even `d`), so the worst
case for the star-first argument is a configuration whose interior degrees are
all even and `>= 6`.

**Why this is not a `γ` improvement.** Theorem 2 improves the *constant* of the
weak cap by `11/16` and is exactly tight at `k = 1`, but its `k`-dependence is
still `2^k`. Per §2b of `threshold-candidates.md`, only the base `γ` moves the
implied f-slope; a constant only moves the offset. Concretely, with threshold
T1 (`a >= 2.4^r/12.79`):

> `f(r) >= ceil(0.26303·r − 0.1367)`  (Theorem 2)
> versus `ceil(0.26303·r − 0.6768)`  (weak cap).

| r | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 20 |
|---|---|---|---|---|---|---|---|---|---|---|
| weak cap `2^(r+k-3)` | 2 | 2 | 2 | 3 | 3 | 3 | 4 | 4 | 4 | 5 |
| **Theorem 2** | 2 | **3** | **3** | 3 | **4** | **4** | 4 | 4 | **5** | **6** |
| true `f(r)` | 5 | 5 | 6 | 7 | 7 | 8 | ? | ? | ? | ? |

so Theorem 2 buys one interior vertex at 6 of the 10 rings shown — real, small,
and free.

---

## 4. The BFS-link ordering and the γ question

### 4.1 The scheme

Let `H` be the induced subgraph of `S` on the interior vertices (connected for a
configuration). Let `h_1` be an interior vertex of maximum degree `d_1`, and
`h_1, ..., h_k` a BFS order of `H`. Colour `h_1` (4 ways) and its whole link
`L_1` as a cycle in 3 colours (`2^{d_1} + 2(-1)^{d_1}` ways). For `j >= 2`:
`h_j` is already coloured (it lies in the link of its BFS parent); split
`link(h_j)` — a cycle — into maximal **arcs** of not-yet-coloured vertices. Each
arc of length `t` is a path of `t` vertices, all adjacent to `h_j` (so all
avoiding `phi(h_j)`: 3 colours available), whose two ends are adjacent to
already-coloured vertices of `link(h_j)`. So the number of colourings of an arc
is a `K_3`-walk count between two *fixed* colours, at most

        M(t) := max_{a,b} #{walks of length t+1 from a to b in K_3}
              = (2^{t+1}+2)/3  (t odd),   (2^{t+1}+1)/3  (t even)
              = 2, 3, 6, 11, 22, 43, 86, ...  for t = 1,2,3,4,5,6,7.

Any further edges only reduce the count. Writing `g(t) = M(t)/2^t`
(`1, 3/4, 3/4, 11/16, 11/16, 43/64, ... -> 2/3`) and using
`sum of arc lengths = n - 1 - d_1`:

        P(S,4) <= 4(2^{d_1} + 2(-1)^{d_1}) · 2^{n-1-d_1} · PROD g(t)
                = 2^{n+1} (1 + 2(-1)^{d_1}2^{-d_1}) · PROD g(t),

        a <= (2/3)(1 + 2(-1)^{d_1}2^{-d_1}) · 2^{n-3} · PROD g(t).        (*)

At `k = 1` there are no arcs and (*) reads `a <= (2^r + 2(-1)^r)/6` — **exactly
Theorem 1**, so the scheme is tight at the base case by construction.

### 4.2 Where min-degree-5 enters (and where it does not)

* It does **not** enter the weak cap, nor Theorem 2's `2^k` factor: the shelling
  identity `sum over vertices of (b_i − 2) = k` (`b_i` = number of earlier
  neighbours) holds for *any* near-triangulation of the disk, whatever the
  degrees, and each vertex still has `<= 2` colours available.
* It enters **only through arc lengths.** At `j = 2` the already-coloured part of
  `link(h_2)` is exactly `{h_1, x, y}` (Fact C2 of §4.3), so the complementary
  arc has `deg(h_2) − 3` vertices. With `deg >= 5` that is `>= 2`, and
  `g(2) = 3/4 < 1`. With `deg = 4` it is `1` and `g(1) = 1`: **no gain at all**.
  (For `j >= 3` earlier steps have already coloured other link vertices and the
  arcs fragment — that is exactly where the scheme fails, §4.3.)
  So min-degree-5 is exactly the hypothesis that
  makes the closing constraint of an interior vertex non-degenerate, and it is
  worth precisely the step from `g(1) = 1` to `g(2) = 3/4`, i.e. `γ = 2 -> 3/2`.
  It cannot, by itself, be worth more: `g(t) >= 2/3` for every `t`, so
  **no argument of this shape can ever give `γ < 4/3`** — `4/3` is the *limit*
  of the scheme, attained only for arbitrarily long arcs, i.e. for interior
  vertices of unbounded degree. The empirical near-tightness of `4/3` is
  therefore not an accident of this scheme; it is the scheme's infimum.
* The same `4/3` is `(q−2)^2/(q−1)` at `q = 4` — Shrock–Tsai's *lower* bound for
  the triangular-lattice entropy. §5 explains why: `4/3` is the mean-field value
  of the per-closing-step factor, and mean-field is a floor, not a ceiling.

### 4.3 The second interior vertex (proved), and why the induction stops there

**Fact C2.** *Every edge `h h'` of `S` with both ends interior has exactly two
common neighbours.* At least two, because an interior edge of a
near-triangulation lies in exactly two triangles. Exactly two unless
`h, h', z` is a **separating** triangle for some third common neighbour `z`.
Machine-checked on all **610,846** interior–interior edges of the corpus: value
`2` in every single case, zero exceptions.

**Theorem 3' (k = 2).** For `k = 2`, Fact C2 holds by pure logic: a third common
neighbour `z` of `h_1, h_2` would give a triangle `h_1 h_2 z` that is not a face
and hence must contain a vertex strictly inside — but the only vertices are
`h_1, h_2` and the ring, and the ring lies outside. So the coloured part of
`link(h_2)` at step 2 is exactly `{h_1, x, y}`, the complementary arc has
`deg(h_2) − 3 >= 2` vertices, it is a *single* arc, and
`PROD g = g(deg(h_2) − 3) <= 3/4`. Substituting in (*) and using
`2^2 · (3/4) = 3`:

        a <= (1 + 2(-1)^{d_1}2^{-d_1}) · (2^r/6) · (3/2) <= (33/32)·(2^r/6)·(3/2)
          = (99/384)·2^r = 0.2578...·2^r .

(Compare the empirical sharp cap at `k = 2`: `W(r)·4/3 ≈ 0.2222·2^r`, and the
observed maximum `a = 1806` at `r = 13`, i.e. `0.2205·2^13`. The provable bound
is 13% above the sharp cap and 17% above the truth at `k = 2`.) The measured
maximum of `gamma_prov` over the whole `k = 2` population is exactly `1.500000`,
confirming the analysis is tight for the scheme.

**Why it stops.** For `j >= 3` the coloured part of `link(h_j)` is no longer
`{parent, x, y}`: earlier steps have already coloured other link vertices, the
arcs fragment, and `g(1) = 1` gives nothing. Hypothesis

> **H2.** every `h_j`, `j >= 2`, contributes at least one arc of length `>= 2`

would give `PROD g <= (3/4)^{k-1}` and hence `a <= (33/32)(2^r/6)(3/2)^{k-1}`
for all `k`. **H2 is FALSE on the corpus:** of the 372,008 BFS steps with
`j >= 2`, 20,379 (5.48%) contribute zero arcs and 119,705 (32.18%) contribute
only length-1 arcs; the length-1-only fraction climbs from ~3% at `k = 3` to
~60% at `k = 16`. Arc-length histogram over the whole corpus:
`t = 1: 119,705 | t = 2: 162,448 | t = 3: 57,974 | t = 4: 11,032 | t = 5: 467 |
t = 6: 3`. Consequently the realised base `gamma_prov` rises with `k`, and it
does so *identically at every ring* — the worst case is a pure function of `k`:

| k | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|
| max `gamma_prov` (any r) | **1.5000** | 1.7321 | 1.8171 | 1.8612 | 1.8882 | 1.9064 | 1.9195 |

`1.7321 = 2·(3/4)^{1/2}` is the signature of "one gaining step out of two", i.e.
`H2` already fails at `k = 3`. Overall max `1.937082`
(`gen-r8-n18-res61-403328`). The scheme therefore has **no uniform `γ < 2`**.
Full tables: `results/mass-law/arc-profile.md`.

One record, `gen-r8-n18-res74-522145`, has an interior vertex (`9`, degree 11)
whose link carries a chord (`4–5`, a separating triangle `4–9–5`). This is
harmless for Theorem 2 (a chord only removes colourings, so `P(C_d,3)` remains
an upper bound) but it does mean "the link of an interior vertex is a
*chordless* cycle" is **not** a corpus invariant: 1 exception in 431,159
(record, interior-vertex) pairs.

---

## 5. Obstruction: what exactly fails, and on which family

### 5.1 The Bridge barrier (rigorous, finite)

Proposition 4. `gen-r8-n10-2` — ten vertices, `r = 8`, `k = 2`, interior
vertices `9` and `10` both of degree 6 — has `P(S,4)/24 = 61` while
`W(8)(4/3) = 57.33` and `a = 55`. So the target inequality is *false for
`P(S,4)/24`* on a 10-vertex example. Any argument that upper-bounds `a` by
first upper-bounding the number of tri-colouring classes is dead at `γ = 4/3`.
Corpus-wide, `max_K (P(S,4)/(24 W(r)))^{1/(k-1)} = 1.4186047`, and the `P`-form
of the sharp cap fails on 1,960 of 59,142 configurations (3.3%), worst ratio
1.3707 (`fr-r13-n20-214279`, `r = 13`, `k = 7`).

The size of the gap is the Bridge-Lemma fibre `P(S,4)/(24a)`, measured to be
exactly `1` at `k = 1` and to grow like `~1.05–1.08^k` (`p4-summary.md` Q4).
It is *this* factor — two colour-inequivalent tri-colourings sharing a ring
restriction — that the sharp cap silently uses. A proof of the sharp cap must
therefore contain a mechanism that sees ring restrictions, not just
tri-colourings: e.g. a bound on the number of *distinct* ring traces, or an
injection from `Phi(K)` into `Phi` of a smaller configuration.

### 5.2 The per-step barrier (why every local argument stops at 4/3)

Order the vertices so each has `b_i >= 2` earlier neighbours. Edge count for a
near-triangulation of the disk (`m = 3n − r − 3`) gives the exact identity

        SUM over i>=4 of (b_i − 2) = k ,

for *any* such order — the "excess adjacency" budget is exactly `k`, i.e. one
closing per interior vertex. A vertex arriving with `b_i = 2` contributes a
factor of exactly `2` (its two predecessors are adjacent, hence differently
coloured). A vertex arriving with earlier neighbours forming a path `u — x — w`
has `4 − |{phi(u),phi(x),phi(w)}|` colours available: `2` if `phi(u) = phi(w)`
and `1` otherwise, i.e. an *average* factor `1 + Pr[phi(u) = phi(w)]` where the
probability is over the uniform measure on proper colourings of the already
built part. Hence, with `n − 3 − k` plain steps and `k` closing steps,

        P(S,4) <= 24 · 2^{n-3-k} · PROD (1 + Pr_i),
        a      <= 2^{r-3} · PROD (1 + Pr_i),

so the cap base is exactly `γ = 1 + Pr`. Thus

* `γ = 2` <=> no information about `Pr` (the shelling bound);
* `γ = 3/2` <=> `Pr[phi(u) = phi(w)] <= 1/2`;
* `γ = 4/3` <=> `Pr[phi(u) = phi(w)] <= 1/3`, i.e. `u` and `w` are *exactly
  uncorrelated* given their common neighbour `x`.

`1/3` is the mean-field / independent value, and correspondingly
`(q−2)^2/(q−1) = 4/3` at `q = 4` is Shrock–Tsai's **lower** bound for the
triangular-lattice ground-state entropy, not an upper bound. Proving `γ = 4/3`
means proving that correlations *never* help, anywhere in the class — a
statement of exactly the strength that fails for antiferromagnetic Potts models
at `q = 4` on the triangular lattice, which is **critical** (Moore–Newman,
cond-mat/9902295): correlations do not decay exponentially, so every
correlation-decay technique (Dobrushin, Salas–Sokal — which need `q >= 11` on
the triangular lattice) is unavailable at `q = 4`. This is a structural
obstruction, not a technical one.

Pointwise, the barrier is visible without any probability: an arc of length
`t = 1` (32% of all BFS-link arcs, and 60% of the steps at `k = 16`) has
`g(1) = M(1)/2 = 1`. No pointwise argument gains anything from a length-1
closing. The gain has to be extracted from the *distribution* of
`phi(u), phi(w)`.

**And that distribution has been measured.** Over a stratified sample of 1,315
configurations covering every occupied `(r,k)` cell, the exact step factors
`f_i = P(G_i,4)/P(G_{i-1},4)` along the star-first order are
(`results/mass-law/star-order-verification.md` Part 4):

| `b_i` (earlier neighbours) | mean `f_i` | min | max | # steps |
|---|---|---|---|---|
| 2 | **2.0000** | 2.0000 | 2.0000 | 14,886 |
| 3 | **1.3155** | 1.1754 | **1.6479** | 6,322 |
| 4 | 0.8583 | 0.7273 | 1.0933 | 1,165 |
| 5+ | 0.5138 | 0.2148 | 0.6576 | 565 |

The `b_i = 3` row is exactly `1 + Pr[phi(u) = phi(w)]`. Its **mean is 1.3155,
just below the mean-field 4/3** — which is why the sharp cap fits so well on
average — but its **maximum is 1.6479, i.e. `Pr = 0.648 > 1/2`**. So *no*
per-closing-step bound can give `γ = 3/2`, let alone `4/3`: individual closings
are demonstrably worse than either target, and any proof must average over
them. The exact per-step products give an implied base of `2.016` at `k = 1`
falling to `1.330` at `k = 16`, above `4/3` at essentially every `k`
(Part 4 table) — a second, independent confirmation of Proposition 4.

### 5.3 The bulk test: the sharp cap SURVIVES where the Bridge Lemma does not

Baxter's ground-state entropy of the 4-state antiferromagnetic Potts model on
the triangular lattice is `W(tri,4) ~ 1.4610` per site — **greater than
4/3 = 1.3333**. A disk cut out of the triangular lattice has all interior
degrees `6 >= 5` and an induced boundary cycle, so it lies in the class the cap
quantifies over. That makes the following prediction: the *P-form* of the cap
must fail badly in the bulk. It was tested directly
(`tools/lattice_disk_entropy.py`, exact `P(S,4)` on hexagonal disks `R = 1..7`
and corner-truncated triangular disks `m = 3..16`, up to `n = 169`):

| disk | r | k | n | `P/24` | cap | `(P/24)/cap` |
|---|---|---|---|---|---|---|
| HEX R=1 (`= W_6`) | 6 | 1 | 7 | 11 | 11 | **1.00** |
| TRI m=4 | 9 | 3 | 12 | 170 | 152.3 | 1.12 |
| HEX R=2 | 12 | 7 | 19 | 5,318 | 3,837.5 | 1.39 |
| HEX R=4 | 24 | 37 | 61 | 9.15e11 | 8.80e10 | 10.4 |
| HEX R=7 | 42 | 127 | 169 | 4.46e31 | 4.05e27 | 1.1e4 |
| TRI m=16 | 45 | 105 | 150 | 8.54e28 | 5.78e25 | 1.5e3 |

The fitted per-site entropy is `w_HEX = 1.541`, `w_TRI = 1.563` (over-estimates
of the bulk constant at these sizes because the boundary term `r·ln2` still
dominates, but unambiguously above 4/3). **So `P(S,4)/24` grows at roughly
1.40–1.44 per interior vertex in the bulk — the P-route is not merely tight, it
is wrong by unbounded factors.**

**But the sharp cap itself survives.** `a = |Phi|` was computed *directly* on the
same disks (`tools/lattice_disk_phi.py` — enumerate proper 4-colourings, take
Klein edge labels `t(uv) = c(u)+c(v)`, restrict to the boundary cycle,
canonicalise under `S_3`; the enumerator reproduces the repo's stored `a`
exactly on 12/12 corpus records):

| disk | r | k | `a` | cap | `a/cap` | `gamma_a` |
|---|---|---|---|---|---|---|
| HEX R=1 (`= W_6`) | 6 | 1 | 11 | 11.0 | **1.0000** | — |
| TRI m=4 | 9 | 3 | 140 | 152.3 | 0.9193 | 1.278 |
| TRI m=5 | 12 | 6 | 2,263 | 2,878.2 | 0.7863 | 1.271 |
| HEX R=2 | 12 | 7 | 2,756 | 3,837.5 | 0.7182 | 1.260 |
| TRI m=6 | 15 | 10 | 41,971 | 72,740.1 | 0.5770 | 1.255 |
| **TRI m=7** | **18** | **15** | **853,124** | **2,452,078** | **0.3479** | **1.2365** |
| ICOSA (4 disks, all interior degrees 5) | 5–6 | 2–6 | — | — | 0.42–0.89 | 1.18–1.30 |

**Zero violations, and the margin improves monotonically as the disk grows**
(0.92 → 0.79 → 0.72 → 0.58 → 0.35), with the realised per-interior-vertex base
`gamma_a` *decreasing* through 1.278, 1.271, 1.260, 1.255, 1.2365 — comfortably
below 4/3 and heading further below. The Bridge-Lemma fibre `P/(24a)` on these
disks is 1.21, 1.65, 1.93, 2.81, 6.30 at `k = 3, 6, 7, 10, 15`: it grows fast
enough to absorb the entire bulk excess, and then some. Note also that
`gamma_a` on lattice disks is *below* the corpus maximum 1.3224 — the extremal
configurations for the cap are not lattice-like; they are wheel-like, exactly
as the tightness at `k = 1` says.

**Conclusion.** The bulk-entropy argument does *not* refute the sharp cap; it
refutes the Bridge Lemma as a vehicle for it, for a second and much more
emphatic time. The sharp cap remains a live conjecture at all `(r,k)` tested,
including `k` far larger than any corpus configuration (`k = 10` at `r = 15`),
and the evidence for it is now out-of-sample: the corpus is exhaustive
enumeration plus catalogues, whereas these lattice disks were constructed
adversarially to break it and did not.

---

## 6. Verification and receipts

### 6.1 Harness receipts (corpus signature `a2b1feba331bf2962b2b`, 59,142 configs)

Every line reproducible with
`.venv/bin/python tools/test_lemma.py --check "<statement>"` (or `--bound`).
`HOLDS` means "survived the corpus", never "proved".

| # | statement | mode | verdict | receipt |
|---|---|---|---|---|
| R1 | `rec.k == 1 implies rec.a == (2**rec.r + 2*(-1)**rec.r)//6` | check | HOLDS (support 6) | `b2fb2220ca3e6953` |
| R2 | `min(len(rec.adjacency[v]) for v in rec.adjacency if v > rec.r) >= 5` | check | HOLDS | `cfd1d7a2eba82b50` |
| R3 | `rec.a <= min((2**deg+2*(-1)**deg)*2**(rec.n-deg-1)/6 over interior v)` | bound | HOLDS, `max lhs/rhs = 1` at the six wheels | `4db503ddffcef7ee` |
| R4 | `rec.a <= 11 * 2**(rec.r + rec.k - 7)` | bound | HOLDS | `e8beefcd5e56f5c5` |
| R5 | `rec.a <= 5 * 2**(rec.r + rec.k - 6)` | bound | **KILLED**, exactly 6 CEs (the six wheels) — as the `min over h` form predicts | `9977aea202daca71` |
| R6 | `rec.a <= (2**rec.r + 2)/6 * (4/3)**(rec.k-1)` (the target) | bound | HOLDS | `7976235be48b5cde` |
| R7 | `rec.a <= (2**rec.r + 2)/6 * 1.5**(rec.k-1)` | bound | HOLDS | `8f36fa12642d793f` |
| R8 | `rec.a <= (2**rec.r + 2)/6 * 1.3224311**(rec.k-1)` | bound | HOLDS (exact minimal base) | `a01bd82ac1b588a8` |
| R9 | every interior–interior edge has exactly 2 common neighbours (Fact C2) | check | HOLDS (610,846 edges) | `663fe16bb1a8ea3c` |
| R10 | `(5 in interior degrees) implies rec.a <= 5*2**(rec.n-6)` (Corollary 2a) | check | HOLDS, support 58,977 | `9fc08fe3083374d8` |
| R11 | `rec.a <= (33/32)*(2**rec.r/6)*1.5**(rec.k-1)` (the γ=3/2 cap, proven only at k<=2) | bound | HOLDS, max ratio 0.977 | `9ee2a646c508979c` |
| R12 | `rec.a <= (33/32)*(2**rec.r/6)*(4/3)**(rec.k-1)` | bound | HOLDS | `7330c3bae7873baf` |

### 6.2 Scripted measurements written for this document

| script | output | what it established |
|---|---|---|
| `src/fourcolor/count4.py` | — | exact `P(G,4)` by frontier DP with `S_4`-canonicalised states; validated against closed forms for wheels/cycles and against brute force on random graphs; 19s for the whole corpus |
| `tools/p4_measure.py` | `p4_measurements.jsonl`, `p4-summary.md` | exact `P(S,4)` for all 59,142; Bridge Lemma holds with 0 failures; `P/24 = a` exactly at all 6 wheels; **P-form of the sharp cap KILLED (1,960 violations)**; `max γ_P = 1.4186047`, `max γ_a = 1.3224310`; Bridge fibre grows `~1.05–1.08^k` |
| `tools/star_order_check.py` | `star-order-verification.md` | STAR-ORDER verified on all **431,159** (record, interior-vertex) pairs, 0 failures; `a <= B_star` 0 violations, `max a/B_star = 1.000000` at the wheels; interior connected / ring induced / Euler `m = 3n−r−3`: 0 violations each; per-step factor table (§5.2) |
| `tools/arc_profile.py` | `arc_profile.jsonl`, `arc-profile.md` | BFS-link scheme not refuted (`a <= BOUND` on all 59,141 evaluable); arc histogram; **H2 false**; `max gamma_prov = 1.937082`; bound/sharp-cap ratio grows from 1.0 at `k=1` to ~12.9 at `k=8` |
| `tools/lattice_disk_entropy.py` | `lattice-disk-entropy.md` | exact `P(S,4)` on hexagonal (`R<=7`, `n<=169`) and corner-truncated triangular (`m<=16`) lattice disks; **P-form of the sharp cap fails by up to 1.1e4** ; fitted per-site entropy 1.541/1.563; weak cap holds everywhere (kernel sanity) |
| `tools/lattice_disk_phi.py` | `lattice-disk-phi.md` | exact `a = |Phi|` on the same disks by direct enumeration + Klein restriction + `S_3` quotient, self-validated 12/12 against the repo's stored `a`; **sharp cap holds on all of them with improving margin**, `gamma_a` 1.278 → 1.255 |

### 6.3 Independent adversarial pass

Theorems 1, 2 and 3 (as "Lemma W", "Lemma S", "Lemma A") were handed to an
adversarial reviewer instructed to refute and to default to "refuted" when
unsure, with independent reimplementation required. Verdicts:

**The colouring kernel — SURVIVED.** Four independent methods, 202
cross-checks, 0 mismatches: exhaustive `4^n` brute force on all 52 corpus
records with `n <= 12`; an independent backtracking counter (different vertex
order, no `S_4` canonicalisation) on 80 random records `n = 13..32` plus all 40
records with `n >= 28`; a fresh memoised deletion–contraction chromatic
polynomial at `q = 4` on 10 records; 20 random graphs against all three.

**Theorem 1 (wheel) — SURVIVED, four ways.** Wheels `W_r`, `r = 5..14`, built
from scratch and `a` computed by (A) the repo's production path
`fourcolor.reduce.check`, (B) the repo's independent tie-breaker
`brute_force_extendable_codes`, (C) a from-scratch enumeration of spoke
sequences with explicit `S_3` canonicalisation, and (D) **the compiled 1995 RSST
C oracle `build/reduce_rsst`**. All four agree with `(2^r + 2(-1)^r)/6` at every
`r = 5..14`, odd `r` included; (D) covers `r = 5..12` and hard-errors at
`r >= 13` on its compile-time `DEG=13` array cap, a build limit, not a
disagreement. The reviewer also confirmed that the repo's `canonical_code` is
exactly the `S_3`-orbit representative the lemma assumes (its "gauge fix" of
colouring the first ring edge 0 is a pure 3× speedup that leaves the code *set*
unchanged), and verified the proof's own internal claim that for even `r`
exactly 6 tri-colourings collapse onto 3 monochromatic rim colourings
(pre-quotient image size `2^r + 2 − 3`).

**Theorem 2 (star-first) — SURVIVED.** Independent reimplementation of the
ordering claim over all 431,159 (record, interior-vertex) pairs: 0 failures,
agreeing with `tools/star_order_check.py`. The numeric corollary was
exact-checked with the colouring counter on 1,223 records (600 random + all 630
with `n >= 28`), every interior `h`: 0 violations, tightest ratio 0.462. The
reviewer additionally built three near-triangulations *violating* min-degree-5
(a stacked degree-3 vertex, a degree-4 diamond stack, two nested separating
triangles) to attack the "no degree hypothesis" claim — the lemma held on all
three, with the bound never tight. And it re-derived symbolically that
`11·2^(n-7)` is the exact global maximum of `bound(d)/2^(n-7)` over `d >= 5`.
Two honest caveats it raised, both now folded into §3: the link of an interior
vertex is a cycle but **need not be induced** (the one corpus chord), and one
of its two cross-checks turned out to be the same test twice.

**Theorem 3 (BFS-link) — core SURVIVED, the general conditional was a HOLE.**
`M(t)` verified against direct `K_3` walk enumeration for `t = 1..14`; the
unconditioned product bound exact-checked on 1,223 records with 0 violations
(tightest ratio 0.779), *including* the 1,175 of them where H2 fails; the
`(33/32)(2^r/6)(3/2)^{k-1}` arithmetic re-derived symbolically and confirmed
(both sides reduce to `(33/32)·2^(r-k)·3^(k-2)`; `1 + 2(-1)^{d_1}2^{-d_1} <= 33/32`
with equality exactly at `d_1 = 6`). **But H2 as originally stated is false on
53,523 of 59,142 records (90.5%) and on 138,583 of 372,017 individual steps
(37.25%)** — matching `arc-profile.md`'s independent 37.66%. The reviewer
called presenting the `γ = 3/2` conclusion under that hypothesis "a real
overclaim"; it has accordingly been demoted to Theorem 3' (`k = 2` only,
unconditional) and the failure is documented in §4.3. Its one residual doubt:
it fixed a canonical tie-break for `h_1` and the BFS order, so a cleverer order
might reduce the 90.5%, though not plausibly close it.

**Not refuted but worth recording:** the reviewer found
`a <= (33/32)(2^r/6)(3/2)^{k-1}` holds on **all 59,142** records with max ratio
0.977 (at the wheel `fr-r8-n9-0`) — receipt `9ee2a646c508979c` — and the
`(4/3)` version of the same shape also holds (`7330c3bae7873baf`). So `γ = 3/2`
with the sharp wheel constant is an empirically solid conjecture; it is only
the *proof* that stops at `k = 2`.

---

## 7. The implied f(r) corollary, with the constant actually proven

Pair the proven cap with the leading threshold candidate T1
(`d_reducible => a >= 2.4^r/12.79`, `threshold-candidates.md` §6; **empirical,
not proven**). `f(r) >= min{ k : B(r,k) >= 2.4^r/12.79 }`.

| cap used | status | closed form | slope |
|---|---|---|---|
| `2^(r+k-3)` | proven (`PROOF-CAP.md`) | `f(r) >= ceil(0.26303 r − 0.6768)` | 0.263 |
| **`11·2^(r+k-7)` (Theorem 2)** | **proven here** | **`f(r) >= ceil(0.26303 r − 0.1367)`** | **0.263** |
| `(33/32)(2^r/6)(3/2)^(k-1)` | proven only at `k = 2` | `f(r) >= ceil(0.44966 r − 0.9425)` | 0.450 |
| `W(r)(4/3)^(k-1)` | **not proven, and not reachable via the Bridge Lemma** | `f(r) >= ceil(0.63375 r − 1.6306)` | 0.634 |

| r | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 20 |
|---|---|---|---|---|---|---|---|---|---|---|
| true `f(r)` | 5 | 5 | 6 | 7 | 7 | 8 | ? | ? | ? | ? |
| weak cap | 2 | 2 | 2 | 3 | 3 | 3 | 4 | 4 | 4 | 5 |
| **Theorem 2 (proven)** | 2 | 3 | 3 | 3 | 4 | 4 | 4 | 4 | 5 | 6 |
| γ = 3/2 (hypothetical) | 3 | 4 | 4 | 5 | 5 | 5 | 6 | 6 | 7 | 9 |
| γ = 4/3 (the target) | 4 | 5 | 5 | 6 | 6 | 7 | 8 | 8 | 9 | 12 |

**Net movement from this session: the proven f-bound gains +1 interior vertex
at six of the ten rings shown, with no change of slope.** The slope is
controlled entirely by `γ`, and `γ = 2` survives.

---

## 8. What would have to be true for 4/3

1. **Drop the Bridge Lemma.** By Proposition 4 the target is false for
   `P(S,4)/24`. One needs a direct handle on `|Phi(K)|`, e.g.
   (a) an injection `Phi(K) -> Phi(K') x [4/3]` for a configuration `K'` with
   one fewer interior vertex and the *same* ring — note that ordinary vertex
   deletion changes the ring (deleting an interior vertex of degree `d` with `j`
   consecutive ring neighbours yields ring length `r + d − 2j + 2`, so the ring
   *grows* — for `d = 5, j = 2` it grows by 3, multiplying the cap by 8, so the
   induction would have to supply `a(K) <= a(K')/6`, an inequality of the wrong
   strength; deletion-based induction on this class is therefore a dead end
   unless the ring can be kept fixed); or
   (b) a transfer-matrix bound on the *ring-trace* operator, whose state space
   is ring colourings, not tri-colourings — the Jacobsen–Salas–Sokal
   Temperley–Lieb machinery (cond-mat/0204587) is the right formalism and its
   state space (non-crossing partitions of the ring) is exactly the object
   `Phi` lives on.
2. **A correlation inequality at `q = 4`**, `Pr[phi(u) = phi(w)] <= 1/3` for the
   distance-2 pairs created by closing steps in a min-degree-5 disk. This is a
   sharp mean-field statement at a critical point; no technique in the surveyed
   literature reaches it.
3. **Or: prove `γ = 3/2` and stop.** H2 (§4.3) is a finite, checkable link
   condition; `3/2` already lifts the implied f-slope from 0.263 to 0.450, and
   the Bridge route permits it.

