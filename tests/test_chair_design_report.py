"""Guards Project/chair/chair_design_report.md against drift from the solver.

Two invariants:
1. Scope - the report must contain NO finite-element analysis. All four
   reference reports in Project/REF are closed-form only, so FEA in this
   document is out of scope.
2. Fidelity - every headline number must equal the deterministic solver result.
"""

import math
from pathlib import Path

import pytest

from core.frame_model import FrameDesignModel, resolve_armrest_shared
from physics.fatigue import FatigueSolver, MarinFactors
from physics.frame_physics import FramePhysicsSolver

REPORT = Path(__file__).resolve().parents[1] / "Project" / "chair" / "chair_design_report.md"


@pytest.fixture(scope="module")
def doc():
    if not REPORT.exists():
        pytest.skip(f"report not generated: {REPORT}")
    return REPORT.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sol():
    return FramePhysicsSolver.solve(FrameDesignModel())


# --------------------------------------------------------------------------
# 1. Scope: no FEA
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
        f"report contains out-of-scope term {banned!r}; "
        "Project/REF references are closed-form member sizing only "
        "(no FEA, no whole-machine overturning analysis)"
    )


def test_report_uses_reference_closed_form_markers(doc):
    for marker in [
        "J.B. Johnson",  # intermediate column formula
        "P_cr",  # critical buckling load
        "l/k",  # slenderness ratio
        "〈X-",  # singularity-function notation
        "S_e",  # endurance limit
        "σ_max",  # maximum normal stress
        "Safety Factor",  # factor of safety
    ]:
        assert marker in doc, f"missing reference-style marker {marker!r}"


# --------------------------------------------------------------------------
# 2. Fidelity: headline numbers must match the solver
# --------------------------------------------------------------------------
def _num(doc, value, dp=3):
    """Assert the literal value appears in the document."""
    txt = f"{value:.{dp}f}"
    assert txt in doc, f"expected {txt} in report"


def test_material_properties_match_model(doc):
    m = FrameDesignModel().material
    for v, dp in [
        (m.ultimate_strength_mpa, 0),
        (m.yield_strength_mpa, 0),
        (m.elastic_modulus_gpa, 0),
        (m.density_kg_m3, 0),
    ]:
        _num(doc, v, dp)


def test_section_properties_match_profiles(doc):
    g = FrameDesignModel().geometry
    for prof, vals in [
        (g.leg_profile, (13885.8, 163.36, 9.220, 991.8)),
        (g.frame_profile, (16345.3, 184.00, 9.425, 1307.6)),
        (g.arm_profile, (5872.5, 114.23, 7.170, 533.9)),
        (g.stretcher_profile, (3180.1, 82.47, 6.210, 334.8)),
    ]:
        Ii = prof.moment_of_inertia_m4 * 1e12
        A = prof.area_m2 * 1e6
        k = math.sqrt(Ii / A)
        Z = Ii / (prof.outer_dimension_mm / 2.0)
        for rep, act, dp in zip(vals, (Ii, A, k, Z), (1, 2, 3, 1), strict=False):
            assert abs(rep - act) < 10**-dp, f"section property drift: {rep} vs {act}"


def test_global_equilibrium_matches_solver(doc, sol):
    _num(doc, sol.total_chair_weight_n, 2)
    _num(doc, sol.total_downward_load_n, 2)


def test_column_results_match_solver(doc, sol):
    for c in sol.floor_reactions:
        _num(doc, c.axial_reaction_n, 2)
        _num(doc, c.buckling_safety_factor, 2)
        _num(doc, c.yield_safety_factor, 2)
        _num(doc, c.combined_stress_mpa, 3)


def test_critical_buckling_load_matches_engine(doc, sol):
    _num(doc, sol.floor_reactions[0].critical_buckling_load_n, 2)


def test_seat_rail_matches_solver(doc, sol):
    _num(doc, sol.seat_frame.rail_bending_stress_mpa, 3)
    _num(doc, sol.seat_frame.rail_deflection_mm, 4)
    _num(doc, sol.seat_frame.rail_safety_factor, 2)


def test_arm_matches_solver(doc, sol):
    a = sol.armrests[0]
    _num(doc, a.strut_base_moment_nm, 3)
    _num(doc, a.strut_combined_stress_mpa, 3)
    _num(doc, a.arm_safety_factor, 2)


def test_every_summary_row_clears_design_factor(sol):
    """No row in the reference-style summary may fall below n_d = 2.0."""
    m = FrameDesignModel()
    g, ld, mat = m.geometry, m.loads, m.material
    SY = mat.yield_strength_mpa
    E = mat.elastic_modulus_gpa * 1000.0
    K = 0.85

    arm = sol.armrests[0]
    # bracket: read straight from the solver. An earlier version of this test
    # recomputed it from the gross plate volume (25x12x11) and a 50/50 axial
    # split -- both of which the solver had already abandoned -- and so agreed
    # with the solver only to within 0.09 n while checking the wrong mechanics.
    n_bracket = sol.arm_brackets[0].bracket_safety_factor

    # stretcher: CAD uses splay offset at stretcher height
    sp = g.stretcher_profile
    sI, sA = sp.moment_of_inertia_m4 * 1e12, sp.area_m2 * 1e6
    sk = math.sqrt(sI / sA)
    s_len = g.seat_width_mm + 2 * (g.seat_height_mm - g.stretcher_height_mm) * math.tan(
        math.radians(g.leg_splay_angle_deg)
    )
    slam = K * s_len / sk
    sPcr = sA * (SY - (SY * slam / (2 * math.pi)) ** 2 / E)
    n_stretcher = sPcr / (ld.backrest_force_n / 2.0)

    # backrest post
    lp = g.leg_profile
    lA, lI = lp.area_m2 * 1e6, lp.moment_of_inertia_m4 * 1e12
    lZ = lI / (lp.outer_dimension_mm / 2.0)
    dz = g.backrest_height_above_seat_mm * math.cos(math.radians(g.backrest_angle_deg - 90.0))
    Fb = ld.backrest_force_n / 2.0
    n_backrest = SY / (Fb * dz / lZ + Fb / lA)

    # endurance limit -- governing member is the arm bracket (highest combined
    # stress). Marin factors and the criterion both come from physics/fatigue.py.
    brk = sol.arm_brackets[0]
    ka = MarinFactors.surface_factor(mat.ultimate_strength_mpa, "machined")
    kb = MarinFactors.size_factor(resolve_armrest_shared(
        g, side=-1.0, arm_tube_r=g.arm_profile.outer_dimension_mm / 2.0
    ).bracket_len_mm / 1000.0)
    kc = MarinFactors.load_factor("bending")
    ke = MarinFactors.reliability_factor(0.90)
    Se = ka * kb * kc * 1.0 * ke * 1.0 * (0.5 * mat.ultimate_strength_mpa)
    # The arm is a repeated pulsating load (R = 0), not a rotating shaft, so
    # Se/sigma_max would wrongly judge it as fully reversed.
    n_fatigue = FatigueSolver.repeated_load_fatigue(
        sigma_max_mpa=brk.combined_stress_mpa,
        s_ut_mpa=mat.ultimate_strength_mpa,
        s_y_mpa=mat.yield_strength_mpa,
        s_e_mpa=Se,
        stress_ratio_r=0.0,
    ).governing_nf

    rows = {
        "column buckling": min(c.buckling_safety_factor for c in sol.floor_reactions),
        "column yield": min(c.yield_safety_factor for c in sol.floor_reactions),
        "seat rail": sol.seat_frame.rail_safety_factor,
        "arm post": arm.arm_safety_factor,
        "bracket": n_bracket,
        "stretcher": n_stretcher,
        "backrest post": n_backrest,
        "fatigue": n_fatigue,
    }
    failing = {k: v for k, v in rows.items() if v < 2.0}
    assert not failing, f"summary rows below n_d=2.0: {failing}"


def test_deflection_within_serviceability_limit(sol):
    g = FrameDesignModel().geometry
    assert sol.seat_frame.rail_deflection_mm < g.seat_width_mm / 250.0


# --------------------------------------------------------------------------
# 4. Honesty guards - the three bugs these tests were written for
# --------------------------------------------------------------------------
def test_lateral_tipping_is_none_not_a_sentinel(sol):
    """Lateral arm loads are equal and opposite, so they cancel exactly.

    There is no net roll moment and therefore no lateral tipping case. The
    solver must say so with ``None`` instead of inventing a large number.
    """
    assert sol.tipping_safety_factor_lat is None, (
        "balanced lateral loads give no net roll moment; a numeric margin here "
        "would be a fabricated safety factor"
    )


_RENDER = {
    "reporting.frame_report": lambda Gen, model, result: Gen.generate_html_report(model, result),
    "reporting.academic_engine": lambda Gen, model, result: Gen.generate_assignment_report(model, result),
}


def _render(generator: str, model, result) -> str:
    """Call the public render entry point of the named generator."""
    import importlib

    module_name = generator.rsplit(".", 1)[1]
    if module_name == "frame_report":
        gen_cls = importlib.import_module(generator).FrameReportGenerator
    else:
        gen_cls = importlib.import_module(generator).AcademicAssignmentEngine
    return _RENDER[generator](gen_cls, model, result)


@pytest.mark.parametrize(
    "generator",
    ["reporting.frame_report", "reporting.academic_engine"],
)
def test_fbd_reaction_arrows_satisfy_vertical_equilibrium(generator):
    """The FBD draws one arrow per leg pair.

    Those arrows must add up to the applied load - otherwise the figure
    contradicts the equilibrium it is supposed to illustrate.
    """
    import re

    model = FrameDesignModel()
    result = FramePhysicsSolver.solve(model)
    html = _render(generator, model, result)

    shown = [
        float(v.replace(",", ""))
        for v in re.findall(r"R_(?:left|right) [^<]*?([\d,]+\.?\d*) N", html)
    ]
    assert shown, "no reaction labels found in the FBD"
    total = sum(shown)
    assert total == pytest.approx(result.total_downward_load_n, rel=1e-3), (
        f"FBD reactions sum to {total:.1f} N but the applied load is "
        f"{result.total_downward_load_n:.1f} N - equilibrium is broken in the figure"
    )


@pytest.mark.parametrize(
    "generator",
    ["reporting.frame_report", "reporting.academic_engine"],
)
def test_no_placeholder_safety_factor_in_reports(generator):
    """A sentinel like 1e6 must never reach a rendered deliverable."""
    model = FrameDesignModel()
    html = _render(generator, model, FramePhysicsSolver.solve(model))

    assert "1000000" not in html.replace(",", ""), (
        "report presents the 1e6 sentinel as a computed safety factor"
    )
    assert "N/A" in html, "lateral tipping should be reported as N/A, not omitted"
