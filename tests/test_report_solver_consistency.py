"""Cross-tier consistency: every renderer must print the same solver numbers.

The academic dossier (v1), the assignment report (v2), the core calculation
sheet and the verified data sheet all describe one deterministic solver run.
If any of them re-derives a value instead of reading it from
``FrameSolverResult``, its number drifts from the others and this test fails.

This is the guard for the reporting-layer extraction: physics lives in
``physics/`` (``frame_physics.py`` + ``frame_checks.py``), and reporting only
formats.
"""

from __future__ import annotations

import pytest

from core.frame_model import FrameDesignModel
from physics.frame_physics import FramePhysicsSolver
from reporting.academic_engine import AcademicAssignmentEngine
from reporting.frame_data_sheet import FrameDataSheetGenerator
from reporting.frame_report import FrameReportGenerator
from reporting.spec import build_academic_v2_spec

TIERS = ("academic_v1", "academic_v2", "calculation_sheet", "data_sheet")


@pytest.fixture(scope="module")
def rendered() -> tuple[object, dict[str, str]]:
    model = FrameDesignModel()
    sol = FramePhysicsSolver.solve(model)
    docs = {
        "academic_v1": AcademicAssignmentEngine.generate_assignment_report(
            model, sol, preview_image=None
        ),
        "academic_v2": AcademicAssignmentEngine.generate_assignment_report_v2(
            model, sol, preview_image=None, use_ai=False
        ),
        "calculation_sheet": FrameReportGenerator.generate_html_report(model, sol),
        "data_sheet": FrameDataSheetGenerator(model).generate_markdown(),
    }
    return sol, docs


def _headline_values(sol: object) -> dict[str, float]:
    return {
        "min leg buckling SF": sol.min_leg_buckling_sf,
        "min leg yield SF": sol.min_leg_yield_sf,
        "seat rail bending stress": sol.seat_frame.rail_bending_stress_mpa,
        "seat rail safety factor": sol.seat_frame.rail_safety_factor,
        "arm bracket combined stress": sol.arm_brackets[0].combined_stress_mpa,
        "arm safety factor": sol.armrests[0].arm_safety_factor,
        "stretcher governing SF": sol.stretchers[0].governing_safety_factor,
    }


@pytest.mark.parametrize("tier", TIERS)
def test_every_tier_prints_the_solver_value(rendered, tier):
    sol, docs = rendered
    doc = docs[tier]
    for label, value in _headline_values(sol).items():
        expected = f"{value:.2f}"
        assert expected in doc, (
            f"{tier} does not print the solver's {label} ({expected}); "
            "the renderer may be re-deriving it instead of reading FrameSolverResult"
        )


@pytest.mark.parametrize("tier", ["academic_v1", "calculation_sheet"])
def test_tiers_use_the_solver_effective_length(rendered, tier):
    """Effective length is K x unbraced length from the solver, not a local guess."""
    sol, docs = rendered
    buck = sol.floor_reactions[0].buckling
    effective_mm = f"{buck.effective_length_m * 1000:.1f}"
    assert effective_mm in docs[tier], (
        f"{tier} does not show the solver's effective length {effective_mm} mm"
    )


def test_solver_exposes_the_transition_slenderness_used_by_reports(rendered):
    sol, _ = rendered
    leg = sol.floor_reactions[0]
    assert leg.transition_slenderness_ratio == pytest.approx(
        leg.buckling.transition_slenderness_ratio
    )
    assert leg.transition_slenderness_ratio > 0.0


def test_solver_exposes_each_member_fatigue_assessment(rendered):
    """Every member a report discusses carries its own fatigue assessment."""
    sol, _ = rendered
    assessments = [
        sol.floor_reactions[0].fatigue,
        sol.armrests[0].fatigue,
        sol.arm_brackets[0].fatigue,
        sol.seat_frame.fatigue,
    ]
    for a in assessments:
        assert a.endurance_limit_mpa > 0.0
        assert a.fatigue_strength_at_1e4_mpa > 0.0
        assert a.repeated_load is not None


def test_v2_prints_the_solver_endurance_limits(rendered):
    """The dossier's Se values must be the solver's, not a second Marin chain."""
    sol, docs = rendered
    doc = docs["academic_v2"]
    expected = {
        "leg Se": sol.floor_reactions[0].fatigue.endurance_limit_mpa,
        "rail Se": sol.seat_frame.fatigue.endurance_limit_mpa,
        "arm Se": sol.armrests[0].fatigue.endurance_limit_mpa,
        "bracket Se": sol.arm_brackets[0].fatigue.endurance_limit_mpa,
    }
    for label, value in expected.items():
        assert f"{value:.2f}" in doc, f"academic_v2 does not print the solver's {label}"


def test_data_sheet_prints_the_solver_bracket_endurance(rendered):
    sol, docs = rendered
    value = sol.arm_brackets[0].fatigue.endurance_limit_mpa
    assert f"{value:.2f}" in docs["data_sheet"]


def test_solver_exposes_arm_and_bracket_section_properties(rendered):
    """Reports format section data; they no longer rebuild it from the profile."""
    sol, _ = rendered
    geom = FrameDesignModel().geometry
    arm = sol.armrests[0]
    assert arm.section_area_m2 == pytest.approx(geom.arm_profile.area_m2)
    assert arm.moment_of_inertia_m4 == pytest.approx(
        geom.arm_profile.moment_of_inertia_m4
    )
    assert arm.extreme_fibre_m == pytest.approx(geom.arm_profile.outer_dim_m / 2.0)
    assert arm.section_modulus_m3 == pytest.approx(geom.arm_profile.section_modulus_m3)
    assert arm.radius_of_gyration_m == pytest.approx(
        geom.arm_profile.radius_of_gyration_m
    )

    bracket = sol.arm_brackets[0]
    assert bracket.extreme_fibre_mm == pytest.approx(
        geom.armrest_bracket_height_mm / 2.0
    )


def test_solver_exposes_the_buckling_end_condition_constant(rendered):
    sol, _ = rendered
    leg = sol.floor_reactions[0]
    assert leg.buckling.end_condition_c == pytest.approx(1.0)
    assert leg.buckling.extreme_fibre_m == pytest.approx(
        FrameDesignModel().geometry.leg_profile.outer_dim_m / 2.0
    )


def test_solver_owns_the_arm_lever_rule_and_load_case(rendered):
    """The lever-rule split is statics, so the report must read it, not redo it."""
    sol, _ = rendered
    model = FrameDesignModel()
    arm = sol.armrests[0]
    loads = model.loads

    assert arm.load_y_mm == pytest.approx(loads.left_arm_load_y_mm)
    assert arm.front_reaction_fraction + arm.rear_reaction_fraction == pytest.approx(1.0)
    assert arm.governing_axial_n == pytest.approx(
        arm.applied_vertical_n
        * max(arm.front_reaction_fraction, arm.rear_reaction_fraction)
    )
    assert arm.rear_axial_n == pytest.approx(
        arm.applied_vertical_n * arm.rear_reaction_fraction
    )
    assert arm.applied_vertical_n == pytest.approx(loads.left_arm_vertical_n)
    assert arm.applied_lateral_n == pytest.approx(abs(loads.left_arm_lateral_n))
    assert arm.post_height_m == pytest.approx(
        model.geometry.armrest_height_above_seat_mm / 1000.0
    )
    assert arm.overhang_m == pytest.approx(
        model.geometry.armrest_overhang_front_mm / 1000.0
    )


def test_v2_spec_reads_the_solver_arm_load_case(rendered):
    sol, _ = rendered
    spec = build_academic_v2_spec(FrameDesignModel(), sol)
    arm = sol.armrests[0]
    assert spec.arm is not None
    assert spec.arm.load_y_mm == arm.load_y_mm
    assert spec.arm.front_fraction == arm.front_reaction_fraction
    assert spec.arm.rear_fraction == arm.rear_reaction_fraction
    assert spec.arm.governing_post_force_n == arm.governing_axial_n
    assert spec.arm.rear_post_force_n == arm.rear_axial_n
    assert spec.arm.applied_vertical_n == arm.applied_vertical_n
    assert spec.arm.applied_lateral_n == arm.applied_lateral_n
    assert spec.arm.post_height_m == arm.post_height_m
    assert spec.arm.overhang_m == arm.overhang_m


def test_v2_spec_reads_solver_section_properties(rendered):
    sol, _ = rendered
    spec = build_academic_v2_spec(FrameDesignModel(), sol)
    arm = sol.armrests[0]
    assert spec.arm is not None
    assert spec.arm.area_m2 == arm.section_area_m2
    assert spec.arm.inertia_m4 == arm.moment_of_inertia_m4
    assert spec.arm.extreme_fibre_m == arm.extreme_fibre_m
    assert spec.arm.section_modulus_m3 == arm.section_modulus_m3
    assert spec.bracket is not None
    assert spec.bracket.extreme_fibre_mm == sol.arm_brackets[0].extreme_fibre_mm


def test_calculation_sheet_uses_the_solver_deflection_criterion(rendered):
    """The sheet must not advertise a laxer limit than the solver applied."""
    sol, docs = rendered
    beam = sol.seat_frame.beam
    doc = docs["calculation_sheet"]
    assert f"{beam.deflection_safety_factor:.2f}" in doc
    assert "L / 250" in doc
    assert "L / 120" not in doc
