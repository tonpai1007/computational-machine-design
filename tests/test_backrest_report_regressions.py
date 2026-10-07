"""Regression tests for two reporting-layer bugs that silently deflated results.

Both lived in ``reporting/frame_data_sheet.py`` and both produced a plausible
number rather than an error, which is why they survived:

1. The backrest moment arm used ``sin(angle - 90)`` -- the post's *horizontal*
   lean -- instead of ``cos``, which is the vertical rise a horizontal thrust
   actually acts through.
2. The same block divided ``F * dz`` by ``1e3`` before dividing by a section
   modulus expressed in mm**3, feeding N.m into a mm**3 denominator.

Between them they understated the backrest post by ~1000x (n = 377 reported
against a true n = 5.80). The 3D FEA independently reports ~63.83 MPa for the
same member, so it serves as an oracle.

Each test reads the *generated datasheet*, not a local recomputation -- a test
that recomputes the formula itself passes even while the module is broken.
"""

import math
import re

import pytest

from core.frame_model import STRUCTURAL_MATERIALS, FrameDesignModel
from physics.fea_3d import build_chair_3d_fea_model
from reporting.frame_data_sheet import FrameDataSheetGenerator


@pytest.fixture(scope="module")
def model():
    return FrameDesignModel(name="x", material=STRUCTURAL_MATERIALS["STEEL_1018"])


@pytest.fixture(scope="module")
def md():
    return FrameDataSheetGenerator(
        FrameDesignModel(name="x", material=STRUCTURAL_MATERIALS["STEEL_1018"])
    ).generate_markdown()


def _cell(md_text: str, row_label: str, *, within: str | None = None) -> float:
    """Pull the numeric value out of a '| <row label> | <value> |' datasheet row.

    ``within`` scopes the search to a numbered section, because labels such as
    ``n = S_y/σ`` are reused across sections.
    """
    if within is not None:
        start = md_text.index(within)
        end = md_text.find("\n## ", start + 1)
        md_text = md_text[start : end if end != -1 else None]
    m = re.search(rf"^\|\s*{re.escape(row_label)}\s*\|\s*([-\d.]+)", md_text, re.M)
    assert m, f"row {row_label!r} not found in datasheet"
    return float(m.group(1))


BACKREST = "## 10. เสาหลังนั่ง"


def test_backrest_moment_arm_is_the_vertical_rise(model, md):
    """A horizontal thrust's moment arm is cos(tilt), not sin(tilt)."""
    g = model.geometry
    h = g.backrest_height_above_seat_mm
    tilt = g.backrest_angle_deg - 90.0
    vertical = h * math.cos(math.radians(tilt))
    horizontal = h * math.sin(math.radians(tilt))

    reported = _cell(md, "ระยะแนวดิ่งของโมเมนต์ dz", within=BACKREST)
    assert reported == pytest.approx(vertical, rel=1e-3), (
        f"datasheet moment arm {reported:.3f} mm matches sin (the horizontal "
        f"lean, {horizontal:.3f} mm) instead of cos (the vertical rise, "
        f"{vertical:.3f} mm)"
    )
    assert reported > 5 * horizontal


def test_backrest_stress_matches_the_3d_fea_oracle(model, md):
    """The closed-form backrest stress must agree with the direct-stiffness FEA.

    The FEA is an independent implementation, so agreement is meaningful; only
    the closed-form path carried the bugs.
    """
    r = build_chair_3d_fea_model(model).solve()
    fea = [
        v["von_mises_mpa"]
        for v in r["members"]
        if "Back_Base" in str(v.get("member_id", ""))
    ]
    assert fea, "FEA no longer exposes the backrest base member"

    reported = _cell(md, "σ = F·dz/Z + F/A", within=BACKREST)
    assert reported == pytest.approx(max(fea), rel=0.02), (
        f"datasheet backrest stress {reported:.3f} MPa disagrees with "
        f"FEA {max(fea):.3f} MPa"
    )


def test_backrest_units_are_n_mm_over_mm3(md):
    """N.m must not reach an mm**3 denominator.

    Regression for ``fb * dz / 1e3 / lZ``, which reported n = 377.1 instead of
    n = 5.80 -- a plausible-looking margin that was wrong by ~65x.
    """
    assert _cell(md, "σ = F·dz/Z + F/A", within=BACKREST) == pytest.approx(63.82, rel=1e-3)
    assert _cell(md, "n = S_y/σ", within=BACKREST) == pytest.approx(5.798, rel=1e-3)
    assert "377" not in md, "the 1e3 units bug is back"
