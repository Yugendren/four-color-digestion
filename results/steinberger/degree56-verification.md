# Verification of the degree-5/6 reconstruction against the paper's actual text

**Date:** 2026-08-23
**Target:** the `d <= 6` rows of `tools/lp_discharge.py::lowdeg_row`, i.e. §4 of
`results/steinberger/LP-SCHEMA-RESULT.md`, on which 3 of the 12 IIS certificate rows depend.

**Verdict: PARTIALLY MATCHES — the mathematics is confirmed and is in fact *conservative*;
the provenance sentence in LP-SCHEMA-RESULT.md §4/§8.3 is wrong and must be corrected.**
*(Update 2026-08-23: that correction is now in, and the anti-conservative gap flagged in
§5(b) has been closed — see the `RESOLVED` notes in §5.)*

The paper does **not** do the degree-5/6 case "by hand". It asserts the *stronger*
statement `T(v) = 0` (not merely `T(v) <= 0`) for `d(v) in {5,6}`, and it discharges that
obligation **by citation to Steinberger 2010**, in one sentence, inside the proof of
Theorem 5.2(i). Since `T(v) = 0` implies `T(v) <= 0`, and the reconstruction's rows encode
exactly `LB(w,x) <= actual final charge <= 0`, **the 3 dependent certificate rows survive
intact.** They are, if anything, weaker than what the paper claims. Two residual caveats
are recorded in §5 below; neither is a refutation, and one is a genuine unclosed gap.

---

## 1. Provenance of the text (this is now settled — the paper *is* obtainable)

The previous claim in `LP-SCHEMA-RESULT.md` §8.3 — *"We were not able to obtain the paper
text (arXiv:2603.24880 §7–8) in this environment"* — is no longer true.

The arXiv e-print tarball is retrievable and contains the **full LaTeX source**:

```
curl -sL -o eprint.tar.gz https://arxiv.org/e-print/2603.24880
# HTTP 200, 423,241 bytes, application/gzip, tarball mtime 2026-05-08
```

Contents: `main__1___1_.tex` (3,650 lines, the whole paper including appendices),
`pseudocode.tex` (2,039 lines), `tikz/rule.tex` (1,905 lines — **the machine-readable
source of Figure "rules", i.e. all 43/84 discharging rules**), `4CT.bib`, and the figure
PDFs. `00README.json` names `main__1___1_.tex` as the toplevel source.

Identity confirmed from the source:

> `\title{The Four Color Theorem with Linearly Many  Reducible Configurations and Near-Linear Time Coloring}` (line 106)
> `\author{ {\em Yuta Inoue}\thanks{The University of Tokyo, ...` (lines 111-113)

All line numbers below refer to `main__1___1_.tex` from that tarball. **The tarball is now
pinned in-repo** at `third_party/arxiv-2603.24880/archive.tar.gz` (sha256
`e517cf6f7af60c473fa7208f3e2de8d7cc8ad9971c86adabea9511a26e92bb8b`, recorded in
`third_party/CHECKSUMS.sha256`) and extracted to `third_party/arxiv-2603.24880/src/`, so
every quote below is re-checkable offline; `tools/fetch_sources.py` re-verifies it
alongside the other three arXiv bundles.

---

## 2. What the paper says, verbatim

### 2.1 Initial charge (line 600-607) — **matches the reconstruction exactly**

> Let $G$ be a triangulation in the plane. We start by assigning to each vertex $v \in V(G)$ the value
> $$ T_0(v) := 10(6 - d(v)), $$
> which we call the *initial charge at $v$*. It follows from Euler's formula (see Lemma \ref{lem:120} below) that
> $$ \sum_{v\in V(G)} T_0(v) = 120. $$

So `T_0(5) = +10`, `T_0(6) = 0`. This is `10*(6-d)` — identical to `lowdeg_row`'s
`constant = 10 * (6 - d)` and to `upper_bound_of_charge`'s `initial_charge`.

### 2.2 Final charge (Definition 6.3, lines 652-661) — matches

> (a) For adjacent vertices $u, v \in V(G)$, we define $\phi(u,v)$ as the sum of the values $r(R)$ over all rules $R\in \mathcal{R}$ that are applied with $s(R) = u$ and $t(R) = v$. This is the *charge sent from $u$ to $v$*.
>
> (b) For a vertex $u \in V(G)$, we set
> $$ T(u) := T_0(u) + \sum_{v \sim u} (\phi(v, u) - \phi(u,v)). $$
> The value $T(u)$ is called the *final charge* at $u$.

Sign convention identical to the reconstruction (`− out + in`).

### 2.3 Total charge is conserved (Lemma 6.4 `lem:120`, lines 671-679) — matches

> $\sum_{u \in V(G)} T(u) = 120$.
>
> *Proof.* By applying any discharging rule, the total sum of all charges remains the same. […]

This is exactly the premise §4 of `LP-SCHEMA-RESULT.md` invokes ("discharging preserves
total charge (= 120 by Euler), so the argument needs *every* vertex to end with charge ≤ 0").

### 2.4 THE KEY SENTENCE — degree 5 and 6 (proof of Theorem `thm:main-theorem`(i), lines 1141-1145)

> \begin{proof}
>    First, we note that (ii) follows directly from Lemma \ref{lem:12+} and Case 1 of Lemma \ref{lem:positive-comp}.
>
>    To get (i), we also need Case 2 of Lemma \ref{lem:positive-comp}, **but we are still missing the case where $v$ has degree at most $6$ and positive final charge. However, this cannot happen, for if $v$ has degree 5 or 6, then it has final charge 0 as proved in \cite{steinberger2010unavoidable}, where exactly the same discharging rules as here are used.**
> \end{proof}

(Emphasis added.) **That single sentence is the entirety of the paper's degree-5/6
discharging argument.** There is no case analysis, no charge accounting, no
hand-verification of the degree-5/6 discharge anywhere else in the 3,650-line source. I
grepped the whole file for every occurrence of "degree 5 / degree five / degree-5 /
degree 6 / degree six / degree-6 / degree at most 6"; the complete hit list is lines 243,
359, 360, 418, 454, 711, 1092, 1144, 1153, 1160, 1161, 1246, 1256, 3226, 3229, 3587, and
none of the others is a charge computation at a degree-5 or degree-6 hub.

### 2.5 What the computer check *does* cover (Lemma 8.2 `lem:positive-comp`, lines 1114-1123)

> Let $v$ be a vertex in $G$ such that there are no local obstructing cycles in $\bar B_2^8(v)$. Suppose that one of the following holds:
> 1. $9 \leq d_G(v) \leq 11$ and $T(v) \geq 0$,
> 2. $7 \leq d_G(v) \leq 8$ and $T(v) > 0$, or
> 3. $7 \leq d_G(v) \leq 8$ and $T(v) = 0$ and all neighbors of $v$ have degree at most $6$.
>
> Then the degree-bounded ball $B_2^8(v)$ contains a D-reducible configuration from $\mathcal{D}$. For the cases where $T(v)>0$, we only need configurations from $\cD_0$.
>
> \begin{proof}[Sketch of computer-assisted proof] The proof just does the above cartwheel enumeration to check that there are no counterexamples. \end{proof}

And from the cartwheel-enumeration paragraph (lines 1100-1101):

> For the center $v$, the maximal degree we consider here is 11 (for larger degrees we have Lemma \ref{lem:12+}), and for other vertices in $\bar B^8_2(v)$ it does not matter if the degree is 9 or larger, so it suffices to consider degrees up to 9.

Degrees `>= 12` are Lemma 7.4 `lem:12+` (lines 1086-1093). **Degrees 5 and 6 are covered by
neither.** This corroborates the observation in `LP-SCHEMA-RESULT.md` §4 that the released
C++ (`README.md`: `enum_all_bad_cartwheels.sh 7|8|9|10|11`) never enumerates a `d<=6` hub —
and now we know *why*: the paper outsources that case to Steinberger.

### 2.6 The "by hand" lemma is a *different* statement (Lemma 8.3 `lem:positive-hand`, lines 1148-1163)

The phrase "by hand" does appear, but it is not about degree-5/6 charge:

> We now begin examining vertices, whose final charge is 0, starting from a simple low-degree case that we can handle by hand.
>
> **Lemma `lem:positive-hand`.** Suppose that $v$ is a vertex in $G$ such that all vertices at distance at most 2 from $v$ are of degree at most 6. Then $B_2(v)$ has an obstructing cycle or a reducible configuration from $\mathcal{D}$.
>
> *Proof.* A vertex of degree at most $4$ is by itself a D-reducible configuration in $\mathcal D$, so we can assume that all vertices in $B_2(v)$ are of degree five and six. Then a configuration in Figure \ref{fig:confs-positive-hand} is contained in the degree-bounded ball $B_2^8(v)$, except if $v$ has degree five and is surrounded by neighbors of degree exactly six. If this is the case, then any one of the neighbors of $v$ and all its neighbors constitutes one of the configurations in Figure \ref{fig:confs-positive-hand}, which is in $\cD$.

This is a **purely structural** (configuration-containment) argument. It contains **no
charge arithmetic at all**. It is the *flat* (`T = 0`) low-degree case of
Theorem `thm:main-theorem`(iii), not the positive-charge case.

### 2.7 How degree-5/6 flat vertices are handled in Theorem (iii) (lines 1338-1348)

> It remains to consider the case where $d(v)= 5$ or $6$.
> If all vertices in $B_2(v)$ have degree at most $6$, we can apply Lemma \ref{lem:positive-hand}.
> Otherwise, let $v'$ be a vertex of degree $7$ or $8$ in $B_2(v)$.
> From the discussion for the case where $d(v)=7$ or $8$, if every vertex $u \in B_8(v')$ has final charge $0$ and all vertices in $B_{10}(v')$ have degree at most 8, then the claim holds.

**This is a structural match to the reconstruction's use of a non-strict `<= 0`.** A
degree-5/6 vertex with final charge *exactly* 0 is a permitted survivor, mopped up by the
gluing lemmas / `lem:positive-hand` — exactly as the reconstruction's rows allow
(`strict=False`, `rhs = -constant`, i.e. `LB <= 0`, not `< 0`). Had the paper required
`T < 0` at `d <= 6`, our rows would have been too weak; had it permitted `T > 0`, our rows
would have been invalid. Neither is the case.

### 2.8 Rule amounts (lines 624-625, 641) — matches, and constrains further

> The value $r(R)$ represents the amount of charge that is sent from the vertex $s(R)$ to its neighbor $t(R)$. **We have $r(R) = 1$ or $r(R)=2$ for all our rules.**
> […]
> In this paper, we use the set $\mathcal{R}$ of 43 rules shown in Figure \ref{fig:rules}. […] Thus, Figure \ref{fig:rules} shows 84 rules since precisely two, the first and fourth last, are symmetric under the reflection. […] This set is exactly the same as the set of rules used in \cite{steinberger2010unavoidable}, except that our 12th and 13th rules are considered as a single rule.

84 rules — matches `third_party/discharging-rules/R`. The published amounts live in
`{1,2}`; the LP relaxes this to `x >= 0`, which is the safe direction for INFEASIBLE.

### 2.9 Rule R(1) — independent confirmation of the tight row `10 − 5·x_rule001 <= 0`

From `tikz/rule.tex`, the first (uncommented, live) rule block, lines 967-977:

```latex
% (page, row, col) = (0, 0, 0)
    \node [deg5] at (0.3, 0.3) (v0) {};
    \node [deg5] at (1.133, 0.3) (v1) {};
    \node [above = 0.15 cm of v1, anchor=center] (v1+) { $+$ };
    \draw [->>-] (v0) -- (v1);
    ...
    \node at (0.7,1.2) {R(1)};
```

Decoded with the paper's own drawing convention (lines 626-635: a plain degree-`k` shape
means `[k,k]`; a `+` sign means `[k, infinity]`) and `->>-` = two arrowheads = `r(R) = 2`
(line 643: "The number of arrows in the figure represents $r(R)$"):

**R(1) = single edge, source of degree exactly 5, target of degree `>= 5`, amount 2.**

This is confirmed byte-for-byte against the released rule file
`third_party/discharging-rules/R/rule001.rule`:

```
2 1 2 2
1 5 5 2 -1
2 5 0 1 -1
```

(2 vertices; amount 2; vertex 1 degree range `[5,5]`; vertex 2 degree range `[5, unbounded]`.)

**Consequence:** a degree-5 vertex sends 2 along *every* incident edge unconditionally, so
its total out-charge is at least `5 x 2 = 10`, exactly its initial charge. Therefore
`T(v) = 10 - 10 - (other sends) + (receipts) = (receipts) - (other sends)`. This is
precisely the arithmetic behind the reconstruction's sanity anchor `10 - 5*x_rule001 <= 0`
being **tight** at `x0` (`x0_rule001 = 2`), and it independently derives the paper's
`T(v) = 0` claim for a degree-5 vertex that receives nothing.

---

## 3. What Steinberger 2010 actually proves (the cited authority)

Checked against the local copy `third_party/arxiv-0905.0043/src/4c.tex` (Steinberger,
*An unavoidable set of D-reducible configurations*).

Charge convention (line 519), which is the paper's `T` divided by 10:

> $$ c_{\mcal{L}}(W) = 6 - d(u) - \sum_{w}o_\mcal{L}(u,w) + \sum_wo_\mcal{L}(w,u) $$

The load-bearing lemma (line 544):

> **Lemma `appears`.** An element of $\mcal{U}_{\ncmath}$ appears in every cartwheel $W$ such that $c_{\mcal{L}_{42}}(W) > 0$.

Its proof, by hub degree (line 551-552):

> As explained, we will divide the proof of Lemma \ref{appears} according to the degree of the hub of $W$. We first describe the proof for the case when $W$ has a hub of degree $\leq 11$. In this case the proof is given by machine-readable scripts called "presentation files" by Robertson et al. **There is one presentation file for each hub degree from 5 to 11.** […] **For cartwheels of hub degree 5 and 6 one can also prove Lemma \ref{appears} by hand, as do Robertson et al., but we will not take the time to do this.** (However readers should easily be able to convince themselves from Fig. \ref{mayerrules}, given that the configurations of Fig. \ref{minorconfs} are in $\mcal{U}_{\ncmath}$.)

And the design intent (lines 443-446):

> Let *minor vertices* be vertices that start with a charge $\geq 0$ (vertices of degree 5, 6) and *major vertices* be vertices that start with a negative charge (vertices of degree $\geq 7$). The rules of Mayer […] remove the charge from vertices of degree 5 and place it on major vertices. **After Mayer's discharging rules are applied minor vertices have zero charge unless they are in the neighborhood of a reducible configuration.**

So the chain is: *Steinberger's degree-5 and degree-6 presentation files* (a computation, at
**Steinberger's own amounts**, against **Steinberger's own unavoidable set**
`U_nc`) ⟹ `c(W) > 0` implies a reducible configuration ⟹ in a minimum counterexample,
`T(v) <= 0` for `d(v) in {5,6}` ⟹ combined with the R(1) arithmetic of §2.9, `T(v) = 0`.

The "by hand" that Steinberger mentions is a proof he **explicitly declines to write down**,
and it belongs to *Robertson–Sanders–Seymour–Thomas*, not to the 2026 paper.

---

## 4. Comparison with the reconstruction

`tools/lp_discharge.py::lowdeg_row` (lines 234-255) builds, for a `d in {5,6}` hub `w`:

```
constant = 10 * (6 - d)
coeffs[k] -= 1   for each spoke i with  not never_apply(g, from_center_i, rule_k)
coeffs[k] += 1   for each spoke j with  always_apply(g, dart_to_center_j, rule_k)
strict   = False
```

and `rhs_of` (line 475-478) turns this into `<coeffs, x> <= -constant`, i.e.

```
LB(w, x) := 10*(6-d) - sum_i POSS_i(x) + sum_j ALW_j(x)  <=  0.
```

| claim in the reconstruction | paper's text | verdict |
|---|---|---|
| initial charge at a `d`-vertex is `10*(6-d)`, so `+10` at `d=5`, `0` at `d=6` | line 601, verbatim `T_0(v) := 10(6-d(v))` | **MATCHES** |
| total charge is conserved and equals 120 (Euler) | Lemma `lem:120`, lines 671-679 | **MATCHES** |
| final charge `= T_0 - out + in` | Definition `dfn:finalcharge`, line 659 | **MATCHES** |
| the argument needs `T(v) <= 0` at `d in {5,6}` | paper asserts the *stronger* `T(v) = 0` (line 1144) | **MATCHES (conservatively)** — our constraint is implied |
| `T(v) = 0` is *permitted* (non-strict row) | Theorem (iii) proof lines 1338-1348 explicitly handles flat `d=5,6` vertices | **MATCHES** |
| the released code never checks `d <= 6` | Lemma `lem:positive-comp` covers 7-11, `lem:12+` covers `>=12`; nothing covers 5-6 | **MATCHES** |
| *"the paper does it by hand"* | **FALSE.** The paper cites `\cite{steinberger2010unavoidable}` in one sentence. The paper's only "by hand" lemma (`lem:positive-hand`) is a structural, charge-free argument about `B_2` with all degrees `<= 6`. | **CONTRADICTED — but the error is in our prose, not in our rows** |
| `x0_rule001 = 2`, degree-5 source, unconditional, so `10 - 5*x_rule001 <= 0` is tight | R(1) in `tikz/rule.tex:967-977` and `rule001.rule` both give: single edge, source `[5,5]`, target `[5,inf]`, `r=2` | **MATCHES**, now derived from the paper's own figure source rather than inferred from the code |
| amounts range over `x >= 0` | paper: `r(R) in {1,2}` for all rules (line 624) | **relaxation** — the LP's feasible set strictly contains the paper's, so INFEASIBLE transfers |

### Effect on the 3 dependent IIS certificate rows

The three degree-5 rows in the 12-row IIS (`d5-55767`, `d5-57577`, `d5-57677`; and
`d5-55677` in the wider 19-row support) are of the form `10 + <coeffs, x> <= 0` with
`coeffs` an over-count of sends and an under-count of receipts. Since

* the paper's initial charge at `d=5` is `+10` (§2.1, verbatim), and
* the paper requires `T(v) = 0`, hence `T(v) <= 0`, at every degree-5 vertex of a minimum
  counterexample (§2.4, verbatim), and
* `LB(w,x) <= T(v)` by the soundness of `always_apply`/`never_apply`,

**the three rows are valid, and they are strictly weaker than what the paper asserts.**
No row needs to be removed, weakened, or re-derived. The certificate's `y^T b = -20` and
the INFEASIBLE verdict are unaffected.

Had the paper turned out to permit positive charge at degree 5, or to use a different
initial charge there, the rows would have collapsed — `LP-SCHEMA-RESULT.md` §8.3 named
exactly those two falsifiers. **Neither obtains.**

---

## 5. What remains unverified — honest statement

Three things. The first was a required edit; the second was a real anti-conservative gap;
the third is a framing hypothesis. **(a) and (b) have since been closed — see the
`RESOLVED` notes below; (c) stands.**

**(a) Correction owed to `LP-SCHEMA-RESULT.md`.** §4 says "…which the released code never
checks because the paper does it by hand", and §8.3 says "We were not able to obtain the
paper text (arXiv:2603.24880 §7–8) in this environment". Both sentences are now false. The
accurate statement is: *the released code never checks `d <= 6` because the paper cites
Steinberger 2010 for the claim that degree-5 and degree-6 vertices have final charge
exactly 0 under these same rules; Steinberger in turn proves it by machine, via his
hub-degree-5 and hub-degree-6 presentation files, at his own amounts and against his own
unavoidable set.* (I did not modify that file, per the task's scope.)

> **RESOLVED (2026-08-23).** Both sentences are corrected in `LP-SCHEMA-RESULT.md` §4 and
> §8.3, which now quote lines 602 and 1144 directly and record that Steinberger's `U_2822`
> has been independently re-verified here (2,822/2,822 D-reducible at ring ≤ 16,
> `results/differential-U_2822-r16/report.jsonl`). §8.5's hedge about `x ≥ 0` vs the
> paper's `r(R) ∈ {1,2}` (line 624) is likewise replaced by the plain statement that the
> LP verdict is *strictly stronger* than the paper's amount space needs.

**(b) The genuinely open gap: `d <= 6` rows are generated on *coarse* cartwheels.**
`lowdeg_rows` (lines 258-290) iterates `enum_wheel_degree_sequences(d)` and calls
`generate_cartwheel(d, degs)` — a hub plus a spoke-degree necklace in `{5,…,9}^d`, with
second-neighbour degrees left unpinned — then tests `wheel_is_blocked` on *that coarse
object*. A coarse wheel can be unblocked while **every** full refinement of it is blocked
by the pool; in that case the emitted row is spurious. This is anti-conservative for an
INFEASIBLE verdict and is *not* covered by the "refining would only strengthen the rows"
remark in §4 (refinement strengthens the *bound*, but it can also *delete the row
entirely*). The same gap exists in principle at `d = 7..11`, but there the C++ search
actually performs the refinement, so it does not bite. **Closing this would require
refining each of the 3 IIS degree-5 necklaces (`5,5,7,6,7`, `5,7,5,7,7`, `5,7,6,7,7`) to
full cartwheels and confirming that at least one refinement survives the ring<=14 pool.**
That check has not been done and is the single largest remaining hole on the degree-5 side.
Note it is a question about the *pool*, not about the paper — the paper text cannot settle
it, and nothing I found in the text bears on it either way.

> **RESOLVED (2026-08-23), `tools/lowdeg_refinement_check.py`, artifact
> `results/steinberger/lowdeg_refinement_check.json`, written up as
> `LP-SCHEMA-RESULT.md` §4.1.** The check was done, exactly and exhaustively, and **no row
> is spurious**. Two findings:
>
> 1. Exact enumeration of the full refinement space `{5,…,9}^m` for each of the four
>    degree-5 necklaces in the certificate (`m` = 10–12 open second-neighbour slots), via a
>    compiled DNF form of the blocking predicate whose equivalence with
>    `nl4ct.wheel_is_blocked` is differentially checked on 2,000 random refinements per
>    necklace (0 disagreements) and exhaustively on a 4-slot necklace in the tests:
>    `d5-55767` 4,087,028 / 9,765,625 unblocked; `d5-57577` 18,116,628 / 48,828,125;
>    `d5-57677` 149,493,536 / 244,140,625; `d5-55677` 3,415,017 / 9,765,625. Between a
>    third and two-thirds survive — not a knife-edge.
> 2. The gap closes uniformly for *all* 86 low-degree rows: `representative_degree`
>    collapses a `[5,9]` vertex to the single value `9`, so the coarse blocking test **is**
>    the blocking test of the refinement pinning every second neighbour to 9. Verified over
>    the whole sweep: all 580 unblocked `d=5` and all 2,466 unblocked `d=6` necklaces have
>    an unblocked tail-maximised refinement, 0 exceptions of 3,046.
>
> No row was dropped, the LP was not re-run, and both certificates re-verify unchanged
> (`yᵀb = −30` at 19 rows, `yᵀb = −20` at 12).

**(c) The architectural hypothesis is unchanged and is confirmed as a hypothesis, not a
theorem.** The paper's `T(v) = 0` at `d in {5,6}` is inherited from Steinberger's
computation *at Steinberger's amounts*. When the LP re-tunes `x`, that citation no longer
applies as proved. The reconstruction's response — impose the necessary condition
`T(v) <= 0` on every `d in {5,6}` cartwheel the pool does not block — is the correct
analogue of what the paper's own machinery demands at `d = 7..11` (see §2.5 and §2.7: a
`d<=6` vertex with `T > 0` is covered by *no* lemma in the paper, and a `d<=6` vertex with
`T = 0` is a permitted survivor). So the encoding is faithful to the proof architecture.
What it does *not* do — and cannot — is rule out a re-tuner who additionally re-runs a
degree-5/6 cartwheel enumeration against the pool and finds the positive-charge cases
blocked. The LP's row is exactly the condition such an enumeration would impose, in
relaxed lower-bound form, so this is a scope note rather than a defect.

**Not a problem:** the LP's `x >= 0` versus the paper's `r(R) in {1,2}`. The LP's feasible
set strictly contains the paper's, so INFEASIBLE over `R^84_{>=0}` implies infeasible over
`{1,2}^84`. This *strengthens* the result relative to how §8.5 currently hedges it.

---

## 6. Sources used

| what | where |
|---|---|
| arXiv:2603.24880 full LaTeX source | `https://arxiv.org/e-print/2603.24880` (HTTP 200, 423 KB tarball, mtime 2026-05-08); toplevel `main__1___1_.tex`, 3,650 lines. **Pinned locally:** `third_party/arxiv-2603.24880/{archive.tar.gz,src/}` |
| the 84 discharging rules as drawn in the paper | `third_party/arxiv-2603.24880/src/tikz/rule.tex`, 1,905 lines; live blocks begin at line 967 with `R(1)` |
| Steinberger 2010 | `third_party/arxiv-0905.0043/src/4c.tex` (local, 701 lines) |
| released rule files | `third_party/discharging-rules/R/rule001.rule` etc. |
| released check driver | `third_party/computer-checks/README.md` (hub degrees 7-11 only) |
| the reconstruction under test | `tools/lp_discharge.py:56-85` (docstring), `:234-255` (`lowdeg_row`), `:258-290` (`lowdeg_rows`), `:475-478` (`rhs_of`) |
