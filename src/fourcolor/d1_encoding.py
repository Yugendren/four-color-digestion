"""D1 canonical token-sequence encoding: config -> input tokens, closure
trace -> process-supervision target tokens.

Design doc / v1 spec (per sources/method-survey.md §2 and the D1 task):

INPUT (encoder) sequence, deterministic given the configuration:
    RING MAG(r) N MAG(n)
    for v in 1..n, IN CANONICAL NUMBERING (fourcolor.canonical picks the
    ring rotation-start + reflection that yields the lexicographically
    smallest serialization; see that module's docstring for why this is a
    real canonicalization, not a heuristic, for this restricted symmetry):
        V DEG MAG(deg(v))
        for each neighbor u of v, in rotation order:
            SIGN(sign(u - v))  MAG(|u - v|)
    Neighbors are encoded as signed offsets relative to the current vertex
    (the "relative/canonical indices" the task spec asks for) rather than
    absolute labels, since the canonical BFS numbering keeps adjacent
    vertices' labels close together (spiral-ish) and this keeps the
    integer range small and shared with the other numeric fields.

TARGET (decoder) sequence, v1 process supervision:
    BOS
    for count in trace:               # trace[0] = initial live-set size
                                       # (canonical codes not immediately
                                       # ruled out); trace[1:] = surviving
                                       # count after each Kempe-closure
                                       # round (fourcolor.reduce.check)
        ROUND SURV MAG(bucket(count))
    VERDICT_R | VERDICT_NR             # d_reducible <=> final trace == 0
    EOS

Bucketing (`surv_bucket`): power-of-two buckets, bucket(count) =
count.bit_length(), i.e. 0->0, 1->1, 2-3->2, 4-7->3, 8-15->4, ... This is
exactly Python's int.bit_length(), which happens to already implement the
"0, 1, 2-3, 4-7, ..." doubling scheme the task spec asks for, with no
special-casing needed.

Honest v1 simplification: the target only carries the SIZE of the
surviving ring-coloring-class set per round, not the set's membership
(the exact per-class survivor identities are exponentially larger and not
representable as a short token sequence at v1 scale — e.g. ring 16 has up
to 3^15 ~ 14M canonical codes). The model is process-supervised on the
*shape* of the fixed-point contraction (how fast |C_i| shrinks and how
many rounds it takes) plus the terminal verdict, not on the fixed point's
exact identity. Predicting the survivor SET (or a compressed sketch of
it) is the natural v2 extension once this v1 scaffold is validated.

Vocabulary (<64 tokens; see `TOKENS`): a handful of structural markers
plus one shared family of magnitude tokens MAG_0..MAG_31 (reused for r,
n, degree, neighbor-offset magnitude, AND survivor-bucket index) and two
sign tokens for the neighbor offsets. All numeric values are clamped to
[0, MAG_CAP]; clamping is logged by the caller (see tools/d1_assemble.py
corpus stats) rather than silently absorbed, since it changes what the
model can see. Observed data (RSST 633 + Steinberger 2822 + generator
sweep) has n <= 29, r <= 16, degree <= 11, so MAG_CAP=31 is not expected
to clamp in practice for those sources; it may clamp survivor-bucket
values for very large closures (bucket 31 covers counts >= 2^31, which
does not occur at the ring sizes in this corpus either) — the headroom is
deliberate, not tight.
"""

from __future__ import annotations

from .canonical import canonical_labeling

MAG_CAP = 31  # MAG_0 .. MAG_31

TOKENS = (
    ["PAD", "BOS", "EOS"]
    + ["RING", "N", "V", "DEG", "ROUND", "SURV", "VERDICT_R", "VERDICT_NR"]
    + ["SIGN_POS", "SIGN_NEG"]
    + [f"MAG_{i}" for i in range(MAG_CAP + 1)]
)
STOI = {t: i for i, t in enumerate(TOKENS)}
ITOS = {i: t for i, t in enumerate(TOKENS)}
VOCAB_SIZE = len(TOKENS)

PAD_ID = STOI["PAD"]
BOS_ID = STOI["BOS"]
EOS_ID = STOI["EOS"]


def surv_bucket(count: int) -> int:
    """Power-of-two bucket index for a survivor count (see module doc)."""
    if count < 0:
        raise ValueError(f"negative survivor count: {count}")
    return min(count.bit_length(), MAG_CAP)


def _mag_token(value: int) -> str:
    clamped = max(0, min(value, MAG_CAP))
    return f"MAG_{clamped}"


def _mag_id(value: int) -> int:
    return STOI[_mag_token(value)]


def encode_config(
    adjacency: dict[int, list[int]], r: int, n: int
) -> list[int]:
    """Encoder input token ids for a configuration (see module doc).

    `adjacency` may use any numbering following the ring=1..r-cyclic
    convention (RSST/Steinberger/nl4ct/generator all do); this function
    canonicalizes internally, so the result is deterministic given the
    configuration's abstract structure, not its input labeling.
    """
    label, _start, direction = canonical_labeling(adjacency, r, n)
    inv = {new: old for old, new in label.items()}

    ids: list[int] = [STOI["RING"], _mag_id(r), STOI["N"], _mag_id(n)]
    for new_v in range(1, n + 1):
        old_v = inv[new_v]
        nbrs = adjacency[old_v]
        if direction == -1:
            nbrs = list(reversed(nbrs))
        new_nbrs = [label[u] for u in nbrs]
        if new_nbrs:
            k = new_nbrs.index(min(new_nbrs))
            new_nbrs = new_nbrs[k:] + new_nbrs[:k]
        ids.append(STOI["V"])
        ids.append(STOI["DEG"])
        ids.append(_mag_id(len(new_nbrs)))
        for u in new_nbrs:
            offset = u - new_v
            ids.append(STOI["SIGN_POS"] if offset >= 0 else STOI["SIGN_NEG"])
            ids.append(_mag_id(abs(offset)))
    return ids


def encode_trace(trace: list[int], d_reducible: bool) -> list[int]:
    """Decoder target token ids (with BOS/EOS) for a closure trace."""
    ids: list[int] = [BOS_ID]
    for count in trace:
        ids.append(STOI["ROUND"])
        ids.append(STOI["SURV"])
        ids.append(_mag_id(surv_bucket(count)))
    ids.append(STOI["VERDICT_R"] if d_reducible else STOI["VERDICT_NR"])
    ids.append(EOS_ID)
    return ids


def decode_verdict(ids: list[int]) -> bool | None:
    """Read off the predicted verdict from a (possibly greedily-decoded)
    target id sequence. Returns None if neither verdict token is present
    (e.g. truncated / malformed generation)."""
    verdict_r = STOI["VERDICT_R"]
    verdict_nr = STOI["VERDICT_NR"]
    for i in ids:
        if i == verdict_r:
            return True
        if i == verdict_nr:
            return False
    return None
