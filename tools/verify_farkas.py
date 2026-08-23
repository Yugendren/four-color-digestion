#!/usr/bin/env python3
"""Standalone, paranoid verifier for a Farkas infeasibility certificate produced by
``tools/lp_discharge.py`` (see that module's docstring for the LP being decided).

This script is the thing that actually carries the proof, so it is written to trust
nothing:

  * it never calls an LP solver (no highspy, no scipy) -- every check below is exact
    rational arithmetic over ``fractions.Fraction``;
  * it does not trust the certificate JSON's ``coeffs``/``constant``/``strict`` fields
    for any row -- it RE-DERIVES each row independently from the ``source`` tag
    (a ``.cartwheel`` filename or a ``d<D>-<degs>`` low-degree tag) using the same
    ``leaf_row``/``lowdeg_row`` extractors as ``lp_discharge.py``, and asserts the
    re-derived row equals what the certificate claims;
  * it checks the Farkas conditions exactly:
        (a) y_i >= 0 for every row i in the support
        (b) at least one y_i > 0
        (c) (y^T A)_k >= 0 for every column k
        (d) y^T b < 0
    which together prove the system ``{x >= 0 : A x <= b}`` is infeasible:
    for any such x,  0 <= (y^T A) x = y^T (A x) <= y^T b < 0, a contradiction;
  * it independently re-checks that the published amount vector x0 violates at least
    one row in the certificate's support, as a sanity anchor (x0 is exactly why the
    LP was built in the first place).

USAGE
-----
    tools/verify_farkas.py                          # verify the default certificate
    tools/verify_farkas.py --certificate PATH        # verify a specific certificate
    tools/verify_farkas.py --allow-underived         # accept rows with source == ""
                                                      # WITHOUT re-derivation (their
                                                      # provenance is then unverified;
                                                      # only meant for synthetic tests)

Exit code 0 on "FARKAS CERTIFICATE VERIFIED", 1 on "FARKAS CERTIFICATE REJECTED: ...".
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import lp_discharge as LD  # noqa: E402  (the module under verification's data schema)
from fourcolor import nl4ct as N  # noqa: E402

DEFAULT_CERTIFICATE = ROOT / "results/steinberger/lp_main_certificate.json"
RULES_DIR = ROOT / "third_party/discharging-rules/R"

# Search order for `.cartwheel` leaf sources (mirrors lp_discharge.py's leaf dirs).
CARTWHEEL_DIRS = [
    ROOT / "third_party/computer-checks/wheels/zero",
    ROOT / "results/p3/runs/steinberger-s1/work/wheels/zero",
    ROOT / "results/p3/runs/steinberger-s1/work/wheels/zero_ndebug",
]

# Low-degree tag: "d<D>-<degs>", e.g. "d5-99999" == hub degree 5, spokes (9,9,9,9,9).
LOWDEG_TAG_RE = re.compile(r"^d(\d+)-([5-9]+)$")


class VerificationError(Exception):
    """Raised for any condition that must reject the certificate."""


# --------------------------------------------------------------------------
# Row re-derivation
# --------------------------------------------------------------------------


def find_cartwheel_file(name: str) -> Path | None:
    for d in CARTWHEEL_DIRS:
        p = d / name
        if p.exists():
            return p
    return None


def rederive_row(source: str, rules) -> LD.Row:
    """Recompute a Row purely from ``source``, independent of any JSON-supplied coeffs.

    Raises VerificationError if ``source`` cannot be resolved to a concrete wheel.
    """
    if source.endswith(".cartwheel"):
        p = find_cartwheel_file(source)
        if p is None:
            searched = ", ".join(str(d) for d in CARTWHEEL_DIRS)
            raise VerificationError(
                f"cartwheel source {source!r} not found in any of: {searched}"
            )
        cw = N.parse_cartwheel_file(p)
        return LD.leaf_row(cw, rules)

    m = LOWDEG_TAG_RE.match(source)
    if m:
        d = int(m.group(1))
        degs = tuple(int(c) for c in m.group(2))
        if len(degs) != d:
            raise VerificationError(
                f"low-degree tag {source!r}: {len(degs)} spoke digits but hub degree {d}"
            )
        w = N.generate_cartwheel(d, degs)
        return LD.lowdeg_row(w, rules)

    raise VerificationError(
        f"source {source!r} matches neither the '*.cartwheel' pattern "
        f"nor the low-degree 'd<D>-<degs>' tag pattern"
    )


def resolve_row(json_row: dict, rules, allow_underived: bool) -> tuple[LD.Row, bool, str]:
    """Return (row_to_use, was_rederived, note) for one certificate row entry.

    If ``source`` is empty, re-derivation is impossible; this is only tolerated
    (and only produces an un-VERIFIED-provenance row) when ``allow_underived`` is set.
    Otherwise every row is independently re-derived from its source and asserted
    to equal the certificate's own (coeffs, constant, strict).
    """
    idx = json_row["index"]
    source = json_row.get("source") or ""
    json_coeffs = tuple(json_row["coeffs"])
    json_constant = json_row["constant"]
    json_strict = json_row["strict"]
    json_d = json_row.get("d")
    json_spoke_degs = tuple(json_row.get("spoke_degs", ()))

    if source == "":
        if not allow_underived:
            raise VerificationError(
                f"row {idx}: source is empty, re-derivation is impossible "
                f"(pass --allow-underived to accept this row's coeffs on faith -- "
                f"NOT recommended for a real certificate)"
            )
        row = LD.Row(
            coeffs=json_coeffs,
            constant=json_constant,
            strict=json_strict,
            d=json_d if json_d is not None else -1,
            spoke_degs=json_spoke_degs,
            sources=(source,),
        )
        return row, False, "source empty: re-derivation SKIPPED (provenance unverified)"

    row = rederive_row(source, rules)
    got = (row.coeffs, row.constant, row.strict)
    want = (json_coeffs, json_constant, json_strict)
    if got != want:
        raise VerificationError(
            f"row {idx} (source={source!r}): re-derivation MISMATCH.\n"
            f"    certificate claims: coeffs={json_coeffs} constant={json_constant} "
            f"strict={json_strict}\n"
            f"    re-derived:         coeffs={row.coeffs} constant={row.constant} "
            f"strict={row.strict}"
        )
    if json_d is not None and row.d != json_d:
        raise VerificationError(
            f"row {idx} (source={source!r}): re-derived d={row.d} != certificate d={json_d}"
        )
    if json_spoke_degs and row.spoke_degs != json_spoke_degs:
        raise VerificationError(
            f"row {idx} (source={source!r}): re-derived spoke_degs={row.spoke_degs} "
            f"!= certificate spoke_degs={json_spoke_degs}"
        )
    return row, True, "re-derived from source, matches certificate"


# --------------------------------------------------------------------------
# Certificate check
# --------------------------------------------------------------------------


def verify(path: Path, allow_underived: bool, rules=None) -> tuple[bool, str]:
    """Verify the certificate at ``path``. Returns (ok, human-readable report)."""
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        return False, f"FARKAS CERTIFICATE REJECTED: cannot read/parse {path}: {e}"
    return verify_certificate_dict(data, allow_underived, rules=rules, label=str(path))


def verify_certificate_dict(
    data: dict, allow_underived: bool, rules=None, label: str = "<in-memory certificate>"
) -> tuple[bool, str]:
    """Verify an already-parsed certificate dict. Returns (ok, human-readable report).

    This is the core entry point ``verify()`` (path-based) wraps; tests use it directly
    with hand-built dicts so no temp files or subprocess calls are needed.
    """
    lines: list[str] = []

    def p(s: str = "") -> None:
        lines.append(s)

    p(f"Certificate: {label}")

    try:
        for field in ("integral", "n_rows", "multipliers", "rows"):
            if field not in data:
                raise VerificationError(f"certificate JSON missing required field {field!r}")
        integral = bool(data["integral"])
        n_rows_claimed = int(data["n_rows"])
        p(f"integral={integral}  n_rows(full LP, before restricting to support)={n_rows_claimed}")

        multiplier_pairs = data["multipliers"]
        json_rows = data["rows"]

        mult_indices = [int(i) for i, _ in multiplier_pairs]
        row_indices = [int(r["index"]) for r in json_rows]
        if sorted(mult_indices) != sorted(row_indices):
            raise VerificationError(
                "index set of 'multipliers' does not match index set of 'rows': "
                f"multipliers={sorted(mult_indices)} rows={sorted(row_indices)}"
            )
        if len(set(mult_indices)) != len(mult_indices):
            raise VerificationError("duplicate row index in 'multipliers'")

        y_by_index: dict[int, Fraction] = {}
        for i, s in multiplier_pairs:
            y_by_index[int(i)] = Fraction(s)  # exact rational parse, never float

        if not y_by_index:
            raise VerificationError("certificate has an empty support (no multipliers)")

        # Resolve rules lazily -- only needed if some row actually needs re-derivation.
        need_rules = any((r.get("source") or "") != "" for r in json_rows)
        if need_rules and rules is None:
            rules = N.load_rules(RULES_DIR)

        resolved: dict[int, tuple[LD.Row, bool, str]] = {}
        json_row_by_index = {int(r["index"]): r for r in json_rows}
        for idx, jr in sorted(json_row_by_index.items()):
            resolved[idx] = resolve_row(jr, rules, allow_underived)

        # All rows must agree on vector dimension.
        dims = {len(row.coeffs) for row, _, _ in resolved.values()}
        if len(dims) != 1:
            raise VerificationError(f"rows disagree on coefficient-vector length: {dims}")
        n_cols = dims.pop()

        # Cross-check the certificate's own precomputed 'rhs' field against rhs_of().
        for idx, jr in json_row_by_index.items():
            row, _, _ = resolved[idx]
            expect_rhs = LD.rhs_of(row, integral)
            if "rhs" in jr and int(jr["rhs"]) != expect_rhs:
                raise VerificationError(
                    f"row {idx}: certificate 'rhs'={jr['rhs']} but rhs_of(row, integral="
                    f"{integral})={expect_rhs}"
                )

        # --- Farkas conditions, exact Fraction arithmetic only -------------------
        support = sorted(y_by_index)
        neg_multipliers = [i for i in support if y_by_index[i] < 0]
        pos_multipliers = [i for i in support if y_by_index[i] > 0]

        combo = [Fraction(0)] * n_cols
        total_b = Fraction(0)
        for i in support:
            yi = y_by_index[i]
            row, _, _ = resolved[i]
            if yi == 0:
                continue
            for k, c in enumerate(row.coeffs):
                if c:
                    combo[k] += yi * c
            total_b += yi * LD.rhs_of(row, integral)

        neg_cols = [k for k, v in enumerate(combo) if v < 0]
        min_combo = min(combo) if combo else None

        conditions_ok = (
            not neg_multipliers
            and len(pos_multipliers) >= 1
            and not neg_cols
            and total_b < 0
        )

        # --- report: per-row table -------------------------------------------
        p("")
        p(f"Support: {len(support)} rows out of {n_rows_claimed} in the full LP.")
        p("")
        header = f"{'idx':>6} {'y_i':>14} {'d':>3} {'spoke_degs':>16} {'rhs':>5} {'C(x0)':>7}  source"
        p(header)
        p("-" * len(header))

        x0 = None
        if rules is not None:
            x0 = LD.x0_of(rules)

        any_rederived = False
        any_underived = False
        for i in support:
            row, rederived, note = resolved[i]
            any_rederived = any_rederived or rederived
            any_underived = any_underived or not rederived
            rhs = LD.rhs_of(row, integral)
            cx0 = "n/a"
            if x0 is not None and len(row.coeffs) == len(x0):
                cx0 = str(row.value_at(x0))
            sd = ",".join(map(str, row.spoke_degs)) if row.spoke_degs else "-"
            p(
                f"{i:>6} {str(y_by_index[i]):>14} {row.d:>3} {sd:>16} {rhs:>5} {cx0:>7}  "
                f"{row.sources[0] if row.sources else json_row_by_index[i].get('source')}"
                f"{'  [UNDERIVED]' if not rederived else ''}"
            )

        p("")
        p(f"Column check: min_k (y^T A)_k = {min_combo}  (need >= 0)")
        p(f"RHS check:    y^T b           = {total_b}  (need < 0)")
        p(f"Sign check:   negative multipliers = {neg_multipliers}  (need [])")
        p(f"Support size: {len(pos_multipliers)} strictly-positive multiplier(s)  (need >= 1)")
        if neg_cols:
            p(f"Violating columns (y^T A)_k < 0: {neg_cols}")

        if not conditions_ok:
            reasons = []
            if neg_multipliers:
                reasons.append(f"negative multipliers at rows {neg_multipliers}")
            if not pos_multipliers:
                reasons.append("no strictly-positive multiplier (support is all zero)")
            if neg_cols:
                reasons.append(f"(y^T A)_k < 0 for columns {neg_cols}")
            if not (total_b < 0):
                reasons.append(f"y^T b = {total_b} is not < 0")
            raise VerificationError("Farkas conditions failed: " + "; ".join(reasons))

        p("")
        p("Contradiction chain (for any x >= 0 satisfying every row A_i . x <= b_i):")
        p(f"    0  <=  (y^T A) x            [y >= 0, x >= 0]")
        p(f"        =  y^T (A x)            [associativity]")
        p(f"       <=  y^T b                [y >= 0, A x <= b elementwise]")
        p(f"        =  {total_b}")
        p(f"        <  0")
        p("    ==> no x >= 0 satisfies every row in the support ==> LP is infeasible.")

        # --- x0 sanity anchor --------------------------------------------------
        p("")
        if any_underived:
            p("x0 sanity check: SKIPPED (certificate contains underived row(s); "
              "x0 is only meaningful against fully re-derived, real 84-dim rows).")
        elif x0 is None or not any_rederived:
            p("x0 sanity check: SKIPPED (no rules available / no re-derived rows).")
        else:
            violations = []
            for i in support:
                row, _, _ = resolved[i]
                if len(row.coeffs) != len(x0):
                    continue
                v = row.value_at(x0)
                lim = -1 if (row.strict and integral) else 0
                if v > lim:
                    violations.append((i, v, lim))
            if not violations:
                raise VerificationError(
                    "sanity check failed: x0 (published amounts) satisfies EVERY row in "
                    "the support -- the certificate cannot be witnessing x0's own failure"
                )
            p(f"x0 sanity check: x0 VIOLATES {len(violations)} row(s) in the support "
              f"(as expected -- this is exactly why the LP was built):")
            for i, v, lim in violations:
                p(f"    row {i}: C(x0) = {v} > limit {lim}")

        p("")
        p("FARKAS CERTIFICATE VERIFIED")
        return True, "\n".join(lines)

    except VerificationError as e:
        p("")
        p(f"FARKAS CERTIFICATE REJECTED: {e}")
        return False, "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--certificate", type=Path, default=DEFAULT_CERTIFICATE,
                     help=f"path to a Farkas certificate JSON (default: {DEFAULT_CERTIFICATE})")
    ap.add_argument("--allow-underived", action="store_true",
                     help="accept rows with source=='' without re-derivation "
                          "(their coeffs are then trusted on faith; only for tests)")
    args = ap.parse_args(argv)

    ok, report = verify(args.certificate, args.allow_underived)
    print(report)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
