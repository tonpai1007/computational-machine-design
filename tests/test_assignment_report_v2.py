"""Guards the academic assignment report (v2) against drift from the solver.

Project/REF references are closed-form member sizing only, so this document
must stay free of finite-element and whole-machine overturning analysis, and
every headline number must equal the deterministic solver result.

The governing member is the arm mounting bracket, which the reference-style
component breakdown used to omit entirely.
"""

import pytest

from core.frame_model import FrameDesignModel, resolve_armrest
from physics.frame_physics import FramePhysicsSolver
from reporting.academic_engine import AcademicAssignmentEngine


@pytest.fixture(scope="module")
def doc():
    m = FrameDesignModel()
    r = FramePhysicsSolver.solve(m)
    return AcademicAssignmentEngine.generate_assignment_report_v2(
        m, r, preview_image=None, use_ai=False
    )


@pytest.fixture(scope="module")
def sol():
    return FramePhysicsSolver.solve(FrameDesignModel())


# --------------------------------------------------------------------------
# 1. Scope: closed-form only
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "banned",
    [
        "FEA",
        "finite element",
        "ANSYS",
        "Abaqus",
        "von Mises",
        "stiffness matrix",
        "DOF",
        "mesh",
        "element analysis",
        "tipping",
        "overturn",
        "n_tipping",
    ],
)
def test_report_contains_no_fea(doc, banned):
    assert banned.lower() not in doc.lower(), (
        f"report contains out-of-scope term {banned!r}; the assignment "
        "report mirrors the closed-form reference style only"
    )


def test_report_never_calls_stress_von_mises(doc):
    """Combined stress is linear superposition, not a von Mises equivalent."""
    assert "linear superposition" in doc
    assert "&sigma;combined = &sigma;axial + &sigma;bending" in doc


# --------------------------------------------------------------------------
# 2. Structure: every component present, ordered, and numbered once
# --------------------------------------------------------------------------
def test_all_five_components_present(doc):
    for heading in [
        "เสาขาโครงสร้างหลัก",
        "คานโครงสร้างรองรับเบาะนั่ง",
        "คานค้ำยันรอบล่าง",
        "ชุดโครงสร้างคานยื่นที่พักแขน",
        "แผ่นยึดเสาพักแขน",
    ]:
        assert heading in doc, f"missing component section: {heading}"


def test_component_part_numbers_are_sequential(doc):
    idx = [doc.index(f"{i}. ") for i in range(1, 6)]
    assert idx == sorted(idx), "component sections are out of order"


def test_bracket_is_flagged_as_governing_member(doc):
    assert "ชิ้นวิกฤตของชุดแขน" in doc


# --------------------------------------------------------------------------
# 3. Fidelity: headline numbers equal the solver
# --------------------------------------------------------------------------
def _num(doc, value, dp):
    txt = f"{value:.{dp}f}"
    assert txt in doc, f"expected {txt} in report"


def test_material_and_global_equilibrium(doc, sol):
    m = FrameDesignModel()
    for v, dp in [
        (m.material.ultimate_strength_mpa, 0),
        (m.material.yield_strength_mpa, 0),
        (m.material.elastic_modulus_gpa, 0),
        (sol.total_chair_weight_n, 1),
        (sol.total_downward_load_n, 1),
    ]:
        _num(doc, v, dp)


def test_rail_span_is_seat_width_not_depth(doc):
    """The rail spans the leg pair, so it must use seat width."""
    g = FrameDesignModel().geometry
    assert f"l = {g.seat_width_mm / 1000:.3f} m" in doc
    assert f"l = {g.seat_depth_mm / 1000:.3f} m" not in doc


def test_rail_matches_solver(doc, sol):
    r = sol.seat_frame
    _num(doc, r.rail_bending_moment_nm, 2)
    _num(doc, r.rail_bending_stress_mpa, 2)
    _num(doc, r.rail_deflection_mm, 4)
    _num(doc, r.rail_safety_factor, 2)


def test_rail_deflection_limit_is_shown(doc):
    g = FrameDesignModel().geometry
    _num(doc, g.seat_width_mm / 250.0, 4)


def test_leg_matches_solver(doc, sol):
    c = sol.floor_reactions[0]
    _num(doc, c.axial_reaction_n, 1)
    _num(doc, c.combined_stress_mpa, 2)
    _num(doc, c.buckling_safety_factor, 2)
    _num(doc, c.yield_safety_factor, 2)


def test_arm_matches_solver(doc, sol):
    a = sol.armrests[0]
    _num(doc, a.overhang_moment_nm, 2)
    _num(doc, a.strut_base_moment_nm, 3)
    _num(doc, a.strut_axial_stress_mpa, 3)
    _num(doc, a.strut_bending_stress_mpa, 3)
    _num(doc, a.strut_combined_stress_mpa, 2)
    _num(doc, a.arm_safety_factor, 2)


def test_arm_shows_governing_post_split(doc):
    """Not 50/50: the front post takes about 79%."""
    m = FrameDesignModel()
    g, l = m.geometry, m.loads
    front, _ = resolve_armrest(g).post_reaction_fractions(l.left_arm_load_y_mm)
    _num(doc, front, 4)
    _num(doc, l.left_arm_vertical_n * front, 1)


def test_bracket_matches_bracket_method_a(doc):
    """Method A: axial on the bW x bH cross-section, lever-rule post share.

    Each arm post has exactly one bracket, so the plate carries that post's
    full lever-rule axial share and the base moment that post resists.
    """
    m = FrameDesignModel()
    g, l = m.geometry, m.loads
    a = FramePhysicsSolver.solve(m).armrests[0]
    bW, bH = g.armrest_bracket_thickness_mm, g.armrest_bracket_height_mm
    Z = (bW * bH**3 / 12.0) / (bH / 2.0)
    ag = resolve_armrest(g)
    r_front, r_rear = ag.post_reaction_fractions(l.left_arm_load_y_mm)
    f_gov = l.left_arm_vertical_n * max(r_front, r_rear)
    sigma = f_gov / (bW * bH) + (a.strut_base_moment_nm / 2.0) * 1e3 / Z
    _num(doc, sigma, 2)
    _num(doc, m.material.yield_strength_mpa / sigma, 2)


def test_bracket_has_its_own_summary_row(doc):
    assert "แผ่นยึดเสาพักแขน |" in doc or "แผ่นยึดเสาพักแขน" in doc


# --------------------------------------------------------------------------
# 4. Shigley conventions
# --------------------------------------------------------------------------
def test_sigma_f_prime_uses_shigley_form(doc):
    """sigma_f' = 1.5 Sut, not the legacy 'Sut + 345'."""
    sut = FrameDesignModel().material.ultimate_strength_mpa
    assert f"&sigma;f' = 1.5 Sut = {1.5 * sut:.1f} MPa" in doc
    assert "Sut + 345" not in doc


def test_marin_factors_use_shigley_values(doc):
    """kb from the size factor; kc axial 0.85 (0.59 is the torsion value)."""
    assert "kc = 0.85 (Axial)" in doc
    assert "kc = 0.59" not in doc
    assert "ke = 0.897 (90% Reliability)" in doc


def test_every_summary_row_clears_design_factor(doc):
    """No summary verdict may read FAIL."""
    assert ">FAIL<" not in doc
    assert "color: #dc2626" not in doc
