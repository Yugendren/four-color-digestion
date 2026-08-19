"""Python reimplementation of the near-linear-4CT wheel-level discharging charge bound.

This module is a faithful line-by-line port of the "stage 1" pruning logic in
``third_party/computer-checks/src`` (C++), specifically:

  - ``pseudo_triangulation.cpp``  (dart/rotation-system construction, homomorphism BFS)
  - ``pseudo_configuration.cpp``  (degree tests, ``always_apply``/``never_apply``,
    ``amount_of_charge_send``, ``amount_of_possible_charge_send``,
    ``blocked_by_reducible_configuration``)
  - ``cartwheel.cpp``             (``generate_cartwheel``, ``enum_wheels``,
    ``CartWheel::upper_bound_of_charge`` with an *empty* ``combined_rule_with_spokes``,
    which is exactly what ``enum_possible_bad_wheels`` uses to produce the files under
    ``third_party/computer-checks/wheels/d{7..11}/*.cartwheel``)
  - ``rule.cpp`` / ``configuration.cpp`` (file formats, cut-vertex/mirror expansion)

Terminology and file formats are documented in
``third_party/computer-checks/FORMAT.md``; read that first.

--------------------------------------------------------------------------
WHAT "wheel-level charge bound" MEANS HERE
--------------------------------------------------------------------------
A cartwheel is a hub vertex of degree ``d`` (``d`` in ``{7,...,11}`` for "bad" wheels)
surrounded by ``d`` spokes (hub-neighbors) with fixed degrees in ``{5,...,9}`` (``9``
meaning "9 or more" -- the discharging rules never distinguish among degrees >= 9, so
representing that whole bucket by the literal value 9 is exact, not an approximation),
plus one layer of "fan" (second-neighbor) vertices with completely free degree range
``[5, 9]`` that closes each spoke of degree < 9 into a fully triangulated local
neighborhood (``generate_cartwheel``). Spokes of degree 9 get no fan: their rotation is
immediately left open (a boundary dart), matching the "9+" abstraction.

Given such a wheel, the C++ pruning step computes an upper bound on the final charge
the hub can end up with, after all discharging rules apply:

    upper_bound = 10*(6-d) - sum_i OUT(spoke_i) + sum_i IN(spoke_i)

  - ``OUT(spoke_i)`` = sum of ``rule.amount`` over all *base* rules that provably
    ALWAYS apply when charge flows hub -> spoke_i.  "Always applies" is a rooted
    graph homomorphism match where, at every matched vertex, the rule's degree
    interval must CONTAIN the wheel's degree interval (``Degree.include``,
    ``pseudo_configuration.cpp:315-317`` -- note the argument order:
    ``include(rule_degree, wheel_degree)``).  Because base-rule matching is a
    purely combinatorial yes/no test (it never looks at rule *amounts*), which
    rules always-apply from a given spoke is a constant, independent of the
    charge-amount vector ``x``.

  - ``IN(spoke_i)`` = the MAXIMUM ``combined_rule.amount`` over all *combined*
    rules that are not provably excluded, i.e. whose degree pattern has a
    non-empty INTERSECTION with the wheel's local structure at that spoke
    (``Degree.has_intersection``, via ``never_apply``,
    ``pseudo_configuration.cpp:319-321,333-343``).  A combined rule's amount is
    literally the sum of the amounts of the base rules it combines (see
    ``combine_rules`` in ``rule.cpp``), i.e. ``combined_rule.amount = <flag, x>``
    where ``flag`` is its 0/1 vector over the 84 base rules (this is exactly the
    01-string at the end of a ``.combined_rule`` file). *Which* combined rules are
    candidates (non-excluded) at a spoke is again a constant, independent of ``x``.

A wheel is a member of ``wheels/d{d}/*.cartwheel`` iff, starting from
``generate_cartwheel``, it survives (i) ``upper_bound >= 0`` and (ii) it is not
"blocked" by a reducible configuration (``blocked_by_reducible_configuration``,
``pseudo_configuration.cpp:274-282``) -- see ``enum_all_bad_wheels`` /
``CartWheel.prune`` with ``combined_rule_with_spokes = ()``. This module reproduces
exactly that stage (NOT the later ``fix_in_rules``/``fix_out_rules`` degree-refinement
stage that produces the final *bad cartwheel* list, which is out of scope here).

--------------------------------------------------------------------------
WHERE THE NONLINEARITY LIVES (for the discharging LP)
--------------------------------------------------------------------------
``charge_bound(wheel, x)`` as a function of the amount vector ``x in R^84`` is

    f(x) = constant - <out_flags, x> + sum_i max_{c in candidates_i} <flag_c, x>

``constant`` and ``out_flags`` (an integer count vector, since a base rule can apply
from more than one spoke) are LINEAR (in fact affine-constant) in ``x``.  The ONLY
nonlinearity is the per-spoke ``max`` over the finite (wheel-dependent, x-independent)
candidate set of combined-rule flag vectors -- a max of affine functions of ``x``, which
is CONVEX. ``charge_bound_symbolic`` returns exactly this data
(:class:`ChargeBoundForm`) so an LP can introduce one epigraph variable ``y_i`` per
spoke with ``y_i >= <flag_c, x>`` for every candidate ``c``, and use ``y_i`` in place of
the max: this gives a sound (conservatively large) surrogate for ``IN(spoke_i)``, so
enforcing the LP's affine bound ``constant - <out_flags,x> + sum_i y_i <= -eps`` implies
the true (nonlinear) ``charge_bound(x) <= -eps`` as well.

--------------------------------------------------------------------------
SCOPE / KNOWN LIMITATIONS
--------------------------------------------------------------------------
- Only the stage-1 ("possible bad wheel") pruning is reimplemented, matching what is
  on disk under ``wheels/d{7..11}/``. The subsequent exhaustive degree-refinement
  search (``fix_in_rules``/``fix_out_rules``/``refinement``, producing the final list
  of literally-bad cartwheels with fully concretized fan degrees) is NOT reimplemented.
- The reducible-configuration blocking check (``blocked_by_reducible_configuration``)
  IS reimplemented faithfully (including cut-vertex ring expansion and mirroring in
  ``.conf`` parsing), because closing the exact differential for d=10/d=11 requires it.
  See ``tools/nl4ct_differential.py`` for how it is (and is not) exercised at scale.
"""

from __future__ import annotations

import itertools
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Sequence

INFTY = 10**9
NIL = -1
CARTWHEEL_DEGREES = (5, 6, 7, 8, 9)
CARTWHEEL_DEG_MIN = 5
CARTWHEEL_DEG_MAX = 9
CONF_DEG_MAX = 12


# --------------------------------------------------------------------------
# Dart-based rotation system (PseudoTriangulation / PseudoConfiguration port)
# --------------------------------------------------------------------------


@dataclass
class Graph:
    """A rotation system with per-vertex degree intervals ("PseudoConfiguration").

    Darts are represented as parallel int arrays (mirrors ``struct Dart`` in
    ``pseudo_triangulation.hpp``): ``head[e]`` is the vertex the dart points to,
    ``rev[e]`` its reverse dart, ``succ[e]``/``pred[e]`` the next/previous dart in the
    (clockwise) rotation around ``head[e]``, or ``NIL`` at an open boundary.
    """

    N: int
    head: list[int]
    rev: list[int]
    succ: list[int]
    pred: list[int]
    deg_lo: list[int]
    deg_hi: list[int]

    @property
    def n_darts(self) -> int:
        return len(self.head)


def _build_darts(
    N: int, rotations: Sequence[Sequence[int]]
) -> tuple[list[int], list[int], list[int], list[int]]:
    """Port of ``PseudoTriangulation::from_v_rotations`` (dart construction only)."""
    dart_id: dict[tuple[int, int], int] = {}
    fresh = 0
    for a in range(N):
        for b in rotations[a]:
            if b == -1:
                continue
            key = (a, b)
            if key in dart_id:
                raise ValueError(f"Multiple darts between {a} and {b}")
            dart_id[key] = fresh
            fresh += 1
    head = [0] * fresh
    rev = [0] * fresh
    succ = [NIL] * fresh
    pred = [NIL] * fresh
    for a in range(N):
        rot = rotations[a]
        size = len(rot)
        for i, b in enumerate(rot):
            if b == -1:
                continue
            e = dart_id[(a, b)]
            rev_key = (b, a)
            if rev_key not in dart_id:
                raise ValueError(f"Discrepancy in dart structure between {a} and {b}")
            r = dart_id[rev_key]
            s = rot[i + 1] if i < size - 1 else rot[0]
            succ_e = dart_id[(a, s)] if s != -1 else NIL
            p = rot[i - 1] if i > 0 else rot[size - 1]
            pred_e = dart_id[(a, p)] if p != -1 else NIL
            head[e] = a
            rev[e] = r
            succ[e] = succ_e
            pred[e] = pred_e
    return head, rev, succ, pred


def from_v_rotations(
    N: int,
    rotations: Sequence[Sequence[int]],
    deg_lo: Sequence[int],
    deg_hi: Sequence[int],
) -> Graph:
    head, rev, succ, pred = _build_darts(N, rotations)
    return Graph(N, head, rev, succ, pred, list(deg_lo), list(deg_hi))


def _is_boundary_vertices(g: Graph) -> list[bool]:
    is_b = [False] * g.N
    for i in range(len(g.head)):
        if g.succ[i] == NIL:
            is_b[g.head[i]] = True
    return is_b


def _first_dart(g: Graph, v: int) -> int:
    for i in range(len(g.head)):
        if g.head[i] == v and g.pred[i] == NIL:
            return i
    return NIL


def _any_dart(g: Graph, v: int) -> int:
    for i in range(len(g.head)):
        if g.head[i] == v:
            return i
    return NIL


def get_e_rotations(g: Graph) -> list[list[int]]:
    """Port of ``PseudoTriangulation::get_e_rotations``."""
    is_b = _is_boundary_vertices(g)
    result: list[list[int]] = []
    for v in range(g.N):
        e_start = _first_dart(g, v) if is_b[v] else _any_dart(g, v)
        e_cur = e_start
        seq: list[int] = []
        while True:
            seq.append(e_cur)
            e_cur = g.succ[e_cur]
            if e_cur == e_start or e_cur == NIL:
                break
        if e_cur == NIL:
            seq.append(NIL)
        result.append(seq)
    return result


def find_dart(g: Graph, head: int, tail: int) -> list[int]:
    """Port of ``PseudoTriangulation::get_darts(head, tail)``."""
    out = []
    for i in range(len(g.head)):
        if g.head[i] == head and g.head[g.rev[i]] == tail:
            out.append(i)
    return out


# --------------------------------------------------------------------------
# Degree tests + generic rooted homomorphism (port of Degree + the
# PseudoConfiguration::homomorphism<DegreeTest> template)
# --------------------------------------------------------------------------


def degree_include(lo_a: int, hi_a: int, lo_b: int, hi_b: int) -> bool:
    """Degree::include(a, b): a's interval CONTAINS b's interval."""
    return lo_a <= lo_b and hi_b <= hi_a


def degree_has_intersection(lo_a: int, hi_a: int, lo_b: int, hi_b: int) -> bool:
    return not (hi_a < lo_b or hi_b < lo_a)


def homomorphism(
    Z: Graph, e: int, Z_star: Graph, e_star: int, mode: str
) -> tuple[list[int], list[int]] | None:
    """Port of the templated ``PseudoConfiguration::homomorphism``.

    ``mode`` is ``"include"`` (used for ``always_apply`` / ``dominantly_apply``-style
    checks: ``degree_test(Z.degree, Z_star.degree) = Degree::include``) or
    ``"intersection"`` (used for ``never_apply``: ``Degree::has_intersection``).

    Returns ``(vmap, dmap)`` on success (vertex map / dart map from ``Z`` into
    ``Z_star``), or ``None`` if no such rooted homomorphism exists.
    """
    vmap = [-1] * Z.N
    dmap = [-1] * len(Z.head)
    Zh, Zr, Zs, Zp, Zlo, Zhi = Z.head, Z.rev, Z.succ, Z.pred, Z.deg_lo, Z.deg_hi
    Sh, Sr, Ss, Sp, Slo, Shi = (
        Z_star.head,
        Z_star.rev,
        Z_star.succ,
        Z_star.pred,
        Z_star.deg_lo,
        Z_star.deg_hi,
    )
    include = mode == "include"
    Q: deque[tuple[int, int]] = deque()
    Q.append((e, e_star))
    while Q:
        f, f_star = Q.popleft()
        if dmap[f] != -1:
            if dmap[f] != f_star:
                return None
            continue
        dmap[f] = f_star
        h = Zh[f]
        h_star = Sh[f_star]
        if vmap[h] != -1 and vmap[h] != h_star:
            return None
        vmap[h] = h_star
        zlo, zhi = Zlo[h], Zhi[h]
        slo, shi = Slo[h_star], Shi[h_star]
        if include:
            ok = zlo <= slo and shi <= zhi
        else:
            ok = not (zhi < slo or shi < zlo)
        if not ok:
            return None
        Q.append((Zr[f], Sr[f_star]))
        succ_f, succ_fs = Zs[f], Ss[f_star]
        if succ_f != NIL:
            if succ_fs == NIL:
                return None
            Q.append((succ_f, succ_fs))
        pred_f, pred_fs = Zp[f], Sp[f_star]
        if pred_f != NIL:
            if pred_fs == NIL:
                return None
            Q.append((pred_f, pred_fs))
    return vmap, dmap


# --------------------------------------------------------------------------
# .rule / .combined_rule parsing (port of Rule::read / CombinedRule::from_file)
# --------------------------------------------------------------------------


@dataclass
class Rule:
    st_id: int  # dart representing the directed edge s -> t
    amount: int  # tenths of a unit
    g: Graph
    name: str = ""


@dataclass
class CombinedRule:
    combined_flag: tuple[int, ...]  # length = number of base rules, 0/1
    st_id: int
    amount: int
    g: Graph
    name: str = ""


def _read_pc_body(
    lines: Sequence[str], n: int
) -> tuple[list[list[int]], list[int], list[int]]:
    rotations: list[list[int] | None] = [None] * n
    deg_lo = [0] * n
    deg_hi = [0] * n
    for line in lines[:n]:
        parts = line.split()
        idx = int(parts[0]) - 1
        lo, hi = int(parts[1]), int(parts[2])
        if hi == 0:
            hi = INFTY
        neigh = [(-1 if p == "-1" else int(p) - 1) for p in parts[3:]]
        rotations[idx] = neigh
        deg_lo[idx] = lo
        deg_hi[idx] = hi
    assert all(r is not None for r in rotations), "missing vertex line"
    return rotations, deg_lo, deg_hi  # type: ignore[return-value]


def _nonblank_lines(text: str) -> list[str]:
    return [ln for ln in text.splitlines() if ln.strip() != ""]


def parse_rule_file(path: str | Path) -> Rule:
    text = Path(path).read_text()
    lines = _nonblank_lines(text)
    N, s, t, amount = map(int, lines[0].split())
    s -= 1
    t -= 1
    rotations, deg_lo, deg_hi = _read_pc_body(lines[1 : 1 + N], N)
    g = from_v_rotations(N, rotations, deg_lo, deg_hi)
    matches = find_dart(g, head=t, tail=s)
    assert len(matches) == 1, f"{path}: expected exactly one s->t dart, got {matches}"
    return Rule(st_id=matches[0], amount=amount, g=g, name=Path(path).stem)


def parse_combined_rule_file(path: str | Path, n_rules: int | None = None) -> CombinedRule:
    text = Path(path).read_text()
    lines = _nonblank_lines(text)
    N, s, t, amount = map(int, lines[0].split())
    s -= 1
    t -= 1
    rotations, deg_lo, deg_hi = _read_pc_body(lines[1 : 1 + N], N)
    g = from_v_rotations(N, rotations, deg_lo, deg_hi)
    matches = find_dart(g, head=t, tail=s)
    assert len(matches) == 1, f"{path}: expected exactly one s->t dart, got {matches}"
    flag_line = lines[1 + N].strip()
    flags = tuple(1 if c == "1" else 0 for c in flag_line)
    if n_rules is not None:
        assert len(flags) == n_rules, f"{path}: flag length {len(flags)} != {n_rules}"
    return CombinedRule(
        combined_flag=flags, st_id=matches[0], amount=amount, g=g, name=Path(path).stem
    )


def load_rules(ruledir: str | Path) -> list[Rule]:
    """Rules sorted by filename, matching ``get_objects<Rule>`` (and the order the
    01-flag strings in .combined_rule files index into)."""
    paths = sorted(p for p in Path(ruledir).iterdir() if p.suffix == ".rule")
    return [parse_rule_file(p) for p in paths]


def load_combined_rules(combined_ruledir: str | Path, n_rules: int) -> list[CombinedRule]:
    paths = sorted(p for p in Path(combined_ruledir).iterdir() if p.suffix == ".combined_rule")
    return [parse_combined_rule_file(p, n_rules) for p in paths]


# --------------------------------------------------------------------------
# CartWheel: parsing, generation, enumeration (port of cartwheel.cpp)
# --------------------------------------------------------------------------


@dataclass
class CartWheel:
    center: int
    center_darts: list[int]  # darts with head == center, one per spoke, clockwise
    g: Graph

    @property
    def degree(self) -> int:
        return self.g.deg_lo[self.center]


def parse_cartwheel_file(path: str | Path) -> CartWheel:
    text = Path(path).read_text()
    lines = _nonblank_lines(text)
    N, center = int(lines[0].split()[0]), int(lines[0].split()[1]) - 1
    rotations, deg_lo, deg_hi = _read_pc_body(lines[1 : 1 + N], N)
    g = from_v_rotations(N, rotations, deg_lo, deg_hi)
    e_rot = get_e_rotations(g)
    return CartWheel(center=center, center_darts=e_rot[center], g=g)


def load_cartwheels(cartwheeldir: str | Path) -> list[CartWheel]:
    paths = sorted(p for p in Path(cartwheeldir).iterdir() if p.suffix == ".cartwheel")
    return [parse_cartwheel_file(p) for p in paths]


def spoke_degree_sequence(wheel: CartWheel) -> tuple[int, ...]:
    """The clockwise spoke-degree necklace, e.g. ``(5, 6, 5, 7, ...)``."""
    g = wheel.g
    seq = []
    for dart in wheel.center_darts:
        spoke_v = g.head[g.rev[dart]]
        seq.append(g.deg_lo[spoke_v])
    return tuple(seq)


def generate_cartwheel(d: int, degrees: Sequence[int]) -> CartWheel:
    """Port of ``CartWheel::generate_cartwheel``.

    Builds the hub (vertex 0) + ``d`` spokes (vertices ``1..d``, fixed degrees taken
    from ``degrees``) + one layer of "fan" second-neighbor vertices (free range
    ``[5, 9]``) closing every spoke of degree < 9 into a triangulated neighborhood.
    Spokes of degree 9 (the "9+" bucket) get no fan and are left open (boundary).
    """
    assert len(degrees) == d
    rotations: list[list[int]] = [[] for _ in range(d + 1)]
    rotations[0] = list(range(1, d + 1))
    for i in range(1, d + 1):
        i_next = i + 1 if i < d else 1
        i_prev = i - 1 if i > 1 else d
        rotations[i] = [i_next, 0, i_prev]
    k = d + 1
    for i in range(1, d + 1):
        if degrees[i - 1] == CARTWHEEL_DEG_MAX:
            continue
        A = degrees[i - 1] - len(rotations[i])
        assert A >= 0
        for _ in range(A):
            i_last = rotations[i][-1]
            rotations.append([])
            rotations[k] = [i, i_last]
            rotations[i].append(k)
            rotations[i_last].insert(0, k)
            k += 1
        i_first = rotations[i][0]
        i_last = rotations[i][-1]
        rotations[i_first].append(i_last)
        rotations[i_last].insert(0, i_first)
    for i in range(1, k):
        if i > d or degrees[i - 1] == CARTWHEEL_DEG_MAX:
            rotations[i].append(-1)
    deg_lo = [CARTWHEEL_DEG_MIN] * k
    deg_hi = [CARTWHEEL_DEG_MAX] * k
    deg_lo[0] = deg_hi[0] = d
    for i in range(1, d + 1):
        deg_lo[i] = deg_hi[i] = degrees[i - 1]
    g = from_v_rotations(k, rotations, deg_lo, deg_hi)
    e_rot = get_e_rotations(g)
    return CartWheel(center=0, center_darts=e_rot[0], g=g)


def _is_lex_min(seq: tuple[int, ...]) -> bool:
    """Port of ``lex_min``: is ``seq`` lexicographically <= all of its rotations?"""
    n = len(seq)
    doubled = seq + seq
    for start in range(1, n):
        if doubled[start : start + n] < seq:
            return False
    return True


def enum_wheel_degree_sequences(d: int) -> Iterator[tuple[int, ...]]:
    """All spoke-degree necklaces of length ``d`` over ``{5,...,9}`` up to rotation.

    Reproduces the exact candidate SET produced by ``CartWheel::enum_wheels``: for
    each possible minimum value ``m``, every other position ranges freely over values
    ``>= m`` (a necessary condition for being lexicographically minimal among
    rotations), followed by the same ``lex_min`` filter used in the C++ to pick the
    canonical representative of each rotation-equivalence class.
    """
    for start_idx, start_val in enumerate(CARTWHEEL_DEGREES):
        tail_domain = CARTWHEEL_DEGREES[start_idx:]
        for rest in itertools.product(tail_domain, repeat=d - 1):
            seq = (start_val,) + rest
            if _is_lex_min(seq):
                yield seq


# --------------------------------------------------------------------------
# always_apply / never_apply / amount_of_*_charge_send (charges along an edge)
# --------------------------------------------------------------------------


def always_apply(g: Graph, dart_id: int, rule: Rule) -> bool:
    return homomorphism(rule.g, rule.st_id, g, dart_id, "include") is not None


def never_apply(g: Graph, dart_id: int, rule: Rule | CombinedRule) -> bool:
    return homomorphism(rule.g, rule.st_id, g, dart_id, "intersection") is None


def amount_of_charge_send(g: Graph, dart_id: int, rules: Sequence[Rule]) -> int:
    return sum(r.amount for r in rules if always_apply(g, dart_id, r))


def amount_of_possible_charge_send(
    g: Graph, dart_id: int, combined_rules: Sequence[CombinedRule]
) -> int:
    amount = 0
    for cr in combined_rules:
        if never_apply(g, dart_id, cr):
            continue
        amount = max(amount, cr.amount)
    return amount


# --------------------------------------------------------------------------
# The charge bound itself: numeric and symbolic (linear-in-x) forms
# --------------------------------------------------------------------------


def charge_bound(
    wheel: CartWheel, rules: Sequence[Rule], combined_rules: Sequence[CombinedRule]
) -> int:
    """Numeric upper bound on the hub's final charge, using each rule's own
    (published) amount. Equals ``CartWheel::upper_bound_of_charge`` with an empty
    ``combined_rule_with_spokes`` -- the stage-1 bound used by ``enum_possible_bad_wheels``."""
    d = wheel.degree
    g = wheel.g
    out_sum = 0
    in_sum = 0
    for j in range(d):
        dart_to_center = wheel.center_darts[j]
        in_sum += amount_of_possible_charge_send(g, dart_to_center, combined_rules)
        from_center = g.rev[dart_to_center]
        out_sum += amount_of_charge_send(g, from_center, rules)
    return 10 * (6 - d) - out_sum + in_sum


@dataclass
class ChargeBoundForm:
    """Symbolic (linear-in-x, up to one convex max per spoke) charge bound.

    ``value(x) = constant - dot(out_flags, x) + sum(max(dot(c, x) for c in choices)
                                                       for choices in in_choices)``

    ``out_flags[k]`` counts how many spokes have a base rule ``k`` that ALWAYS applies
    outward (so it is an integer, not just 0/1, if the same rule matches more than one
    spoke). ``in_choices[i]`` is the list of 0/1 flag vectors of every combined rule
    that is a *candidate* (not excluded) at spoke ``i``; see the module docstring for
    why the max is the only nonlinearity and how to LP-ify it.
    """

    d: int
    constant: int
    out_flags: list[int]
    in_choices: list[list[tuple[int, ...]]]
    rule_names: list[str]

    def evaluate(self, x: Sequence[float]) -> float:
        out_dot = sum(f * xi for f, xi in zip(self.out_flags, x))
        in_sum = 0.0
        for choices in self.in_choices:
            in_sum += max(sum(f * xi for f, xi in zip(flags, x)) for flags in choices)
        return self.constant - out_dot + in_sum


def charge_bound_symbolic(
    wheel: CartWheel, rules: Sequence[Rule], combined_rules: Sequence[CombinedRule]
) -> ChargeBoundForm:
    d = wheel.degree
    g = wheel.g
    n_rules = len(rules)
    out_flags = [0] * n_rules
    in_choices: list[list[tuple[int, ...]]] = []
    for j in range(d):
        dart_to_center = wheel.center_darts[j]
        from_center = g.rev[dart_to_center]
        for k, r in enumerate(rules):
            if always_apply(g, from_center, r):
                out_flags[k] += 1
        choices = [cr.combined_flag for cr in combined_rules if not never_apply(g, dart_to_center, cr)]
        in_choices.append(choices)
    constant = 10 * (6 - d)
    return ChargeBoundForm(
        d=d,
        constant=constant,
        out_flags=out_flags,
        in_choices=in_choices,
        rule_names=[r.name for r in rules],
    )


# --------------------------------------------------------------------------
# .conf parsing + reducible-configuration blocking check
# (port of configuration.cpp + PseudoConfiguration::{contain_conf,
#  rooted_contain_conf, darts_by_degree, blocked_by_reducible_configuration,
#  representative_degree})
# --------------------------------------------------------------------------


@dataclass
class Configuration:
    dart_id: int
    g: Graph


def _remove_ring(
    N: int, R: int, deg_lo: Sequence[int], deg_hi: Sequence[int],
    rotations: Sequence[Sequence[int]], remove: Sequence[bool],
) -> Graph:
    old2new = [-1] * N
    new_id = 0
    for i in range(N):
        if i < R and remove[i]:
            continue
        old2new[i] = new_id
        new_id += 1
    new_N = new_id
    new_rotations: list[list[int]] = [[] for _ in range(new_N)]
    for i in range(N):
        if i < R and remove[i]:
            continue
        for j in rotations[i]:
            new_rotations[old2new[i]].append(-1 if j == -1 else old2new[j])
    new_deg_lo = [1] * new_N
    new_deg_hi = [INFTY] * new_N
    for i in range(R):
        if remove[i]:
            continue
        k = old2new[i]
        d = sum(1 for v in new_rotations[k] if v != -1)
        assert d in (3, 4), f"ring vertex {i} has {d} non-boundary neighbors after removal"
        new_deg_lo[k] = d + 1
        new_deg_hi[k] = INFTY
    for i in range(R, N):
        k = old2new[i]
        new_deg_lo[k] = deg_lo[i]
        new_deg_hi[k] = deg_hi[i]
    return from_v_rotations(new_N, new_rotations, new_deg_lo, new_deg_hi)


def _maximum_degree_dart(g: Graph) -> int:
    f = -1
    d_f = (0, 0)
    for i in range(len(g.head)):
        y = g.head[i]
        x = g.head[g.rev[i]]
        if g.deg_lo[y] != g.deg_hi[y] or g.deg_lo[x] != g.deg_hi[x]:
            continue
        d_e = (g.deg_lo[y], g.deg_lo[x])
        if d_e > d_f:
            f = i
            d_f = d_e
    assert f != -1
    return f


def _find_cut_pairs(N: int, R: int, rotations: Sequence[Sequence[int]]) -> list[tuple[int, int]]:
    P: list[tuple[int, int]] = []
    for i in range(R, N):
        U_R: list[int] = []
        t = 0
        rot = rotations[i]
        d = len(rot)
        for j in range(d):
            k1 = rot[j]
            assert k1 != -1
            if k1 < R:
                U_R.append(k1)
            k2 = rot[(j + 1) % d]
            if k1 < R and k2 >= R:
                t += 1
        assert t <= len(U_R)
        if t >= 2 and len(U_R) != 2:
            raise ValueError(f"Invalid configuration (vertex {i} is an invalid cut-vertex)")
        if t == 2 and len(U_R) == 2:
            P.append((U_R[0], U_R[1]))
    return P


def _extend_from_cut_vertices(
    N: int, R: int, deg_lo: Sequence[int], deg_hi: Sequence[int],
    rotations: Sequence[Sequence[int]],
) -> list[Configuration]:
    P = _find_cut_pairs(N, R, rotations)
    configs = []
    P_size = len(P)
    for S in range(1 << P_size):
        remove = [True] * R
        for i, (a, b) in enumerate(P):
            if S & (1 << i):
                remove[a] = False
            else:
                remove[b] = False
        g = _remove_ring(N, R, deg_lo, deg_hi, rotations, remove)
        dart = _maximum_degree_dart(g)
        configs.append(Configuration(dart_id=dart, g=g))
    return configs


def _mirror(conf: Configuration) -> Configuration:
    g = conf.g
    new_g = Graph(g.N, list(g.head), list(g.rev), list(g.pred), list(g.succ), list(g.deg_lo), list(g.deg_hi))
    return Configuration(dart_id=conf.dart_id, g=new_g)


def parse_conf_file(path: str | Path) -> list[Configuration]:
    """Port of ``Configuration::from_file``: one physical ``.conf`` record expands
    into ``2 * 2**|cut pairs|`` :class:`Configuration` objects (cut-vertex ring
    splitting x mirroring)."""
    text = Path(path).read_text()
    lines = _nonblank_lines(text)
    N, R = map(int, lines[0].split())
    deg_lo = [1] * N
    deg_hi = [INFTY] * N
    rotations: list[list[int]] = [[] for _ in range(N)]
    suc = [[-1] * N for _ in range(R)]
    idx = 1
    for u in range(R, N):
        parts = lines[idx].split()
        idx += 1
        assert int(parts[0]) == u + 1
        d = int(parts[1])
        neigh = [int(x) - 1 for x in parts[2 : 2 + d]]
        assert len(neigh) == d
        deg_lo[u] = deg_hi[u] = d
        rotations[u] = neigh
        for j in range(d):
            v = neigh[j]
            pre = neigh[(j + d - 1) % d]
            nxt = neigh[(j + 1) % d]
            if v < R:
                suc[v][nxt] = u
                suc[v][u] = pre
    for v in range(R):
        start = (v + 1) % R
        end = (v + R - 1) % R
        curr = start
        seq: list[int] = []
        while curr != -1:
            seq.append(curr)
            curr = suc[v][curr]
        if not seq or seq[-1] != end:
            raise ValueError(f"Invalid configuration file: {path}")
        seq.append(-1)
        rotations[v] = seq
    configs = _extend_from_cut_vertices(N, R, deg_lo, deg_hi, rotations)
    mirrors = [_mirror(c) for c in configs]
    return configs + mirrors


def load_configurations(confdir: str | Path) -> list[Configuration]:
    confs: list[Configuration] = []
    for p in Path(confdir).iterdir():
        if p.suffix == ".conf":
            confs.extend(parse_conf_file(p))
    return confs


def _representative_degree(g: Graph, center: int) -> list[Graph]:
    """Port of ``PseudoConfiguration::representative_degree``.

    NOTE (surprising but verified against the source, see module docstring): for any
    vertex whose degree-upper-bound exceeds 8 (i.e. is 9, the "9+" bucket, or the
    center with an unbounded upper bound > CONF_DEG_MAX), only ONE representative --
    the fixed value ``upper`` -- is produced, NOT one representative per value in the
    range. For the raw (stage-1) wheels this module targets, every vertex's degree is
    already either fully fixed or has upper bound exactly 9, so this function always
    returns exactly one Graph (no combinatorial blow-up) for our use case.
    """
    N = g.N
    T: list[list[tuple[int, int]]] = [[(1, INFTY)] * N]
    for v in range(N):
        L: list[tuple[int, int]] = []
        if v == center and g.deg_hi[v] > CONF_DEG_MAX:
            L.append((g.deg_hi[v], g.deg_hi[v]))
        elif v != center and g.deg_hi[v] > 8:
            L.append((g.deg_hi[v], g.deg_hi[v]))
        else:
            for deg in range(g.deg_lo[v], g.deg_hi[v] + 1):
                L.append((deg, deg))
        new_T = []
        for degs in T:
            for d in L:
                new_degs = list(degs)
                new_degs[v] = d
                new_T.append(new_degs)
        T = new_T
    results = []
    for degs in T:
        lo = [d[0] for d in degs]
        hi = [d[1] for d in degs]
        results.append(Graph(N, g.head, g.rev, g.succ, g.pred, lo, hi))
    return results


def _darts_by_degree(g: Graph) -> dict[tuple[int, int], list[int]]:
    buckets: dict[tuple[int, int], list[int]] = {}
    for i in range(len(g.head)):
        y = g.head[i]
        x = g.head[g.rev[i]]
        dy, dx = g.deg_lo[y], g.deg_lo[x]
        if dy > CONF_DEG_MAX or dx > CONF_DEG_MAX:
            continue
        buckets.setdefault((dy, dx), []).append(i)
    return buckets


def _rooted_contain_conf(g: Graph, dart_id: int, conf: Configuration) -> bool:
    return homomorphism(conf.g, conf.dart_id, g, dart_id, "include") is not None


def _contain_conf(g: Graph, center: int, confs: Sequence[Configuration]) -> bool:
    buckets = _darts_by_degree(g)
    for conf in confs:
        y = conf.g.head[conf.dart_id]
        x = conf.g.head[conf.g.rev[conf.dart_id]]
        d_y, d_x = conf.g.deg_lo[y], conf.g.deg_lo[x]
        for f_star in buckets.get((d_y, d_x), ()):
            if d_y > 8 and g.head[f_star] != center:
                continue
            if _rooted_contain_conf(g, f_star, conf):
                return True
    return False


def blocked_by_reducible_configuration(g: Graph, center: int, confs: Sequence[Configuration]) -> bool:
    for Z in _representative_degree(g, center):
        if not _contain_conf(Z, center, confs):
            return False
    return True


def wheel_is_blocked(wheel: CartWheel, confs: Sequence[Configuration]) -> bool:
    return blocked_by_reducible_configuration(wheel.g, wheel.center, confs)


# --------------------------------------------------------------------------
# Convenience: default repo-relative paths
# --------------------------------------------------------------------------

_COMPUTER_CHECKS = Path(__file__).resolve().parents[2] / "third_party" / "computer-checks"


def default_rule_dir() -> Path:
    return _COMPUTER_CHECKS / "discharging-rules" / "R"


def default_combined_rule_dir(blocked: bool = False) -> Path:
    name = "all" if blocked else "non_blocked"
    return _COMPUTER_CHECKS / "combined_rules" / name


def default_conf_dir() -> Path:
    return _COMPUTER_CHECKS / "reducible-configurations" / "D"


def default_wheel_dir(d: int) -> Path:
    return _COMPUTER_CHECKS / "wheels" / f"d{d}"
