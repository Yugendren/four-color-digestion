"""Fast tests for tools/lp_wheel_level.py (the STRONG wheel-level cutting-plane LP).

Kept well under 20s total: no full ~16k-wheel build here (that's exercised by the real
runs, see the module docstring's USAGE section) -- just a handful of real wheel files
for the differential check, plus a tiny hand-built synthetic cutting-plane instance.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import lp_discharge as L  # noqa: E402
import lp_wheel_level as W  # noqa: E402
from fourcolor import nl4ct as N  # noqa: E402

RULE_DIR = N.default_rule_dir()
COMBINED_DIR = N.default_combined_rule_dir(blocked=False)
WHEEL_D7_DIR = N.default_wheel_dir(7)


def _have_data() -> bool:
    return RULE_DIR.is_dir() and COMBINED_DIR.is_dir() and WHEEL_D7_DIR.is_dir()


@unittest.skipUnless(_have_data(), "third_party/computer-checks data not available")
class TestZeroOptionPresent(unittest.TestCase):
    """The implicit-zero fix: every spoke's flag-matrix must contain the all-zero row,
    even when nl4ct.charge_bound_symbolic's own in_choices for that spoke is nonempty."""

    def test_zero_row_present_for_every_spoke(self):
        rules = N.load_rules(RULE_DIR)
        combined = N.load_combined_rules(COMBINED_DIR, len(rules))
        paths = sorted(WHEEL_D7_DIR.glob("*.cartwheel"))[:5]
        forms = W.build_wheel_forms(paths, rules, combined)
        self.assertEqual(len(forms), 5)
        for f in forms:
            for arr in f.spoke_choices:
                zero_rows = [row for row in arr if not any(row)]
                self.assertGreaterEqual(
                    len(zero_rows), 1, "zero flag vector missing from a spoke's choices"
                )
            # raw_choice_counts is the length BEFORE the zero row was appended, so
            # every spoke_choices matrix must be exactly one row taller.
            for arr, raw_n in zip(f.spoke_choices, f.raw_choice_counts):
                self.assertEqual(arr.shape[0], max(raw_n, 0) + 1)


@unittest.skipUnless(_have_data(), "third_party/computer-checks data not available")
class TestMatchesChargeBoundAtX0(unittest.TestCase):
    """f_w(x0), evaluated via the argmax-selection machinery, must equal
    nl4ct.charge_bound(wheel, rules, combined_rules) exactly (integers, x0 integral)."""

    def test_three_full_pool_wheels(self):
        rules = N.load_rules(RULE_DIR)
        combined = N.load_combined_rules(COMBINED_DIR, len(rules))
        x0 = L.x0_of(rules)
        import numpy as np

        x0_arr = np.array(x0, dtype=float)
        paths = sorted(WHEEL_D7_DIR.glob("*.cartwheel"))[:3]
        self.assertEqual(len(paths), 3)
        forms = W.build_wheel_forms(paths, rules, combined)
        for p, f in zip(paths, forms):
            w = N.parse_cartwheel_file(p)
            expected = N.charge_bound(w, rules, combined)
            f_val, _coeffs = W.evaluate_wheel(f, x0_arr)
            self.assertAlmostEqual(f_val, expected, places=6, msg=p.name)
            self.assertEqual(round(f_val), expected, p.name)


class TestSyntheticCuttingPlaneTerminates(unittest.TestCase):
    """A tiny hand-built max-of-affine instance: 1 "wheel" with 2 spokes over 2 rules.

    constant = 4, out_flags = (0, 0). Spoke 0's candidates (besides the implicit zero)
    are flag (1, 0); spoke 1's are flag (0, 1). So
        f(x) = 4 + max(0, x1) + max(0, x2) = 4 + x1 + x2   (x >= 0 always).
    The strong condition needs f(x) <= -1 (integral): impossible for x >= 0 since the
    minimum of f is 4 (at x = 0) -- so this is INFEASIBLE with NO low-degree rows at
    all (the "vacuous LP" caveat doesn't apply here because the wheel row alone already
    forces x1 = x2 = 0 as the only candidate to try, and even that fails).
    """

    def _make_form(self):
        import numpy as np

        return W.WheelForm(
            name="synthetic",
            d=7,
            spoke_degs=(5, 5),
            constant=4,
            out_flags=np.array([0, 0], dtype=np.int64),
            spoke_choices=[
                np.array([[1, 0], [0, 0]], dtype=np.int8),
                np.array([[0, 1], [0, 0]], dtype=np.int8),
            ],
            raw_choice_counts=(1, 1),
        )

    def test_cutting_plane_reaches_infeasible_quickly(self):
        import numpy as np

        form = self._make_form()
        n_vars = 2
        x0 = [0, 0]
        rows: dict[tuple, L.Row] = {}
        f0, coeffs0 = W.evaluate_wheel(form, np.array(x0, dtype=float))
        row0 = W.make_row(form, coeffs0)  # argmax selection at x=0
        rows[row0.key()] = row0

        status = None
        for it in range(1, 21):
            row_list = list(rows.values())
            status, x_sol, ray = L.solve_lp(row_list, n_vars, True)
            if status == "INFEASIBLE":
                break
            self.assertEqual(status, "FEASIBLE")
            x_arr = np.array(x_sol, dtype=float)
            f_val, coeffs = W.evaluate_wheel(form, x_arr)
            row = W.make_row(form, coeffs)
            if not W.is_violated(row, x_sol, True):
                break
            rows[row.key()] = row
        self.assertEqual(status, "INFEASIBLE")
        self.assertLessEqual(it, 5, "should converge in very few cutting-plane rounds")

        # Independently verify the Farkas certificate the way the real driver does.
        y = L.exact_certificate_from_ray(row_list, ray, True)
        self.assertIsNotNone(y)
        ok, detail = L.farkas_check(row_list, y, True)
        self.assertTrue(ok, detail)


if __name__ == "__main__":
    unittest.main()
