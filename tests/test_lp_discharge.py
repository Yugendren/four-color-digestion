"""Tests for tools/lp_discharge.py -- the LP encoding of the discharging argument's
schema-robustness question (see that module's docstring for the full mathematical
background; ``leaf_row``/``lowdeg_row`` are ports of ``cartwheel.cpp::enum_bad_cartwheels``
and the module's own "d <= 6" lower-bound argument, respectively).

These tests are deliberately cheap: they sample small, fixed, deterministic subsets
(40 leaf files; a single hand-built d=5 wheel; the full but fast d=5 necklace sweep;
a hand-built 2-row synthetic Farkas system) rather than iterating the ~10k-leaf full
pool or the d=6 necklaces, so the whole file runs in a few seconds.
"""

import json
import random
import sys
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import lp_discharge as LD  # noqa: E402
from fourcolor import nl4ct as N  # noqa: E402

# 40 specific, sorted, deterministic cartwheel files from the published full-pool
# leaves -- same directory and same sort order (`sorted(p.glob("*.cartwheel"))`) that
# `lp_discharge.extract_rows`/`validate` use, so this mirrors production exactly.
_LEAF_PATHS_40 = sorted(LD.FULL_POOL_LEAVES.glob("*.cartwheel"))[:40]

CERT_PATH = ROOT / "results/steinberger/lp_main_certificate.json"


@unittest.skipUnless(_LEAF_PATHS_40, f"no cartwheel files found under {LD.FULL_POOL_LEAVES}")
class TestLeafRowMatchesCppInvariant(unittest.TestCase):
    """Mirrors the C++ ``assert(C == 0)`` in cartwheel.cpp::enum_bad_cartwheels: at x0,
    every published full-pool leaf's charge upper bound must be exactly 0. A regression
    here means leaf_row's linear form has drifted from the C++ semantics."""

    @classmethod
    def setUpClass(cls):
        cls.rules = LD.load_rules()
        cls.x0 = LD.x0_of(cls.rules)

    def test_leaf_row_matches_cpp_invariant(self):
        self.assertEqual(len(_LEAF_PATHS_40), 40)
        for path in _LEAF_PATHS_40:
            cw = N.parse_cartwheel_file(path)
            row = LD.leaf_row(cw, self.rules)
            self.assertEqual(
                row.value_at(self.x0), 0,
                f"{path.name}: C(x0) = {row.value_at(self.x0)} != 0",
            )


@unittest.skipUnless(_LEAF_PATHS_40, f"no cartwheel files found under {LD.FULL_POOL_LEAVES}")
class TestLeafRowDegreeAsserts(unittest.TestCase):
    """The other two C++ asserts on the same leaves: d in {7, 8}, and at least one spoke
    of degree >= 7 -- hence, per leaf_row's own `strict = d >= 9 or max(spoke_degs) < 7`,
    every one of these leaves must come out non-strict."""

    @classmethod
    def setUpClass(cls):
        cls.rules = LD.load_rules()

    def test_leaf_row_degree_asserts(self):
        for path in _LEAF_PATHS_40:
            cw = N.parse_cartwheel_file(path)
            row = LD.leaf_row(cw, self.rules)
            self.assertIn(row.d, (7, 8), f"{path.name}: d={row.d} not in (7, 8)")
            self.assertGreaterEqual(
                max(row.spoke_degs), 7,
                f"{path.name}: no spoke of degree >= 7, spoke_degs={row.spoke_degs}",
            )
            self.assertFalse(row.strict, f"{path.name}: expected strict=False")


@unittest.skipUnless(_LEAF_PATHS_40, f"no cartwheel files found under {LD.FULL_POOL_LEAVES}")
class TestLeafRowIsAffine(unittest.TestCase):
    """leaf_row's charge form is f(x) = constant + <coeffs, x>, affine in x with integer
    coefficients (per the module docstring's "LEAF CHARGE IS LINEAR IN x" section). For
    an affine f, f(u) + f(v) == f(u+v) + f(0) for all u, v -- this is exactly additivity
    of the linear part (f(u)+f(v)-f(0) = <a,u>+<a,v> = <a,u+v> = f(u+v)-f(0))."""

    @classmethod
    def setUpClass(cls):
        cls.rules = LD.load_rules()
        cls.n = len(cls.rules)

    def test_leaf_row_is_affine(self):
        path = _LEAF_PATHS_40[0]
        cw = N.parse_cartwheel_file(path)
        row = LD.leaf_row(cw, self.rules)
        zero = [0] * self.n
        f0 = row.value_at(zero)

        rng = random.Random(20260822)  # fixed seed: deterministic test
        for _ in range(5):
            u = [rng.randint(-5, 5) for _ in range(self.n)]
            v = [rng.randint(-5, 5) for _ in range(self.n)]
            uv = [a + b for a, b in zip(u, v)]
            self.assertEqual(
                row.value_at(u) + row.value_at(v),
                row.value_at(uv) + f0,
            )


class TestLowdegRowD5AllNines(unittest.TestCase):
    """Hand-checkable base case from the module docstring: hub degree 5, all five spokes
    of degree 9, must give exactly ``10 - 5*x_rule001 <= 0`` (the row attaining the
    docstring's claimed d=5 maximum LB of 0 at x0)."""

    def test_lowdeg_row_d5_all_nines(self):
        rules = LD.load_rules()
        # rule001 is the first rule by sorted filename (rule001.rule sorts before
        # rule002_1.rule etc.) and must be the amount-2 "send 2 units in" base rule
        # whose coefficient the docstring's row `10 - 5*x_rule001 <= 0` refers to.
        self.assertEqual(rules[0].name, "rule001")
        self.assertEqual(rules[0].amount, 2)

        x0 = LD.x0_of(rules)
        w = N.generate_cartwheel(5, (9, 9, 9, 9, 9))
        row = LD.lowdeg_row(w, rules)

        self.assertEqual(row.constant, 10)
        self.assertEqual(row.coeffs[0], -5)
        self.assertTrue(all(c == 0 for c in row.coeffs[1:]))
        self.assertEqual(row.value_at(x0), 0)


class TestLowdegRowsNonpositiveAtX0(unittest.TestCase):
    """Sanity claim from the module docstring: at x0, LB(w, x0) <= 0 for every unblocked
    d=5 wheel over the ring<=14 pool (max attained is exactly 0, at all-nines).

    Chose the FULL d=5 sweep (629 necklaces, 49 blocked -> 580 rows) over a 25-necklace
    sample: measured first (`N.load_configurations(R14_POOL_DIR)` ~0.4s, the full sweep
    with `wheel_is_blocked` + `lowdeg_row` on every necklace ~6s), comfortably inside the
    20s total budget, so there is no need to fall back to a partial sample. d=6 (2,466
    necklaces) is skipped for speed, per the task spec.
    """

    def test_lowdeg_rows_nonpositive_at_x0(self):
        rules = LD.load_rules()
        x0 = LD.x0_of(rules)
        confs = N.load_configurations(LD.R14_POOL_DIR)

        total = blocked = checked = 0
        for degs in N.enum_wheel_degree_sequences(5):
            total += 1
            w = N.generate_cartwheel(5, degs)
            if N.wheel_is_blocked(w, confs):
                blocked += 1
                continue
            row = LD.lowdeg_row(w, rules)
            checked += 1
            self.assertLessEqual(
                row.value_at(x0), 0,
                f"degs={degs}: LB(x0) = {row.value_at(x0)} > 0",
            )
        self.assertEqual(total, 629)
        self.assertEqual(blocked, 49)
        self.assertEqual(checked, 580)


class TestRhsOf(unittest.TestCase):
    """rhs_of: -constant normally, -1-constant when strict AND integral (dropping to
    the non-strict formula when integral=False, per the module's --real weakening)."""

    def test_rhs_of(self):
        constant = 7
        strict_row = LD.Row(coeffs=(), constant=constant, strict=True, d=0, spoke_degs=())
        nonstrict_row = LD.Row(coeffs=(), constant=constant, strict=False, d=0, spoke_degs=())

        self.assertEqual(LD.rhs_of(strict_row, integral=True), -1 - constant)
        self.assertEqual(LD.rhs_of(strict_row, integral=False), -constant)
        self.assertEqual(LD.rhs_of(nonstrict_row, integral=True), -constant)
        self.assertEqual(LD.rhs_of(nonstrict_row, integral=False), -constant)


class TestFarkasCheckAcceptsAndRejects(unittest.TestCase):
    """Hand-built 2-row, 2-variable synthetic system over x >= 0:
        row A:  -x1        <= -1     (i.e. x1 >= 1)
        row B:   x1        <=  0
    genuinely infeasible (row A forces x1 >= 1, row B forces x1 <= 0), witnessed by
    y = (1, 1): y^T A = (-1*1 + 1*1, 0) = (0, 0) >= 0, y^T b = 1*(-1) + 1*0 = -1 < 0."""

    def setUp(self):
        # Row.value_at / farkas_check only look at coeffs/constant/strict; rhs_of()
        # derives the RHS from (constant, strict, integral), so we pick constant such
        # that rhs_of(row, integral=True) equals the RHS values above (-1 and 0).
        self.row_a = LD.Row(coeffs=(-1, 0), constant=1, strict=False, d=0, spoke_degs=())
        self.row_b = LD.Row(coeffs=(1, 0), constant=0, strict=False, d=0, spoke_degs=())
        self.rows = [self.row_a, self.row_b]
        self.assertEqual(LD.rhs_of(self.row_a, True), -1)
        self.assertEqual(LD.rhs_of(self.row_b, True), 0)

    def test_accepts_genuine_certificate(self):
        y = [Fraction(1), Fraction(1)]
        ok, detail = LD.farkas_check(self.rows, y, integral=True)
        self.assertTrue(ok, detail)
        self.assertEqual(detail["yTb"], "-1")

    def test_rejects_negated_multiplier(self):
        y = [Fraction(-1), Fraction(1)]
        ok, detail = LD.farkas_check(self.rows, y, integral=True)
        self.assertFalse(ok, detail)
        self.assertIn(0, detail["negative_multipliers"])

    def test_rejects_all_zero_multipliers(self):
        y = [Fraction(0), Fraction(0)]
        ok, detail = LD.farkas_check(self.rows, y, integral=True)
        self.assertFalse(ok, detail)
        self.assertEqual(detail["yTb"], "0")

    def test_rejects_scaled_to_zero_yTb(self):
        # Zero out just row A's multiplier: y = (0, 1). Sign conditions still hold
        # (y >= 0, (y^T A) = (1, 0) >= 0) but y^T b = 0*(-1) + 1*0 = 0, not < 0 --
        # a distinct failure mode from "zero them all" (still has positive support).
        y = [Fraction(0), Fraction(1)]
        ok, detail = LD.farkas_check(self.rows, y, integral=True)
        self.assertFalse(ok, detail)
        self.assertEqual(detail["negative_multipliers"], [])
        self.assertEqual(detail["negative_columns"], [])
        self.assertEqual(detail["yTb"], "0")


class TestScaleToIntegers(unittest.TestCase):
    """scale_to_integers: turns a Fraction vector into an integer-valued Fraction vector
    of content 1 (gcd of the integer entries is 1), preserving direction (y_new = k*y_old
    for a single positive rational k)."""

    def test_scale_to_integers(self):
        y_old = [Fraction(2, 3), Fraction(4, 3), Fraction(-1, 6)]
        y_new = LD.scale_to_integers(y_old)

        # Integer-valued.
        for v in y_new:
            self.assertEqual(v.denominator, 1)

        # Content 1.
        from math import gcd
        content = 0
        for v in y_new:
            content = gcd(content, int(v))
        self.assertEqual(content, 1)

        # Direction preserved: a single positive k with y_new == k * y_old.
        nonzero = [i for i, v in enumerate(y_old) if v != 0]
        self.assertTrue(nonzero)
        k = y_new[nonzero[0]] / y_old[nonzero[0]]
        self.assertGreater(k, 0)
        for i in range(len(y_old)):
            self.assertEqual(y_new[i], k * y_old[i])


@unittest.skipUnless(CERT_PATH.exists(), f"no certificate at {CERT_PATH}")
class TestCertificateOnDiskStillVerifies(unittest.TestCase):
    """If the real Farkas certificate is present on disk, rebuild its Row objects purely
    from the JSON's own coeffs/constant/strict fields (no re-derivation from .cartwheel
    sources -- that's verify_farkas.py's job) and confirm lp_discharge.farkas_check itself
    still accepts it, with a strictly negative y^T b."""

    def test_certificate_on_disk_still_verifies(self):
        import json

        data = json.loads(CERT_PATH.read_text())
        integral = bool(data["integral"])
        json_rows = data["rows"]
        y_by_index = {int(i): Fraction(s) for i, s in data["multipliers"]}

        # index set of multipliers must match index set of rows (support-only certificate).
        self.assertEqual(set(y_by_index), {int(r["index"]) for r in json_rows})

        ordered = sorted(json_rows, key=lambda r: int(r["index"]))
        rows = [
            LD.Row(
                coeffs=tuple(r["coeffs"]),
                constant=r["constant"],
                strict=r["strict"],
                d=r["d"],
                spoke_degs=tuple(r["spoke_degs"]),
            )
            for r in ordered
        ]
        y = [y_by_index[int(r["index"])] for r in ordered]  # full-length, index-aligned

        ok, detail = LD.farkas_check(rows, y, integral)
        self.assertTrue(ok, detail)
        self.assertLess(Fraction(detail["yTb"]), 0)


if __name__ == "__main__":
    unittest.main()


class TestMathNecessity(unittest.TestCase):
    """tail_maximise / row_is_math_necessary -- the §5 repair in LP-SCHEMA-RESULT.md."""

    def test_tail_maximise_only_narrows(self):
        cw = LD.N.parse_cartwheel_file(
            LD.FULL_POOL_LEAVES / sorted(p.name for p in LD.FULL_POOL_LEAVES.glob("*.cartwheel"))[0])
        cw2 = LD.tail_maximise(cw)
        self.assertEqual(cw2.g.head, cw.g.head)          # structure untouched
        self.assertEqual(cw2.g.deg_hi, cw.g.deg_hi)
        for a, b in zip(cw.g.deg_lo, cw2.g.deg_lo):
            self.assertGreaterEqual(b, a)                # lower bounds only rise
        self.assertTrue(all(lo == 9 for lo, hi in zip(cw2.g.deg_lo, cw2.g.deg_hi) if hi == 9))

    def test_iis_rows_are_mathematically_necessary(self):
        cert = LD.OUT_DIR / "lp_main_certificate_iis.json"
        if not cert.exists():
            self.skipTest("IIS certificate not built")
        audit = LD.OUT_DIR / "iis_math_necessity.json"
        if not audit.exists():
            self.skipTest("necessity audit not run (tools/lp_discharge.py --audit-necessity)")
        res = json.loads(audit.read_text())
        self.assertTrue(res["all_mathematically_necessary"])
        leaves = [r for r in res["rows"] if r["kind"] == "leaf"]
        self.assertEqual(len(leaves), 9)
        for r in leaves:
            self.assertTrue(r["out_exact_after_tail_maximise"], r["source"])
            self.assertTrue(r["row_unchanged_by_tail_maximise"], r["source"])
            self.assertFalse(r["blocked_after_tail_maximise"], r["source"])
