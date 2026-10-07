"""
Traceability guardrails.

These tests are the guardrail for the single-source-of-truth chain:

    FrameDesignModel -> FramePhysicsSolver -> FrameSolverResult -> CAD/drafting/reporting

If a report, drawing sheet or CAD solid restates a value instead of reading it
from the solver, one of these fails. That is exactly how the pre-redesign
numbers (130 mm overhang, 193.33 mm post span, a stale bracket stress)
survived a geometry change in the first place.
"""

from __future__ import annotations

import pytest

from cad.assembly import armrest_primitives
from core.frame_model import (
    ARM_PAD_THICKNESS_MM,
    FrameDesignModel,
    resolve_armrest_shared,
)
from drafting.part_drawings import resolve_armrest_shared as drafting_resolver
from physics.frame_physics import FramePhysicsSolver
from physics.provenance import build_manifest, manifest_dict, write_manifest
from reporting.frame_data_sheet import FrameDataSheetGenerator


@pytest.fixture(scope="module")
def model() -> FrameDesignModel:
    return FrameDesignModel()


@pytest.fixture(scope="module")
def manifest(model: FrameDesignModel):
    return build_manifest(model)


# --------------------------------------------------------------------------
# 1. One geometry instance shared by every layer
# --------------------------------------------------------------------------
def test_all_layers_resolve_the_same_armrest_instance(model: FrameDesignModel):
    """physics, CAD, drafting and reporting must not each resolve independently."""
    g = model.geometry
    kwargs = {
        "side": -1.0,
        "arm_tube_r": g.arm_profile.outer_dimension_mm / 2.0,
        "pad_thickness_mm": ARM_PAD_THICKNESS_MM,
    }
    instances = {
        "cad": resolve_armrest_shared(g, **kwargs),
        "drafting": drafting_resolver(g, **kwargs),
        "reporting": FrameDataSheetGenerator(model).ag,
    }
    ids = {id(v) for v in instances.values()}
    assert len(ids) == 1, f"layers resolved different armrest geometry: {instances.keys()}"


def test_solver_moment_matches_geometry_cantilever(model: FrameDesignModel):
    """The analysed overhang must be the drawn overhang, not a nominal field."""
    g = model.geometry
    ag = resolve_armrest_shared(
        g,
        side=-1.0,
        arm_tube_r=g.arm_profile.outer_dimension_mm / 2.0,
        pad_thickness_mm=ARM_PAD_THICKNESS_MM,
    )
    arm = FramePhysicsSolver.solve(model).armrests[0]
    expected = model.loads.left_arm_vertical_n * ag.cantilever_front_mm / 1000.0
    assert arm.overhang_moment_nm == pytest.approx(expected, abs=1e-9)


def test_cad_tie_rail_equals_resolved_post_span(model: FrameDesignModel):
    """CAD geometry is model-derived, not restated."""
    g = model.geometry
    ag = resolve_armrest_shared(
        g,
        side=-1.0,
        arm_tube_r=g.arm_profile.outer_dimension_mm / 2.0,
        pad_thickness_mm=ARM_PAD_THICKNESS_MM,
    )
    prims = armrest_primitives(ag)
    spans = [
        abs(p["b"][1] - p["a"][1])
        for p in prims
        if p["kind"] == "tube" and abs(p["a"][1] - p["b"][1]) > 1.0
    ]
    assert spans, "no fore/aft tie rail found in the armrest primitives"
    assert max(spans) == pytest.approx(ag.post_span_mm, abs=1e-6)


# --------------------------------------------------------------------------
# 2. Engineering conclusions live in physics/, not in the reporting layer
# --------------------------------------------------------------------------
def test_bracket_analysis_comes_from_the_solver(model: FrameDesignModel):
    result = FramePhysicsSolver.solve(model)
    assert result.arm_brackets, "arm bracket analysis missing from the solver result"
    for brk in result.arm_brackets:
        # Superposition, and the moment is the one the post actually resists.
        assert brk.combined_stress_mpa == pytest.approx(
            brk.axial_stress_mpa + brk.bending_stress_mpa, abs=1e-9
        )
        assert brk.post_base_moment_nm > 0.0
        assert brk.section_area_mm2 > 0.0


def test_bracket_axial_uses_lever_rule_not_a_flat_half(model: FrameDesignModel):
    """A blind 50/50 split is the bug this chain previously hid."""
    result = FramePhysicsSolver.solve(model)
    g = model.geometry
    ag = resolve_armrest_shared(
        g,
        side=-1.0,
        arm_tube_r=g.arm_profile.outer_dimension_mm / 2.0,
        pad_thickness_mm=ARM_PAD_THICKNESS_MM,
    )
    w_front, w_rear = ag.post_reaction_fractions(model.loads.left_arm_load_y_mm)
    expected = model.loads.left_arm_vertical_n * max(w_front, w_rear)
    assert result.arm_brackets[0].post_axial_n == pytest.approx(expected, abs=1e-9)
    assert result.arm_brackets[0].post_axial_n != pytest.approx(
        model.loads.left_arm_vertical_n / 2.0, abs=1e-6
    )


def test_bracket_participates_in_the_pass_fail_verdict(model: FrameDesignModel):
    """A bracket below the design factor must fail the design, not hide."""
    result = FramePhysicsSolver.solve(model)
    assert result.min_arm_bracket_sf == pytest.approx(
        min(b.bracket_safety_factor for b in result.arm_brackets)
    )
    assert result.all_safety_criteria_passed == all(b.passed for b in result.arm_brackets) or (
        not result.arm_brackets
    )


def test_reporting_layer_does_not_recompute_bracket_stress():
    """frame_data_sheet must read the solver, not rebuild the formula."""
    import inspect

    from reporting import frame_data_sheet

    src = inspect.getsource(frame_data_sheet.FrameDataSheetGenerator)
    # The removed re-implementation had these exact shapes.
    for banned in ("_bracket_sigma", "_governing_post_axial_n"):
        assert banned not in src, f"{banned} re-derives solver values in the report layer"
    assert "self.sol.arm_brackets[0]" in src, "bracket section no longer reads the solver"


def test_reporting_layer_uses_physics_marin_factors():
    """Marin factors must come from physics/fatigue.py, not an inline copy."""
    import inspect

    from reporting import academic_engine, frame_data_sheet

    for mod in (frame_data_sheet, academic_engine):
        src = inspect.getsource(mod)
        assert "4.51 * (Sut**-0.265)" not in src, f"{mod.__name__} inlines the Marin k_a"
        assert "1.24 * (d_mm**-0.107)" not in src, f"{mod.__name__} inlines the Marin k_b"
        assert "MarinFactors" in src, f"{mod.__name__} does not use physics.fatigue.MarinFactors"


# --------------------------------------------------------------------------
# 3. The manifest traces back to solver fields
# --------------------------------------------------------------------------
def test_every_manifest_quantity_names_a_source(manifest):
    assert manifest, "manifest is empty"
    for q in manifest:
        assert q.source, f"{q.key} has no provenance source"
        assert q.formula, f"{q.key} has no formula"
        assert q.key, f"{q.key} has no key"


def test_manifest_values_match_the_solver(model: FrameDesignModel):
    result = FramePhysicsSolver.solve(model)
    by_key = {q.key: q for q in build_manifest(model, result)}
    assert by_key["bracket.left.combined_stress"].value == pytest.approx(
        result.arm_brackets[0].combined_stress_mpa, abs=1e-9
    )
    assert by_key["arm.left.base_moment"].value == pytest.approx(
        result.armrests[0].strut_base_moment_nm, abs=1e-9
    )
    assert by_key["leg.min_buckling_sf"].value == pytest.approx(
        result.min_leg_buckling_sf, abs=1e-9
    )


def test_manifest_carries_the_verdict(model: FrameDesignModel):
    d = manifest_dict(model)
    assert d["all_safety_criteria_passed"] is True
    assert d["min_safety_factors"]["arm_bracket"] > 2.0


def test_write_manifest_round_trips(tmp_path, model: FrameDesignModel):
    import json

    path = write_manifest(tmp_path, model)
    assert path.name == "provenance.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["quantities"]
    assert data["material"] == model.material.name


# --------------------------------------------------------------------------
# 4. Generated artifacts carry no stale pre-redesign values
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "stale",
    [
        "193.33",  # old post span (front post at +40)
        "285.44",  # old diagonal brace length
        "66.44",   # old arm base moment at 130 mm overhang
        "65.35",   # old arm post combined stress
        "58.50",   # old cantilever moment
        "138.68",  # old bracket stress
        "356.9",   # old lever-rule axial (79% share)
    ],
)
def test_generated_data_sheet_has_no_stale_values(model: FrameDesignModel, stale: str):
    md = FrameDataSheetGenerator(model).generate_markdown()
    assert stale not in md, f"stale value {stale!r} reappeared in the generated data sheet"
