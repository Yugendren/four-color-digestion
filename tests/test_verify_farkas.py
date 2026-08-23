"""Tests for tools/verify_farkas.py, the standalone Farkas-certificate verifier for
tools/lp_discharge.py's discharging LP (see that module's docstring).

These tests use a hand-built, tiny synthetic certificate (2 variables, 2 rows,
``source == ""`` on every row) rather than the real 84-variable / tens-of-thousands-
of-rows certificate, so they run in well under a second. Because the rows carry no
``source``, re-derivation is impossible by construction; the tests exercise the
explicit "underived" escape hatch (``--allow-underived`` / ``allow_underived=True``)
and confirm the verifier REFUSES to say VERIFIED without it.

The synthetic system is, over x = (x1, x2) >= 0:
    row A:  -x1 <= -1      (i.e. x1 >= 1)
    row B:   x1 <=  0
which is infeasible for any x1 >= 0 -- witnessed by multipliers y = (1, 1):
    y^T A = (-1*1 + 1*1, 0) = (0, 0) >= 0
    y^T b =  1*(-1) + 1*0  = -1 < 0
A third row (index 2, unused, y=0) is included in the certificate's "rows" list only
to mimic the fact that real certificates carry more rows than are in the support --
it is not referenced by any multiplier.
"""

import sys
import unittest
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import lp_discharge as LD  # noqa: E402
import verify_farkas as VF  # noqa: E402


def make_synthetic_certificate() -> dict:
    """A genuine, hand-built Farkas certificate over 2 underived (source=="") rows."""
    return {
        "integral": True,
        "n_rows": 2,
        "multipliers": [[0, "1"], [1, "1"]],
        "rows": [
            {
                # "constant + <coeffs,x> <= rhs_of(row)" with rhs_of = limit(0) -
                # constant, so constant=1 here encodes "-x1 <= -1" i.e. x1 >= 1.
                "index": 0,
                "coeffs": [-1, 0],
                "constant": 1,
                "strict": False,
                "rhs": -1,
                "d": 0,
                "spoke_degs": [],
                "source": "",
            },
            {
                "index": 1,
                "coeffs": [1, 0],
                "constant": 0,
                "strict": False,
                "rhs": 0,
                "d": 0,
                "spoke_degs": [],
                "source": "",
            },
        ],
    }


class TestSyntheticCertificateShape(unittest.TestCase):
    """Sanity: the synthetic fixture itself is internally consistent with rhs_of()."""

    def test_rhs_matches_rhs_of(self):
        cert = make_synthetic_certificate()
        for jr in cert["rows"]:
            row = LD.Row(
                coeffs=tuple(jr["coeffs"]), constant=jr["constant"], strict=jr["strict"],
                d=jr["d"], spoke_degs=tuple(jr["spoke_degs"]),
            )
            self.assertEqual(LD.rhs_of(row, cert["integral"]), jr["rhs"])


class TestVerifyFarkasAcceptsGenuineCertificate(unittest.TestCase):
    def test_accepts_with_allow_underived(self):
        cert = make_synthetic_certificate()
        ok, report = VF.verify_certificate_dict(cert, allow_underived=True)
        self.assertTrue(ok, report)
        self.assertIn("FARKAS CERTIFICATE VERIFIED", report)

    def test_refuses_without_allow_underived(self):
        cert = make_synthetic_certificate()
        ok, report = VF.verify_certificate_dict(cert, allow_underived=False)
        self.assertFalse(ok, report)
        self.assertIn("FARKAS CERTIFICATE REJECTED", report)
        self.assertIn("empty", report.lower())


class TestVerifyFarkasRejectsNegatedMultiplier(unittest.TestCase):
    def test_negated_multiplier_rejected(self):
        cert = deepcopy(make_synthetic_certificate())
        cert["multipliers"][0] = [0, "-1"]  # y_0 = -1, violates y >= 0
        ok, report = VF.verify_certificate_dict(cert, allow_underived=True)
        self.assertFalse(ok, report)
        self.assertIn("FARKAS CERTIFICATE REJECTED", report)
        self.assertIn("negative", report.lower())


class TestVerifyFarkasRejectsPositiveYTB(unittest.TestCase):
    def test_flipped_rhs_rejected(self):
        cert = deepcopy(make_synthetic_certificate())
        # Flip row 1's rhs from 0 to +5 (constant -5, still strict=False, limit=0):
        # rhs_of = limit - constant = 0 - (-5) = 5.  y^T b becomes -1 + 5 = 4 >= 0.
        cert["rows"][1]["constant"] = -5
        cert["rows"][1]["rhs"] = 5
        ok, report = VF.verify_certificate_dict(cert, allow_underived=True)
        self.assertFalse(ok, report)
        self.assertIn("FARKAS CERTIFICATE REJECTED", report)
        self.assertIn("y^T b", report)


class TestAgreesWithLpDischargeFarkasCheck(unittest.TestCase):
    """The verifier's own Farkas arithmetic must agree with lp_discharge.farkas_check
    on the exact same (rows, y, integral) -- two independently-written pieces of code
    computing the same exact-rational quantities should never disagree."""

    def _rows_and_y(self, cert):
        rows = []
        y = []
        for jr in cert["rows"]:
            rows.append(LD.Row(
                coeffs=tuple(jr["coeffs"]), constant=jr["constant"], strict=jr["strict"],
                d=jr["d"], spoke_degs=tuple(jr["spoke_degs"]),
            ))
        y_by_index = {int(i): Fraction(s) for i, s in cert["multipliers"]}
        for i in range(len(rows)):
            y.append(y_by_index.get(i, Fraction(0)))
        return rows, y

    def test_agrees_on_genuine_certificate(self):
        cert = make_synthetic_certificate()
        rows, y = self._rows_and_y(cert)
        ok_ld, detail = LD.farkas_check(rows, y, cert["integral"])
        ok_vf, report = VF.verify_certificate_dict(cert, allow_underived=True)
        self.assertTrue(ok_ld, detail)
        self.assertTrue(ok_vf, report)
        self.assertEqual(ok_ld, ok_vf)

    def test_agrees_on_negated_multiplier(self):
        cert = deepcopy(make_synthetic_certificate())
        cert["multipliers"][0] = [0, "-1"]
        rows, y = self._rows_and_y(cert)
        ok_ld, detail = LD.farkas_check(rows, y, cert["integral"])
        ok_vf, report = VF.verify_certificate_dict(cert, allow_underived=True)
        self.assertFalse(ok_ld, detail)
        self.assertFalse(ok_vf, report)
        self.assertEqual(ok_ld, ok_vf)

    def test_agrees_on_flipped_rhs(self):
        cert = deepcopy(make_synthetic_certificate())
        cert["rows"][1]["constant"] = -5
        cert["rows"][1]["rhs"] = 5
        rows, y = self._rows_and_y(cert)
        ok_ld, detail = LD.farkas_check(rows, y, cert["integral"])
        ok_vf, report = VF.verify_certificate_dict(cert, allow_underived=True)
        self.assertFalse(ok_ld, detail)
        self.assertFalse(ok_vf, report)
        self.assertEqual(ok_ld, ok_vf)


if __name__ == "__main__":
    unittest.main()
