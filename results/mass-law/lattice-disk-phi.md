# |Phi| on synthetic lattice disks: does the SHARP CAP itself survive?

`tools/lattice_disk_entropy.py` found that the **P-form** of the sharp cap
fails on triangular-lattice disks. That is a statement about `P(S,4)/24`,
not about `a = |Phi(K)|`. This file computes `a` directly on the same disks.

Reproduce: `PYTHONPATH=src .venv/bin/python tools/lattice_disk_phi.py`.

## 0. Self-validation of the |Phi| enumerator against the repo's stored `a`

| ident | r | k | stored a | computed |Phi| | match |
|---|---|---|---|---|---|
| `gen-r7-n12-770` | 7 | 5 | 45 | 45 | yes |
| `gen-r10-n14-322` | 10 | 4 | 352 | 352 | yes |
| `gen-r8-n12-171` | 8 | 4 | 72 | 72 | yes |
| `gen-r9-n11-1` | 9 | 2 | 106 | 106 | yes |
| `gen-r6-n14-294270` | 6 | 8 | 25 | 25 | yes |
| `fr-r9-n10-0` | 9 | 1 | 85 | 85 | yes |
| `gen-r11-n14-36` | 11 | 3 | 551 | 551 | yes |
| `gen-r11-n14-44` | 11 | 3 | 551 | 551 | yes |
| `gen-r11-n14-49` | 11 | 3 | 576 | 576 | yes |
| `gen-r7-n14-58434` | 7 | 7 | 56 | 56 | yes |
| `gen-r10-n14-426` | 10 | 4 | 296 | 296 | yes |
| `gen-r7-n13-6179` | 7 | 6 | 47 | 47 | yes |

**12/12 exact matches.** The enumerator computes the same
object as `fourcolor.reduce`'s `n_extendable`.

## 1. |Phi| versus the sharp cap

`cap = ((2^r+2)/6)*(4/3)^(k-1)`; `gamma_a = (a/W(r))^(1/(k-1))` is the
realised per-interior-vertex base (compare 4/3 = 1.3333).

| disk | r | k | n | a = &#124;Phi&#124; | cap | a/cap | gamma_a | seconds |
|---|---|---|---|---|---|---|---|---|
| HEX R=1 | 6 | 1 | 7 | 11 | 11.0 | 1.0000 | -- | 0.0 |
| HEX R=2 | 12 | 7 | 19 | 2756 | 3837.5 | 0.7182 | 1.2618 | 0.2 |
| HEX R=3 | 18 | 19 | 37 | SKIPPED (n > 33) | | | | |
| HEX R=4 | 24 | 37 | 61 | SKIPPED (n > 33) | | | | |
| TRI m=3 | 6 | 1 | 7 | 11 | 11.0 | 1.0000 | -- | 0.0 |
| TRI m=4 | 9 | 3 | 12 | 140 | 152.3 | 0.9193 | 1.2784 | 0.0 |
| TRI m=5 | 12 | 6 | 18 | 2263 | 2878.2 | 0.7863 | 1.2707 | 0.2 |
| TRI m=6 | 15 | 10 | 25 | 41971 | 72740.1 | 0.5770 | 1.2543 | 5.6 |
| TRI m=7 | 18 | 15 | 33 | 853124 | 2452078.1 | 0.3479 | 1.2365 | 294.6 |
| TRI m=8 | 21 | 21 | 42 | SKIPPED (n > 33) | | | | |
| ICOSA icosa-minus-[0] | 5 | 6 | 11 | 10 | 23.9 | 0.4188 | 1.1203 | 0.0 |
| ICOSA icosa-minus-[0, 1, 2, 8] | 6 | 2 | 8 | 13 | 14.7 | 0.8864 | 1.1818 | 0.0 |
| ICOSA icosa-minus-[0, 1, 5] | 6 | 3 | 9 | 14 | 19.6 | 0.7159 | 1.1282 | 0.0 |
| ICOSA icosa-minus-[0, 1] | 6 | 4 | 10 | 16 | 26.1 | 0.6136 | 1.1330 | 0.0 |

**Violations of the sharp cap (a-form): 0.**

None. On every lattice disk computable here the sharp cap holds, and the
margin **improves** as the disk grows -- the opposite of what the P-form
measurement suggested. The Bridge-Lemma fibre `P(S,4)/(24a)` grows fast
enough to absorb the entire excess.

