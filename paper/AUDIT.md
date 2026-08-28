# Adversarial error audit — `paper/main.tex`, `paper/sec_ml.tex`, `paper/refs.bib`

Method: every numerical claim in the paper was re-derived from the repository
artifact it cites (or from the pinned third-party source), not read back from a
summary document. Both Farkas certificates were re-verified by running
`tools/verify_farkas.py`. Claims that check out are **not** listed; this document
records only defects and unverifiable items.

For the record, the following load-bearing claims were re-derived and **do**
check out exactly, so they are not findings: the 19-row certificate
($y^\top b=-30$) and the 12-row IIS ($y'^\top b=-20$), including every multiplier
in Table `tab:cert`; the 19-column support and the "78 of 84 columns cancel, six
carry slack" claim; the 8,200/5,895 pool split and its ring histogram; the entire
Table `tab:frsweep` sweep (13,207,259 / 42,389 / 32,070 / 10,319 / 0) and the
per-shard $r{=}13$ timings; all eight rows of Table `tab:lpvariants` plus the four
`--exact-only`/`--conservative` rows; 833/16,157 and 77,185 recovered leaves;
$580+2{,}466=3{,}046$ low-degree wheels collapsing to 86 rows, and $\max
\mathrm{LB}(x_0)=0$ attained at the all-9 degree-5 wheel; the four refinement
percentages (41.9/37.1/61.2/35.0 %); 236 false positives (83+44+109), 215
oracle-confirmed, 21 exactly the ring-16 cases; the 59,142-record corpus with
signature `a2b1feba331bf2962b2b`, 13,169 D-reducible, 610,846 interior–interior
edges, 431,159 (record, vertex) pairs and 58,977/165; the whole coloring-mass
frontier table and the lattice-disk table (recomputed exactly from $W(r)(4/3)^{k-1}$);
$P(S_0,4)=1464$, $61>172/3>55$, floor $61/43$; 5,692,937 wheel candidates;
$85$ / $7{,}422$ / $2{,}253{,}185$ coverage; 430 zero-usage configs and the
`batch1b` PASS; every killed threshold form and its counterexample count; and all
four verbatim quotations from the pinned e-prints (Steinberger `4c.tex` lines 137
and 552; `arXiv:2603.24880` lines 602, 624, 635, 1144).

---

## BLOCKERS

### B1. The central citation misnames five of the paper's six subjects
**Location:** `paper/refs.bib:66–77` (entry `nl4ct2026`); rendered everywhere as
"Y. Inoue et al."

**Claim:** `author = {Inoue, Yuta and others}`, with
`note = {Author list and metadata taken from the pinned e-print source
third_party/arxiv-2603.24880/src/main__1___1_.tex; sha256 e517cf6f...92bb8b}`.

**What the artifact says:** `\author{...}` at line 111 of that exact file gives
six authors in full:

> Yuta Inoue (The University of Tokyo) `\and` Ken-ichi Kawarabayashi (National
> Institute of Informatics & The University of Tokyo) `\and` Atsuyuki Miyashita
> (The University of Tokyo) `\and` Bojan Mohar (Simon Fraser University & FMF,
> University of Ljubljana) `\and` Carsten Thomassen (Technical University of
> Denmark) `\and` Mikkel Thorup (University of Copenhagen)

The note is therefore false as written: the pinned source contains the full list,
and it was not used. Publishing an impossibility result *about* this paper while
citing it as "Inoue and others" — dropping Kawarabayashi, Mohar, Thomassen and
Thorup — is the single most damaging thing in the draft. (The sha256 stub does
check out: it is the digest of `arxiv-2603.24880/archive.tar.gz` in
`third_party/CHECKSUMS.sha256`, and `shasum -c` passes on all four e-prints.)

**Severity:** BLOCKER

**Suggested replacement (`refs.bib`):**
```bibtex
@misc{nl4ct2026,
  author       = {Inoue, Yuta and Kawarabayashi, Ken-ichi and Miyashita, Atsuyuki
                  and Mohar, Bojan and Thomassen, Carsten and Thorup, Mikkel},
  title        = {The Four Color Theorem with Linearly Many Reducible Configurations
                  and Near-Linear Time Coloring},
  year         = {2026},
  eprint       = {2603.24880},
  archivePrefix= {arXiv},
  primaryClass = {math.CO},
  note         = {Author list taken from \texttt{\textbackslash author} at line 111 of the pinned
                  e-print source \texttt{third\_party/arxiv-2603.24880/src/main\_\_1\_\_\_1\_.tex};
                  archive sha256 \texttt{e517cf6f...92bb8b} recorded in
                  \texttt{third\_party/CHECKSUMS.sha256}}
}
```

---

### B2. The abstract claims header agreement for a catalog that has no headers to agree with
**Location:** `paper/main.tex:72–74` (abstract) and `paper/main.tex:1090–1092`
(caption of Table `tab:catalogs`)

**Claim (abstract):** "the RSST $633$ ($249$ D-reducible, $384$ C-reducible),
Steinberger's $2{,}822$, and $7{,}697$ of the 2026 pool, **all with computed
$|\Phi(K)|$ matching the published headers exactly**".
**Claim (table caption):** "``Agree'' means the computed $|\Phi(K)|$ and
$|{\rm consistent}|$ both match the published header fields *and* the
configuration is confirmed reducible" — a definition applied uniformly to all
three rows, including the 2026 row (`7,770 / 7,697`).

**What the artifact says:** the 2026 pool's `.conf` files carry a two-field
header only. `third_party/reducible-configurations/D/D0003.conf` begins `13 8`
($n$, $r$) — no $|\Phi(K)|$, no contract count. Every one of the ten `D000*.conf`
files I checked has exactly two fields on the header line. By contrast RSST's
`unavoidable.conf` record `2.126` has `12   8      81     154` and Steinberger's
`U_2822.conf` has `10 6 16 0`, both carrying $a$. Correspondingly
`results/p3/pool-verify/SUMMARY.json` reports only
`{"verified": 7697, "d_reducible": 7697, "anomalies": 0, "cpu_hours": 12.3,
"unverified_rings_17_18": 73}` — no header-agreement field, because there is no
header to agree with.

The paper contradicts itself on this: `main.tex:981–982` correctly restricts
header agreement to "all $3{,}455$ hand-curated catalog configurations"
($633+2{,}822$), excluding the 2026 pool.

**Severity:** BLOCKER

**Suggested replacement (abstract, lines 72–74):**
> the RSST $633$ ($249$ D-reducible, $384$ C-reducible) and Steinberger's
> $2{,}822$, both with computed $|\Phi(K)|$ matching the published headers
> exactly, and $7{,}697$ of the 2026 pool independently confirmed D-reducible
> (that pool's released files carry only an $n\ r$ header, so there is no
> published $|\Phi(K)|$ to compare against) ---

**Suggested replacement (Table `tab:catalogs` caption):**
> Independent re-verification of the published catalogs. For the RSST and
> Steinberger rows, ``agree'' means the computed $|\Phi(K)|$ and
> $|{\rm consistent}|$ both match the published header fields \emph{and} the
> configuration is confirmed reducible. The 2026 released files carry only an
> $n\ r$ header, so for that row ``agree'' means only ``independently confirmed
> D-reducible''; the $73$-configuration shortfall is the rings-$17$--$18$
> remainder that is outside our engines' budget, not a disagreement.

---

### B3. Theorem 3.1's "i.e." gloss is vacuously satisfied by every $x$
**Location:** `paper/main.tex:396–399`

**Claim:** "Then there is no vector of nonnegative rule amounts
$x \in \mathbb{R}^{84}_{\ge 0}$ under which the discharging argument closes over
$P_{14}$: **i.e. under which every vertex of a hypothetical minimum
counterexample ends with charge $\le 0$**."

**What is actually true:** the Four Colour Theorem is a theorem, so there is no
minimum counterexample. Any statement universally quantified over the vertices
of a minimum counterexample is therefore vacuously true, for *every* $x\ge 0$.
Read literally, the gloss makes the theorem false. This is not a quibble a
referee will let pass: it is the one sentence that says what the theorem means.

What the artifacts actually certify is a statement about a finite family of
*unblocked local objects*: the 48,509 deduplicated rows are generated from
97,860 fully refined cartwheels and 3,046 unblocked coarse degree-$\le6$
necklaces, and the certificate shows the resulting linear system has no
nonnegative solution. The theorem must be stated at that level. (The paper knows
this — `main.tex:164–169` and `817–838` say exactly the right thing about
unblocked $\ne$ realizable — but the theorem statement does not inherit it.)

**Severity:** BLOCKER

**Suggested replacement (lines 396–399):**
> Then there is no vector of nonnegative rule amounts
> $x \in \mathbb{R}^{84}_{\ge 0}$ satisfying the local charge conditions that the
> $2026$ schema imposes over $P_{14}$: i.e.\ no $x\ge 0$ under which every
> cartwheel leaf that $P_{14}$ fails to block satisfies $C(L,x)\le 0$ (strictly
> $<0$ in the cases of \S\ref{sec:necessity}) and every unblocked degree-$5$ or
> degree-$6$ wheel satisfies $\mathrm{LB}(w,x)\le 0$. In particular the
> discharging argument of \cite{nl4ct2026} cannot be made to close over $P_{14}$
> by re-tuning its amounts. The hypotheses under which these rows are necessary
> conditions --- including that an unblocked local structure need not be
> realizable --- are stated in \S\ref{sec:lp-scope}.

---

### B4. The "structural principle" slope formula is wrong
**Location:** `paper/main.tex:1600–1606` (Remark, *The structural principle*)

**Claim:** "Under a cap $B(r,k) = C\cdot 2^r\gamma^k$, the implied $f$-slope is
$(\log_2\beta - 1)/(1 - \log_2\gamma)$."

**What is actually true:** from $c\beta^r \le a \le C2^r\gamma^k$ one gets
$k\log_2\gamma \ge r(\log_2\beta - 1) + \log_2(c/C)$, so the slope is
$$(\log_2\beta - 1)\big/\log_2\gamma.$$
The stated formula is wrong, and demonstrably so against the paper's own numbers.
With $\beta=2.4$ ($\log_2\beta = 1.263034$):

| cap | $\gamma$ | correct formula | paper's formula | slope the paper reports |
|---|---|---|---|---|
| weak $2^{r+k-3}$ / Thm 4.4 | $2$ | $0.263$ | **division by zero** | $0.263$ (`main.tex:1370`, `1597`) |
| $\gamma=3/2$ | $3/2$ | $0.4497$ | $0.6338$ | $0.450$ (`main.tex:1873`) |
| sharp cap | $4/3$ | $0.6338$ | $0.4497$ | $0.634$ (`main.tex:1594`) |

Every slope the paper actually uses comes from the *correct* formula; the printed
formula both blows up on the proven cap and swaps the $3/2$ and $4/3$ answers.
All of Table `tab:implied` recomputes correctly under
$(\log_2\beta-1)/\log_2\gamma$, so nothing downstream changes.

**Severity:** BLOCKER

**Suggested replacement (line 1601–1602):**
> Under a cap $B(r,k) = C\cdot 2^r\gamma^k$, the implied $f$-slope is
> $(\log_2\beta - 1)/\log_2\gamma$ --- $0.263$ at $\gamma=2$, $0.450$ at
> $\gamma=3/2$, $0.634$ at $\gamma=4/3$.

---

### B5. The abstract says "we prove" for a result the paper itself grades *Certified*
**Location:** `paper/main.tex:49–51` (abstract); cf.\ `main.tex:96–105`
(definition of the three grades), `main.tex:391` (`\begin{theorem}[Certified]`)

**Claim:** "we **prove** that \emph{no} nonnegative amount vector
$x\in\mathbb{R}^{84}_{\ge 0}$ closes the discharging argument."

**What the paper itself says:** §1.1 defines **Proven** as "a mathematical
argument, in some cases with a finite exhaustive case analysis whose completeness
argument is given" and **Certified** as "a finite computation whose output is an
independently checkable certificate". Theorem 3.1 is labelled `[Certified]`, not
`[Proven]`; §1.3 item 2 states that a spurious row from an unrealizable-but-
unblocked structure "is anti-conservative for an \textsc{infeasible} verdict";
§1.3 item 3 states that three of the twelve rows rest on a *reconstruction* of a
case the source paper discharges by citation. A paper whose stated methodological
contribution is disciplined epistemic grading cannot use the verb "prove" in its
abstract for its own `[Certified]` headline.

**Severity:** BLOCKER

**Suggested replacement (lines 49–51):**
> D-reducible pool to its $5{,}895$ members of ring size $\le 14$, we certify that
> \emph{no} nonnegative amount vector $x\in\mathbb{R}^{84}_{\ge 0}$ closes the
> discharging argument --- ``certify'' in the sense of \S\ref{sec:notclaim}: an
> exact-rational Farkas certificate over a row set that is necessary under two
> stated hypotheses, not an unconditional proof.

---

### B6. The paper's headline ML finding is a negative replication of a work it cites incompletely and does not pin
**Location:** `paper/refs.bib:238–247` (`huang2025zeta`); used at
`sec_ml.tex:20–22`, `25`, `254–315`

**Claim:** `author = {Huang and Jackson and Lee}`, `note = {Author list
abbreviated; see the e-print. Follow-up: arXiv:2605.30482. ...}`.

**What the artifacts say:** there is no pinned copy of `arXiv:2511.12421`
anywhere in `third_party/` or in the repository (the four 4CT e-prints *are*
pinned, with checksums; this one is not). Consequently *none* of the source-side
numbers §7.5 argues against — the "about 1.5\% exact-match" ablation cost, the
"approximately 84\%" probe accuracy, the "339,716" parameter count, the
$n=11$–$16$ length-generalization range — can be checked against a pinned
document, while §7.5 concludes that the source's mechanism does not replicate.
The bare-surname author list ("Huang", "Jackson", "Lee", no given names) will
also not render as a usable citation, and `arXiv:2605.30482` is cited in a note
with no bib entry at all.

Given §7.5's conclusion ("a materially different internal mechanism by every
measure we could apply"), the burden is on this paper to pin and cite the target
properly.

**Severity:** BLOCKER

**Suggested action:** pin `arXiv:2511.12421` (and `2605.30482`) under
`third_party/` with recorded SHA-256, extract the full author list from the
e-print's `\author` block exactly as was done for `arXiv:2603.24880`, give
`huang2025zeta` a complete `author` field and a separate bib entry for the
follow-up, and add to Appendix A a row citing the pinned source line for each of
the three source-side numbers §7.5 contradicts. **Do not invent the author
names**; if the source cannot be pinned before submission, §7.5 must be recast
so that it does not attribute specific quantitative findings to an unpinnable
citation.

---

## SHOULD-FIX

### 7. Mutation-search totals attributed to the three killed rules include the fourth (surviving) rule
**Location:** `paper/main.tex:1757–1761`; also Appendix A `main.tex:2111–2112`

**Claim:** "Adversarial mutation search ... generated $339{,}600$ mutants from
$9{,}391$ seeds; $248{,}861$ failed the structural legality gate, $88{,}496$ no
longer satisfied the rule, $291$ were duplicates, and $1{,}952$ novel legal
rule-satisfying configurations were submitted to the reducibility checker."
This sits in §8.1, headed "Three mined sufficient conditions, killed by mutation".

**What the artifact says:** `results/theorem/stress_test.json` has four states.
The quoted totals are the sum over **all four**, including `dual_r11` — which is
the *surviving* rule that §8.2 reports separately, and whose numbers (41,449 /
1,664 seeds / 41,148 gate / 273 rule / 28 dup / 0 labelled) the paper then quotes
again at `main.tex:1785–1787`. So the same run is counted twice.

Correct totals for the three killed candidates:

| | paper (all four) | three killed rules only |
|---|---|---|
| seeds | 9,391 | **7,727** |
| mutants generated | 339,600 | **298,151** |
| failed legality gate | 248,861 | **207,713** |
| no longer satisfied the rule | 88,496 | **88,223** |
| duplicates | 291 | **263** |
| submitted to the checker | 1,952 | 1,952 (unchanged) |

**Severity:** SHOULD-FIX

**Suggested replacement (lines 1757–1761):**
> Adversarial mutation search (\S\ref{sec:methods}, M2) generated $298{,}151$
> mutants from $7{,}727$ seeds against these three rules; $207{,}713$ failed the
> structural legality gate, $88{,}223$ no longer satisfied the rule, $263$ were
> duplicates, and $1{,}952$ novel legal rule-satisfying configurations were
> submitted to the reducibility checker.

and in Appendix A (line 2111): "Mutation stress test: $339{,}600$ mutants over
all four candidate rules ($298{,}151$ against the three killed ones), $1{,}952$
labelled, $236$ FPs, $215$ oracle-confirmed".

---

### 8. The (H2) failure count appears in no artifact, and two artifacts disagree about the step count
**Location:** `paper/main.tex:1839–1842`

**Claim:** "(H2) fails on at least $53{,}549$ of $59{,}142$ records
($\ge 90.5\%$) and on $37.66\%$ of individual BFS steps ($140{,}084$ of
$372{,}008$)."

**What the artifacts say:**
* `results/mass-law/PROOF-SHARP-CAP.md:640–642`: "H2 as originally stated is
  false on **53,523** of 59,142 records (90.5%) and on **138,583 of 372,017**
  individual steps (37.25%)".
* `results/mass-law/arc-profile.md:145`: `| all | 372008 | 20379 | 0.0548 |
  119705 | 0.3218 |`, giving $20{,}379+119{,}705 = 140{,}084$ of $372{,}008$
  ($37.66\%$) — which is what `main.tex:1412–1415` correctly quotes.

So the paper takes its record count from `PROOF-SHARP-CAP.md` but transcribes it
as 53,549 rather than 53,523, and takes its step count from the *other* artifact,
which disagrees with `PROOF-SHARP-CAP.md` (140,084/372,008 vs 138,583/372,017).
Both round to 90.5% / ~37–38%, so nothing downstream changes — but this is in the
paragraph headed "Corrections to our own record", where a transcription slip is
maximally costly.

**Severity:** SHOULD-FIX

**Suggested replacement (lines 1839–1842):**
> lengths that looked innocuous. (H2) fails on $53{,}523$ of $59{,}142$ records
> ($90.5\%$) and on $37.66\%$ of individual BFS steps ($140{,}084$ of
> $372{,}008$; the record-level count is from
> \art{results/mass-law/PROOF-SHARP-CAP.md} and the step-level counts from the
> independent sweep in \art{results/mass-law/arc-profile.md}, whose step totals
> differ by $9$ because of a differing tie-break in the BFS order).

Better still, re-run one of the two and quote a single artifact for both numbers.

---

### 9. "Two further conditions" is followed by three, and §4.2 cites a condition 7 that is never defined
**Location:** `paper/main.tex:293–303` and `paper/main.tex:885`

**Claim (293):** "RSST's reference parser \texttt{ReadConf} in \texttt{reduce.c}
enforces **two further conditions** on any file it accepts, and we enforce both:"
— followed by a list numbered 4, 5, 6 (three items).
**Claim (885):** "filtered to the RSST configuration class (nonempty connected
interior of minimum degree $5$; **RSST conditions 4--7** including the
ring-contact-arc condition 6)".

**What is defined:** conditions 1–6 only. There is no condition 7 anywhere in the
paper. Condition 5 is explicitly "automatic given 1--3", which is presumably why
the prose says "two", but the list says three and the later cross-reference says
four.

**Severity:** SHOULD-FIX

**Suggested replacement (293–294):**
> RSST's reference parser \texttt{ReadConf} in \texttt{reduce.c} records three
> further conditions on any file it accepts --- one of them redundant --- and we
> enforce all three:

**Suggested replacement (885):**
> filtered to the RSST configuration class (nonempty connected interior of
> minimum degree $5$; conditions 1--6 of \S\ref{sec:prelim}, including the
> ring-contact-arc condition 6)

---

### 10. "Proved three times by machine", with four machine proofs cited on the same line
**Location:** `paper/main.tex:106–107`; cf.\ abstract `main.tex:39–41`

**Claim:** "The Four Colour Theorem has been proved three times by machine
\cite{appel1977every,appel1977every2,rsst1997,steinberger2010,nl4ct2026}".

**What the citation list contains:** four independent machine proofs — Appel–Haken
(two papers), RSST 1997, Steinberger 2010 and `nl4ct2026`. Steinberger's is a
complete independent unavoidable-set-plus-reducibility proof, which the paper
itself treats as such at `main.tex:203–207` ("$\sim1834 \to 633 \to 2{,}822$
D-only $\to 8{,}200$") and at `main.tex:1119–1123`. The abstract compounds it by
naming only three and omitting Steinberger — the very author whose open question
(C1) answers.

**Severity:** SHOULD-FIX

**Suggested replacement (106–107):**
> The Four Colour Theorem has been proved four times by machine
> \cite{appel1977every,appel1977every2,rsst1997,steinberger2010,nl4ct2026}

and in the abstract (39–41), "(Appel--Haken 1977; Robertson--Sanders--Seymour--Thomas
1997; Steinberger 2010; and the 2026 near-linear-time proof of \texttt{arXiv:2603.24880})",
adjusting "three machine proofs" to "four".

---

### 11. "13,103 s of checker CPU" is recorded nowhere
**Location:** `paper/main.tex:1120–1121`

**Claim:** "$2{,}822/2{,}822$ agree with the published headers, $0$
disagreements, $13{,}103$ s of checker CPU."

**What the artifact says:** `results/differential-stein-log.txt` is a pure
progress log with no timestamps and no elapsed-time line; its last two lines are
`final: 2822 agree, 0 disagree -> .../report.jsonl` and `exit=0`. Nothing in
`results/` records 13,103 s. (The $633$/$2{,}822$/$b{=}0$/ring-$6$–$16$ facts all
check out; only the timing is unbacked.) Appendix A does not flag this number as
narrative-only, unlike the $2{,}145$ monotonicity pairs and the $0.082$ slack,
which it correctly does flag at `main.tex:1989–1995`.

**Severity:** SHOULD-FIX

**Suggested action:** either drop the figure, or re-derive it and store it (e.g.
add a `seconds` field to `results/differential-U_2822-r16/report.jsonl`'s summary)
and cite it in Appendix A. If dropped, replace lines 1120–1121 with:
> $2{,}822/2{,}822$ agree with the published headers, $0$ disagreements.

---

### 12. An unverifiable negative claim about other people's work
**Location:** `paper/main.tex:1130–1132`

**Claim:** "Prior to this, the 2026 pool's reducibility had **never** been
independently verified: the authors' own verification was external to the
released code."

**Problem:** the first half is a universal negative about the world that no
artifact in this repository can support, and it is asserted flatly rather than
hedged (contrast `main.tex:191–192`, "as far as we can determine", and
`main.tex:197`, "We have found no prior claim of ...", which are the right
register). The second half is a checkable statement about the released
repository and should be kept, with a pointer.

**Severity:** SHOULD-FIX

**Suggested replacement:**
> We are not aware of any prior independent verification of the 2026 pool's
> reducibility; the released \texttt{computer-checks} repository
> (\art{third\_party/GIT\_PINS.txt}, commit \texttt{6cb85666}) consumes the pool
> as an input and contains no reducibility checker of its own.

---

### 13. The "independent" C++ confirmation of the low-degree wheel counts has no stored output, and Appendix A points back at our own sweep
**Location:** `paper/main.tex:639–641`; Appendix A `main.tex:1969–1971`

**Claim (639–641):** "**Independently**, running the released C++ with
\texttt{--enum\_wheels -d 5} and \texttt{-d 6} returns exactly $580$ and
$2{,}466$ unblocked wheels, matching our generation wheel for wheel."

**What the artifact table says:** the corresponding Appendix A cell reads
"released C++ \texttt{--enum\_wheels -d 5}, \texttt{-d 6}; **same counts in the
low-degree sweep above**" — i.e. it cites *our own* sweep as the evidence for the
C++ side. No `-d 5` or `-d 6` log exists anywhere under `results/` or
`third_party/computer-checks/log/` (the stored wheel logs are `wheels_d7`
through `wheels_d11` only). The 580/2,466 figures are in our own
`results/steinberger/lowdeg_rows_main.json` and
`lowdeg_refinement_check.json`, which is exactly the thing the C++ run is
supposed to corroborate. As recorded, the corroboration is circular.

**Severity:** SHOULD-FIX

**Suggested action:** re-run the released binary with `--enum_wheels -d 5` and
`-d 6`, store its stdout as `results/steinberger/enum_wheels_d5.log` and
`_d6.log`, and cite those files in Appendix A. Until then, replace lines 639–641
with:
> Independently, running the released C++ with \texttt{-{}-enum\_wheels -d 5} and
> \texttt{-d 6} returns exactly $580$ and $2{,}466$ unblocked wheels, matching our
> generation wheel for wheel (\art{results/steinberger/enum\_wheels\_d\{5,6\}.log}).

---

### 14. Appendix A cites two stats files for the eight-variant table that in fact contain a different variant
**Location:** `paper/main.tex:1950–1953`; affects `main.tex:715–717`

**Claim:** "$8$-variant LP matrix (Table~\ref{tab:lpvariants}) &
\art{results/steinberger/lp\_variants\_summary.json},
\art{results/steinberger/lp\_control\_stats.json},
\art{results/steinberger/lp\_main\_stats.json}".

**What the artifacts say:** `lp_variants_summary.json` does back all eight rows
exactly (verified). But `lp_control_stats.json` and `lp_main_stats.json` on disk
both carry `"conservative": true` and `n_rows_dedup` of **4,321** and **52,400** —
they are the `--conservative` diagnostic run (Table `tab:lpvariants` rows 11–12),
not the headline `3,511`/`48,509` run. The later run overwrote the earlier one.

A consequence: the headline row breakdown at `main.tex:715–717` ("$d{=}7$:
$40{,}257$; $d{=}8$: $8{,}070$; $d{=}9$: $93$; $d{=}10$: $3$; $d{=}5$: $26$;
$d{=}6$: $60$") is in **no** stored artifact. The stored
`lp_main_stats.json` gives `{'7': 44148, '8': 8070, '10': 3, '9': 93, '5': 26,
'6': 60}` — the conservative run. The headline $d{=}7$ figure is only recoverable
arithmetically as $48{,}509 - 8{,}070 - 93 - 3 - 26 - 60 = 40{,}257$.

**Severity:** SHOULD-FIX

**Suggested action:** write the headline run's stats to distinct filenames
(`lp_control-low_stats.json` / `lp_main-low_stats.json`) so the four variants do
not overwrite each other, and correct the Appendix A cell to:
> \art{results/steinberger/lp\_variants\_summary.json} (all eight rows);
> \art{lp\_main-low\_stats.json} (headline row breakdown by hub degree);
> \art{lp\_control-exact\_stats.json}, \art{lp\_main-exact\_stats.json},
> \art{lp\_control\_stats.json}, \art{lp\_main\_stats.json} (the
> \texttt{-{}-exact-only} and \texttt{-{}-conservative} diagnostics)

---

### 15. "C-reducibility is strictly weaker" contradicts the definition given two lines earlier
**Location:** `paper/main.tex:318–321`

**Claim:** "$K$ is \emph{C-reducible} if the same holds after contracting a
**nonempty** \emph{contract} $X$ of edges. C-reducibility **is strictly weaker**:
\S\ref{sec:cvsd} exhibits catalog configurations that are C-reducible but not
D-reducible with fewer interior vertices than $f(r)$."

**Problem:** under the stated definition (contract required nonempty), a
D-reducible configuration is *not* automatically C-reducible, so the two classes
are formally incomparable, not nested — "strictly weaker" is a claim about
containment that the definition denies. This matters because Theorem 4.1 is
D-scoped and §4.4 is the place a referee will check the scoping. The paper's own
data confirms the classes are not nested as defined: `main.tex:1111–1114` reports
$249$ configurations that are D-reducible and $384$ that are "C-reducible via a
nonempty published contract and are \emph{not} D-reducible".

**Severity:** SHOULD-FIX

**Suggested replacement (319–321):**
> $K$ is \emph{C-reducible} if the same holds after contracting a contract $X$ of
> edges; the published catalogs record a nonempty $X$ exactly for those
> configurations that are not already D-reducible, so we say ``C-reducible'' for
> the union (empty $X$ included) and ``C-reducible, not D-reducible'' for the
> proper part. Reducibility in the C-or-D sense is strictly weaker than
> D-reducibility: \S\ref{sec:cvsd} exhibits catalog configurations that are
> C-reducible but not D-reducible with fewer interior vertices than $f(r)$.

---

### 16. Theorem 4.1's epistemic grade changes between its statement and §9
**Location:** `paper/main.tex:861` (`\begin{theorem}[Proven, exhaustive]`) vs
`paper/main.tex:1897–1901`

**Claim (§9):** "The finite content of Theorem~\ref{thm:fr} is a replay of
$10{,}319$ configuration checks. That is within reach of a proof assistant ... and
it would upgrade the theorem **from ``certified'' to ``proven''** in the strongest
available sense."

**Problem:** the theorem is labelled `[Proven, exhaustive]` at line 861 and is
listed under **Proven** throughout §1. §9 then calls it "certified". Given that
the paper's whole framing rests on the three-grade distinction, an inconsistency
in the grade of the paper's cleanest result is exactly what a referee will fix
on. (Substantively §9 is right that the finite content is a machine replay; §1.1's
definition of **Proven** explicitly admits "a finite exhaustive case analysis
whose completeness argument is given", which is what §4.2 provides, so keeping
`[Proven, exhaustive]` is defensible — but then §9 must not contradict it.)

**Severity:** SHOULD-FIX

**Suggested replacement (1899–1901):**
> That is within reach of a proof assistant given Gonthier's formalisation
> \cite{gonthier2008} of the reducibility machinery, and it would replace the
> $10{,}319$-check replay --- currently the one part of Theorem~\ref{thm:fr}'s
> completeness argument that is machine-executed rather than machine-verified ---
> with a checked object.

---

### 17. "Four verified structural facts" oversells contribution (C4)
**Location:** `paper/main.tex:42`; cf.\ `main.tex:176–177`

**Claim:** "We report **four verified structural facts** obtained by re-deriving
these proofs computationally".

**What the paper says elsewhere:** §1.3 item 4 — "**The sharp cap is a
conjecture**, not a theorem, and the threshold half of the coloring-mass law is
corpus-supported only." (C4) as summarised in the abstract (lines 80–84) bundles
three proven statements (wheel closed form, the $11\cdot2^{r+k-7}$ cap, $\gamma=3/2$
at $k=2$, the obstruction theorem) with a conjecture and a corpus-supported
threshold. Calling the bundle a "verified structural fact" contradicts §1.3.

**Severity:** SHOULD-FIX

**Suggested replacement (line 42):**
> theorem itself is largely unexamined. We report three verified structural facts
> and one framework of proven bounds around an explicit conjecture, all obtained
> by re-deriving

---

### 18. "We replaced a legacy C oracle" is not what happened
**Location:** `paper/main.tex:75–76` (abstract), `paper/main.tex:174` (C3)

**Claim (abstract):** "Along the way we **replaced** a legacy C oracle that aborts
partway through Steinberger's set".

**What §5.2 actually reports** (`main.tex:1140–1149`): `reduce_stein` aborts at
configuration 783 with SIGABRT, and "the full-set verification of
$\mathcal{U}_{2822}$ **rests on our checker against the published headers, not on
that binary**; the binary corroborates the first $783$ and then dies." Nothing
replaced the oracle: the fallback is the paper's own Python checker, which is not
an independent oracle for the remaining 2,039 configurations. "Replaced" invites
the reader to think a working substitute oracle exists.

**Severity:** SHOULD-FIX

**Suggested replacement (abstract, 75–76):**
> Along the way we found that the legacy C oracle aborts $783$ configurations
> into Steinberger's set, so that our own checker against the published headers
> carries the remainder unaided,

and correspondingly at line 174: "documented where a legacy C oracle aborts and
what carries the verification past it".

---

### 19. "Jacobsen–Salas–Sokal" is cited to a two-author entry
**Location:** `paper/main.tex:1867–1869`; `paper/refs.bib:111–120`

**Claim:** "The **Jacobsen--Salas--Sokal** Temperley--Lieb machinery
\cite{jacobsen2006}".

**What the bib says:** `author = {Jacobsen, Jesper Lykke and Salas, Jes{\'u}s}` —
two authors. `jacobsen2006` is paper IV of the Jacobsen–Salas series; Sokal is a
co-author of other papers in that series but not of this entry as recorded, and
the entry's venue/volume/pages (J. Stat. Phys. **122** (2006) 705–760) cannot be
confirmed from anything in `third_party/`.

**Severity:** SHOULD-FIX

**Suggested replacement:** either write "The Jacobsen--Salas transfer-matrix
machinery \cite{jacobsen2006}", or add the Salas–Sokal / Jacobsen–Saleur–Sokal
paper that actually carries the Temperley--Lieb formulation and cite both. Also
confirm volume/pages from a canonical source and record it.

---

### 20. Three statistical-physics attributions rest on unpinned sources and carry no locator
**Location:** `paper/main.tex:1465–1469`, `main.tex:1496–1498`

**Claims:**
1. "the standard correlation-decay techniques \cite{salas1997} need $q\ge11$ **there**" (i.e. on the triangular lattice);
2. "$4/3 = (q-2)^2/(q-1)$ at $q=4$ is **Shrock--Tsai's \emph{lower} bound** for the triangular-lattice entropy \cite{shrock1997}";
3. "Baxter's ground-state entropy of the $4$-state antiferromagnetic Potts model on the triangular lattice is $\approx 1.4610$ per site \cite{baxter1987}".

**Status:** none of `salas1997`, `shrock1997`, `baxter1987`, `moore2000` is
pinned in `third_party/` (only the four 4CT e-prints and `plantri` are), and none
of them is annotated in Appendix A. Claims 1 and 2 in particular are specific
attributions of a *numerical threshold* and a *named bound* — exactly the kind of
statement a statistical-physics referee will check first, and exactly the kind
this paper's own methodology says must be sourced to a line. Claim 3 is used
quantitatively (to predict that the $P$-form must fail in the bulk), and the
paper's own fitted per-site entropies $1.541/1.563$ exceed it without comment.

**Severity:** SHOULD-FIX (unverifiable as it stands)

**Suggested action:** add a theorem/equation locator to each — e.g.
"\cite[Thm.~3.1]{salas1997}", "\cite[eq.~(1.8)]{shrock1997}",
"\cite[\S4]{baxter1987}" — and add an Appendix A row recording where each was
checked. Add one sentence after line 1503 noting that the fitted boundary-inclusive
entropies $1.541/1.563$ exceed Baxter's bulk $1.4610$ as expected for finite
disks with a free boundary.

---

### 21. §7.6 says the surviving mined rule "became Theorem 4.1"; §8.2 says it became one case of it
**Location:** `paper/sec_ml.tex:324–327`; cf.\ `paper/main.tex:1782–1783`

**Claim (§7.6):** "the rule-mining process that produced the candidate rules
discussed in Section~\ref{sec:negative} -- of which **the surviving rule, in its
exhaustively verified form, became Theorem~\ref{thm:fr}**."

**What §8.2 says:** "``$r=11$ and $k \le 6$ implies not D-reducible'' ... is the
statement that became **the $r=11$ case** of Theorem~\ref{thm:fr}." Theorem 4.1
covers $r=8,\dots,13$; the mined rule is one of its six rows, and §8.2 goes on to
say the mutation evidence for it "should nevertheless be discounted almost
entirely". §7.6 as written credits the ML line with the whole theorem — precisely
the reading §7 exists to prevent.

**Severity:** SHOULD-FIX

**Suggested replacement (`sec_ml.tex:324–327`):**
> ... to the rule-mining process that produced the candidate rules discussed in
> Section~\ref{sec:negative} -- of which the one surviving rule, ``$r=11$ and
> $k\le6$ implies not D-reducible'', became the $r=11$ case of
> Theorem~\ref{thm:fr} once it was established exhaustively by the
> \texttt{plantri} sweep (and, as \S\ref{sec:negative} records, the mutation
> evidence for it is worth almost nothing).

---

### 22. "Three reported mechanistic findings" is followed by four bullets
**Location:** `paper/sec_ml.tex:267–302`

**Claim:** "We then reran each of the paper's **three** reported mechanistic
findings against our own checkpoint." The `itemize` that follows has four items:
causal ablation, attention statistics, linear probes, length generalization.

**Severity:** SHOULD-FIX

**Suggested replacement (line 268):** "paper's four reported findings against our
own checkpoint." — or, if length generalization is not one of the source's
*mechanistic* findings, say so explicitly: "the paper's three reported
mechanistic findings, plus its length-generalization result, against our own
checkpoint."

---

### 23. The ring-8/9/10 ML corpus sizes match neither each other nor the committed data
**Location:** `paper/sec_ml.tex:62–63`, `sec_ml.tex:128`, `paper/main.tex:1709–1714`

**Claims:** §7.1 — "the corpora held $1{,}162 / 1{,}446 / 1{,}746$ configurations
at $r=8,9,10$"; §7.3 — "an enlarged ring-10 corpus ($3{,}269$ configurations)";
§6 — "the ring-$8$ trace corpus grew from $1{,}162$ to $1{,}736$ records".

**What the artifacts say:** `wc -l` on the committed files gives
`data/v2/traces_r8.jsonl` = **1,736**, `traces_r9.jsonl` = **2,979**,
`traces_r10.jsonl` = **4,257**. So none of the three §7.1 numbers matches the
repository; the ring-10 corpus is quoted as 1,746, then 3,269, then is actually
4,257 on disk; and §6 flags only the ring-8 drift, though rings 9 and 10 drifted
further (1,446→2,979 and 1,746→4,257). The `code_index` sizes 1,094 / 3,281 /
9,842 in the same sentence **do** match the artifacts exactly, which makes the
mismatch harder to spot rather than easier.

**Severity:** SHOULD-FIX

**Suggested replacement (`sec_ml.tex:61–63`):**
> ... carrying full per-round survivor sets. Every model below was trained on a
> snapshot: at training time the corpora held $1{,}162 / 1{,}446 / 1{,}746$
> configurations at $r=8,9,10$ (the committed files have since grown, by
> continued generation, to $1{,}736 / 2{,}979 / 4{,}257$; the ring-$10$
> second-pass run of \S\ref{sec:ml-boundary} used a $3{,}269$-configuration
> snapshot). Ring-colouring code-index sizes are $1{,}094 / 3{,}281 / 9{,}842$
> respectively and are unchanged.

and extend `main.tex:1710–1713` to say all three corpora drifted, not just ring 8.

---

### 24. "$591$/$633$" appears once, unexplained
**Location:** `paper/main.tex:1907–1908`

**Claim:** "a minimal $U$ in the wheel-based schema is \emph{not} comparable to
RSST's **$591$**/$633$ (axle-based, C-reducibility with contracts, ring $\le14$)."

**Problem:** $591$ appears nowhere else in the paper and is not defined. Every
other mention of the RSST set — abstract, §1.1, §1.3 item 6, Table
`tab:catalogs`, §5.1 — says $633$. (It is presumably the reduced count from a
later RSST note, but a reader has no way to know.)

**Severity:** SHOULD-FIX

**Suggested replacement:** drop it — "is \emph{not} comparable to RSST's $633$
(axle-based, ...)" — or define it on first use with a citation.

---

### 25. Bibliography hygiene
**Location:** `paper/refs.bib`

* `tao2023machine` (lines 163–168): key says 2023, `year = {2025}`, and the real
  venue (Notices AMS **72**(1), 6–13) is buried in a `note` on an `@misc`.
  BibTeX `plain` will render this as an unsourced miscellaneous item.
* `buzzard2024` (170–175): same pattern — Bull. AMS **61**(2), 211–224 in a
  `note` on an `@misc`.
* `davies2021signature` (190–198): key says 2021, `year = {2024}`.
* `steinberger2010` (55–64): key says 2010, `year = {2009}` (the e-print year),
  with the 2010 TAMS publication in a `note`. Defensible, but inconsistent with
  how `rsst-reduce`/`rsst-discharge` are handled.
* Four entries are never cited and will be silently dropped by `plain`:
  `birkhoff1946`, `farkas1902`, `gukov2021`, `tutte1954`. `main.blg` confirms
  only 20 of the 24 entries are used. **`farkas1902` in particular ought to be
  cited** — §3 and Appendix B are built entirely on a Farkas certificate and the
  lemma is never attributed.
* `rsst-reduce` / `rsst-discharge`: the pinned sources (`reduce.tex`,
  `discharge.tex`) contain no `\author` block, so those author lists come from
  arXiv metadata rather than from the pinned artifact. The ancillary-file claims
  in both notes **do** check out (`anc/` contains `reduce.c` +
  `unavoidable.conf`, and `discharge.c` + `rules` + `present7`–`present11`
  respectively), and `steinberger2010`'s title matches `4c.tex:90` verbatim.
* Venues I could not confirm from any pinned source or in-repo artifact, and
  which should be checked against a canonical index before submission:
  `jacobsen2006`, `shrock1997`, `moore2000`, `salas1997`, `baxter1987`,
  `brinkmann2007`, `davies2021signature`, `gukov2021`, `tutte1954`,
  `birkhoff1946`, `farkas1902`.

**Severity:** SHOULD-FIX

**Suggested action:** convert `tao2023machine` and `buzzard2024` to `@article`
with explicit `journal`/`volume`/`number`/`pages`; align every key's year digits
with its `year` field; cite `farkas1902` at the first use of "Farkas certificate"
(`main.tex:397` region) and delete the other three uncited entries.

---

### 26. The lemma that carries Theorem 3.1's soundness has only a proof sketch
**Location:** `paper/main.tex:500–524` (Lemma 3.2, Monotonicity); also
`main.tex:1263–1282` (Bridge Lemma, "proven") and `main.tex:1328–1357`
(Theorem 4.6, "[Proven]")

**Problem:** Lemma 3.2 is what licenses using leaves observed under $x_0$-pruning
as constraints valid for all $x\ge0$; without it, Theorem 3.1's row set is not a
relaxation of anything and the certificate proves nothing about the schema. It is
given a four-part `\begin{proof}[Proof sketch]`. The same applies to the Bridge
Lemma (labelled "proven") and Theorem 4.6 (labelled "[Proven]"), both of which
also have only sketches. Labelling a result **Proven** — the paper's strongest
grade, explicitly defined in §1.1 — while supplying a sketch is the kind of
mismatch this paper's own methodology section is about.

**Severity:** SHOULD-FIX

**Suggested action:** promote Lemma 3.2's sketch to a full proof (each of (a)–(d)
is one short paragraph and (c) is the only one needing care), or, if the
supporting measurement is what carries part (c), say so in the statement: e.g.
after "For every observed leaf $L$ and every $x\ge0$" add "(the monotonicity of
\texttt{upper\_bound\_of\_charge} in part~(c) is argued from the source, and
measured on $2{,}145$ parent/child pairs; see \S\ref{sec:lp-scope} item 5)". For
the Bridge Lemma and Theorem 4.6, either complete the proofs or relabel the
environments as "[Proven; sketch given]".

---

## NITs

**27.** `main.tex:405` — the quotation "Figure \texttt{fig:rules} shows 84 rules
since precisely two, the first and fourth last, are symmetric under the
reflection" is entirely on **line 635** of the pinned source; line 636 is the
GitHub-repository footnote. Cite "source line 635". (Line 634 is where the "43
rules" figure appears, if a second locator is wanted.)

**28.** `main.tex:408–409` — "the paper notes the rule set is the same as
Steinberger's $42$ except that **his** $12$th and $13$th are merged". The source
(line 637) says "our 12th and 13th rules are considered as a single rule in
\cite{steinberger2010unavoidable}" — it is the *2026* paper's 12th and 13th that
Steinberger treats as one. Replace with "except that its $12$th and $13$th rules
are a single rule in Steinberger's set".

**29.** `main.tex:1081–1082` — "written from the mathematics of
\cite{rsst-reduce} (the \texttt{reduce.tex} write-up, in particular **its**
Theorem 3.2 machinery)". `reduce.tex:144` says it "is to provide more details
about the proof of [RSST 1997, theorem (3.2)]" — theorem (3.2) belongs to
\cite{rsst1997}, not to `reduce.tex`. Replace "its Theorem 3.2 machinery" with
"in particular its expansion of \cite[Theorem (3.2)]{rsst1997}".

**30.** `main.tex:777–779` — "those **four** rows come from wheels
\texttt{d7\_3358}, \texttt{d7\_3372}, \texttt{d7\_3376} --- precisely **three** of
the wheels whose job the \emph{C++} aborted". Correct (`d7_3358` contributes
leaves `_2133` and `_2134`), but the 4-vs-3 will read as a typo. Add
"(\texttt{d7\_3358} contributes two leaves)".

**31.** `main.tex:1370–1371` — "$f(r) \ge \lceil 0.26303\,r - 0.1367\rceil$".
Recomputing $7 - \log_2 12.79 - \log_2 11$ gives $-0.1363$, not $-0.1367$. No
table entry changes (the nearest margin, $r{=}12$, is $3.020$).

**32.** `sec_ml.tex:224–225` — "The headline boundary result reported in\n of
\S\ref{sec:ml-boundary} was therefore ..." — stray "in".

**33.** `sec_ml.tex:266–267` — "the same headline accuracy the paper reports:
$0.9950$ greedy exact-match on **a held-out instances** of size $n=13$" —
"a held-out set of instances".

**34.** `main.tex:1713–1714` — "Ring $8$ carries none of the results reported in
\S\ref{sec:ml}, which are at rings $9$ and $10$." But `sec_ml.tex:50–63` reports
a ring-8 specialist and its corpus size as part of the D1-v2 design, and the D1
corpus spans rings 6–16. Narrow to: "No result reported in \S\ref{sec:ml} depends
on the ring-$8$ D1-v2 model; the boundary and extraction results are at rings $9$
and $10$."

**35.** `main.tex:602–608` — "and exhaustively on all $625$ refinements of a
$4$-slot necklace". This is real, but it lives in
`tests/test_lowdeg_refinement_check.py:26,48`, not in
`results/steinberger/lowdeg_refinement_check.json` (which stores only the
`{"samples": 2000, "disagreements": 0}` field per necklace). Add the test file to
the Appendix A row at `main.tex:1965–1968`.

**36.** `results/mass-law/arc-profile.md:3` records that the BFS-link scheme hit a
scheme-integrity failure on **1 of the 59,142** records ("Scheme succeeded ... on
59141"). §4.7/§8.5 quote the step statistics as if the sweep were complete.
Add "(one record of $59{,}142$ failed a scheme-integrity check and is excluded;
see \art{results/mass-law/arc-profile.md})" at `main.tex:1412`.

**37.** `main.tex:28–30` — the author block still reads "(draft --- author list to
be completed)". Obvious, but it must not survive to submission, and (see B1) the
paper's own standard for author lists is now on record.

**38.** `main.tex:1450–1451` — "The Bridge-Lemma fibre $P(S,4)/(24a)$ --- two
colour-inequivalent tri-colourings sharing a ring restriction ---" is a sentence
fragment used as a definition. Rewrite as "The Bridge-Lemma fibre $P(S,4)/(24a)$
--- the average number of colour-inequivalent tri-colourings per ring-colouring
class ---".

---

## Verdict

**Not submission-ready, but close, and the gap is prose and citation discipline
rather than computation.** Every substantive numerical claim I re-derived held
up: both Farkas certificates re-verify from source with `tools/verify_farkas.py`
(multipliers, $y^\top b$, column support, IIS irreducibility all exact), the
entire $f(r)$ sweep reproduces from the manifests to the last digit, the mass-law
frontier and lattice-disk tables reproduce exactly from $W(r)(4/3)^{k-1}$, the
236/215/21 false-positive accounting is exactly right, and all four verbatim
quotations from the pinned e-prints are faithful, down to the line numbers. That
is an unusually clean artifact record, and the paper deserves credit for the
Appendix A discipline that made this audit possible at all. What is not ready is
the layer of statements *about* those computations: the abstract claims header
agreement against a catalog whose files have no such header, the headline theorem
is glossed in a way that makes it vacuous, a displayed general formula is simply
false, and the paper cites the work it analyses under a truncated author list
while asserting in the same entry that the list came from the pinned source it
contradicts. Those are the failures a referee sees first, and each of them
undercuts precisely the epistemic care that is the paper's stated contribution.

**Top three fixes, in order:**

1. **Fix the citations (B1, B6).** Give `arXiv:2603.24880` its six real authors
   from the pinned `\author` block, and correct the note that falsely claims this
   was already done. Pin `arXiv:2511.12421` and give it a real author list, or
   recast §7.5 so it does not attribute specific numbers to an unpinnable source.
   These cost an hour and are the difference between a careful paper and one that
   looks careless about the very literature it is auditing.
2. **Restate Theorem 3.1 and downgrade the abstract's verb (B3, B5).** Replace
   the "hypothetical minimum counterexample" gloss with the unblocked-cartwheel
   formulation, and change "we prove" to "we certify" with a one-clause pointer
   to §1.3. The result is genuinely strong; stating it in terms of objects the
   certificate actually constrains makes it *more* defensible, not less.
3. **Fix B2 and B4, then sweep the artifact table.** Correct the header-agreement
   claim (abstract and Table 5.1 caption) and the $(\log_2\beta-1)/\log_2\gamma$
   formula; then work through findings 11, 13, 14 and 35, which are all the same
   defect — Appendix A pointing at a file that does not contain the number, or at
   our own output in place of the independent one. Appendix A is the paper's
   strongest claim to trustworthiness, so a cell that does not deliver costs more
   than the number it fails to support.
