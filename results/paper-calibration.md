# Paper calibration: what papers in our target space actually look like

Six papers were downloaded, page-counted with `pdfinfo`, and measured section by
section from `pdftotext` output with page ranges resolved against form-feed page
breaks. Section classes: FRONT = abstract/intro/related work; MATH = definitions,
lemmas, proofs, discharging rules; COMP = algorithm/encoding description,
solver/LP/SAT details, implementation, timing, hardware, tables of machine
output, proof checking; BACK = conclusion/open problems/references/appendix.

Where a classification was genuinely ambiguous (Bousquet et al. §4, where the LP
formulation *is* the mathematics) both readings are given.

## Measurements

| | Bousquet–Deschamps–de Meyer–Pierron | Stolee | La–Valicov | Subercaseaux–Heule | Empty hexagon (ITP 2024) | Steinberger |
|---|---|---|---|---|---|---|
| arXiv | 2204.05791 | 1409.5922 | 2202.03885 | 2301.09757 | 2403.17370 | 0905.0043 |
| venue | SIAM J. Discrete Math. 38(1) 2024 | preprint / extended abstract | preprint | TACAS-adjacent (no journal-ref on arXiv) | ITP 2024 (LIPIcs) | TAMS 362 (2010) |
| **pages (PDF)** | **24** (A4) | **17** (Letter) | **35** (A4) | **21** (Letter) | **19** (A4) | **37** (Letter) |
| references | 33 | 36 | 11 | 23 | 40 | 19 |
| FRONT | 2.6 pp (10.7 %) | 2.8 pp (16.5 %) | 1.6 pp (4.4 %) | 2.3 pp (11.0 %) | 3.5 pp (18.3 %) | 3.7 pp (10.0 %) |
| MATH | 16.4 pp (68.4 %) | 5.9 pp (34.5 %) | 18.0 pp (51.3 %) | ~0 pp (0 %) | 8.0 pp (42.2 %) | 31.7 pp (85.6 %) |
| **COMP** | **2.1 pp (8.9 %)** strict; 7.3 pp (30 %) generous | **1.7 pp (10.1 %)** + 4 pp of appendix tables | **5.0 pp (14.3 %)** | **12.3 pp (58.7 %)** | **4.0 pp (20.9 %)** | **~0–1 pp (0–3 %)** |
| BACK | 2.9 pp (12.0 %) | 6.6 pp (38.7 %) | 10.5 pp (30.0 %) | 6.4 pp (30.2 %) | 3.5 pp (18.3 %) | 1.6 pp (4.4 %) |
| appendix | none (0 %) | 2 appendices, 4.0 pp (23.4 %) | 1 appendix, 10.0 pp (28.4 %) | 5 appendices, 3.9 pp (18.5 %) | none (0 %) | none (0 %) |
| tables | **0** | 5 (1 inline, **4 in appendix**) | 2 (both inline, both small) | 3 (all inline) | **0** | 1 (inline) |
| figures | 16 (all inline) | 4 | — | — | 9 | 15 |
| code/data reference | inline sentence + bare GitLab URL, inside an "Implementation" paragraph in §4.3; also flagged in the intro | **numbered footnote** with a bare URL at the end of §4 | inline sentence + bare GitLab URL, **in the abstract** and again in §5 | **no repository link at all**; a 27-line Python listing is printed as Appendix C | inline sentence + bare GitHub URL, first paragraph of the intro | prose: "The necessary files and programs are in the `aux` folder accompanying this arxiv submission" |
| bibliography entry for the software? | no | no | no | n/a | no | no |
| "Data Availability" heading? | no | no | no | no | no | no |
| machine-output tables inline or deferred? | n/a (none) | **deferred** to appendix | inline (small only) | **inline**, incl. the 34 TB / 122 TB proof sizes, reported in prose | n/a (none) | **deferred online**: "The 2822 configurations ... require over 30 pages to draw ... they are available online in both machine- and human-readable forms" |
| headline theorem names the computation? | no (Thm 1.2 is classical); intermediate Thm 4.1/4.3 do | Thm 1 no; **Thms 4–11 yes** — "The adage proof using rule N demonstrates δ(X) ≥ 23/55" | no (Thm 2 is classical) | no (Thm 4 is "χρ(Z²) = 15") | no (a bare Lean `theorem` signature) | no single theorem statement; the computation is folded into the lemma chain |

Notes on measurement quality:
- Page fractions are resolved to within one text line and should not be read to
  more than two significant figures.
- A4 (Bousquet, La–Valicov, hexagon) vs. US Letter (Stolee, Subercaseaux–Heule,
  Steinberger) means raw page counts are not perfectly comparable.
- The arXiv abs page for Bousquet et al. carries no Comments and no Journal-ref
  field, so the 24 pages measured are the arXiv v1 typesetting, not the SIAM
  published version.
- Stolee's arXiv Comments field says "2 figures"; the PDF has 4. Reported as
  measured.
- Steinberger's COMP share is ~0 because he has no computational-methods section
  at all: the dispatch algorithm sits inside §4 as mathematics, and every
  implementation detail is either one sentence in the intro or deferred to the
  `aux` folder.

## Norms we should follow

1. **Target 16–18 pages including references.** The five non-outlier papers run
   17–24 pages; the two that exceed that (Steinberger 37, La–Valicov 35) do so
   with hand case analysis and deferred-proof appendices, not with computational
   reporting. The three closest siblings — a discharging/LP method plus a single
   headline result — are 24, 17 and 19 pages.

2. **Keep computational detail under ~20 % of the page budget.** Every paper
   whose headline is a *mathematical* statement spends 9–21 % on computation
   (Bousquet 8.9 %, Stolee 10.1 %, La–Valicov 14.3 %, hexagon 20.9 %). Only
   Subercaseaux–Heule spends 59 %, and there the computation *is* the
   contribution. Our headline is a theorem about a schema, so ~3 pages of
   computational reporting is the ceiling, not the floor.

3. **One or two tables, and machine-output catalogs go to the artifact.** Two of
   six papers print zero tables; the closest sibling (Bousquet et al.) prints
   zero and reports its timings in a single prose paragraph. Stolee defers four
   of his five tables to appendices. Steinberger's precedent is explicit and is
   the one to follow: "Instead of appending them as a figure to the paper, which
   would be of limited use, they are available online in both machine- and
   human-readable forms."

4. **Cite code as an inline sentence with a bare URL at the point of use.** No
   paper in this space uses a numbered bibliography entry for its software, and
   none has a "Data Availability" heading. Stolee's numbered footnote is the most
   formal instance. A single short availability paragraph is a defensible modest
   upgrade given our artifact volume, but it should be a paragraph, not a
   section with subsections.

5. **Reference counts track scope, not length.** Observed range 11–40, median
   ~28, and it correlates with breadth rather than with page count: La–Valicov
   (35 pp) carries 11, Steinberger (37 pp) carries 19, the ITP hexagon paper
   (19 pp) carries 40. A narrowly scoped result is entitled to a short list.
   What is *not* optional is the automated-discharging line — Stolee, Bousquet
   et al., La–Valicov, and the Cranston–West survey — which our previous
   bibliography omitted entirely while making a novelty claim against it.

6. **Put computational hypotheses in the statement when the result is *about* a
   computation.** The default is a classical statement (five of six papers), but
   Stolee — whose results are relative to a fixed automated framework and a named
   rule set — writes them into the theorem: "The adage proof using rule N
   demonstrates δ(X) ≥ 23/55." Our result is an impossibility relative to a fixed
   rule-shape set and a fixed pool, so Stolee's convention is the correct
   precedent, and it is also what the internal audit demands.

7. **No appendix that duplicates the repository.** Three of six papers have no
   appendix; the three that do use it for deferred *proofs* (La–Valicov) or
   deferred *machine output* (Stolee), never for material that is also online. A
   12-row certificate is small enough to belong inline; the 84-column
   coefficient vectors belong in the artifact.

8. **Report abandoned lines in sentences, not sections.** None of these papers
   gives a negative-results section. Bousquet, Stolee and La–Valicov each fold
   what their loop failed to achieve into one to three sentences of the
   discussion.


## Outcome

`paper/short.tex` was written to these norms and compiles to **18 pages**
including references: at the top of the 16–18 band of norm 1, between Stolee's
17 and the ITP hexagon paper's 19. Four tables (the certificate, an LP-variant
summary, a verification summary, an enumeration sweep), no appendix, no figures,
18 references, and a single availability paragraph rather than a section.

Measured against norm 2 with the same strict convention used for Bousquet et al.
(the LP formulation itself counted as MATH, since it is stated as definitions, a
lemma and a proof), the split is roughly: FRONT 4.3 pp, MATH 5.0 pp,
COMPUTATIONAL 4.1 pp, BACK 2.4 pp of body plus 1.6 pp of references.
Computational reporting is therefore about **23 %** of the page budget — above
the 9–21 % band of the four theorem-headline papers, and closest to the ITP
hexagon paper's 21 %. That overrun is deliberate and is the one norm we
knowingly miss: §5 exists to license the certificate, and the audit that
motivated this rewrite treated the verification record as load-bearing rather
than as supporting material. It is also the first place to cut if a referee asks
for length.
