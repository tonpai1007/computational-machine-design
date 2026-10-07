"""
Tests for the ``mdie trace`` interface.

The views are how a user inspects the physics chain, so these lock in two
things: every view renders without recomputing any value, and the numbers it
shows are exactly the solver's.
"""

from __future__ import annotations

import io
from argparse import Namespace

import pytest
from rich.console import Console

from core.frame_model import FrameDesignModel
from physics.frame_physics import FramePhysicsSolver
from reporting.trace_view import (
    _MEMBERS,
    render,
    render_member,
    render_pipeline,
    render_steps,
    render_values,
)


@pytest.fixture
def model() -> FrameDesignModel:
    return FrameDesignModel()


def _render(fn, *args, **kwargs) -> str:
    """Render to a string buffer instead of the real terminal."""
    buf = io.StringIO()
    con = Console(file=buf, width=140, force_terminal=False, no_color=True, legacy_windows=False)
    fn(con, *args, **kwargs)
    return buf.getvalue()


# --------------------------------------------------------------------------
# every view renders
# --------------------------------------------------------------------------
def test_pipeline_view_renders(model: FrameDesignModel):
    out = _render(render_pipeline, model)
    assert "How the number gets made" in out
    assert "FrameSolverResult" in out
    assert "Agreement checks" in out
    assert "Governing safety factors" in out


def test_steps_view_renders(model: FrameDesignModel):
    out = _render(render_steps, model)
    assert "Solver derivation" in out
    # The log must explain the arm and bracket, not stop at column buckling.
    assert "Arm bracket" in out
    assert "lever rule" in out
    assert "Verification verdict" in out


def test_values_view_renders(model: FrameDesignModel):
    out = _render(render_values, model)
    assert "arm_brackets.left.bracket_safety_factor" in out
    assert "263.333" in out  # post span


@pytest.mark.parametrize("member", _MEMBERS)
def test_every_member_view_renders(member: str, model: FrameDesignModel):
    out = _render(render_member, member, model)
    assert out.strip(), f"member view {member!r} produced no output"


def test_unknown_member_is_reported_not_crashed(model: FrameDesignModel):
    out = _render(render_member, "nope", model)
    assert "unknown member" in out
    for member in _MEMBERS:
        assert member in out


# --------------------------------------------------------------------------
# the views show solver values, not recomputed ones
# --------------------------------------------------------------------------
def test_bracket_view_shows_solver_numbers(model: FrameDesignModel):
    result = FramePhysicsSolver.solve(model)
    b = result.arm_brackets[0]
    out = _render(render_member, "bracket", model)
    assert f"{b.combined_stress_mpa:.3f}" in out
    assert f"{b.bracket_safety_factor:.3f}" in out
    assert f"{b.post_axial_n:.1f}" in out
    assert f"{b.section_modulus_mm3:.2f}" in out


def test_arm_view_shows_solver_numbers(model: FrameDesignModel):
    result = FramePhysicsSolver.solve(model)
    a = result.armrests[0]
    out = _render(render_member, "arm", model)
    assert f"{a.strut_base_moment_nm:.3f}" in out
    assert f"{a.arm_safety_factor:.3f}" in out
    assert f"{result.arm_brackets[0].post_axial_n:.1f}" in out


def test_rail_view_shows_limit_and_margin(model: FrameDesignModel):
    model_geometry = model.geometry
    limit = model_geometry.seat_width_mm / 250.0
    out = _render(render_member, "rail", model)
    assert f"{limit:.4f}" in out  # L/250 limit is stated, not hidden
    assert "within limit" in out


def test_pipeline_reports_agreement(model: FrameDesignModel):
    """The agreement checks must actually pass, not just be displayed."""
    out = _render(render_pipeline, model)
    assert "NO" not in out, "an agreement check failed"


def test_tipping_view_marks_absent_lateral_case(model: FrameDesignModel):
    """A None lateral margin must read as n/a, never as a large number."""
    out = _render(render_member, "tipping", model)
    assert "n/a" in out
    assert "not 'infinitely safe'" in out


# --------------------------------------------------------------------------
# dispatch
# --------------------------------------------------------------------------
def _render_dispatch(args, model: FrameDesignModel) -> str:
    """Run the dispatching entry point into a string buffer."""
    buf = io.StringIO()
    render(args, model, console=Console(file=buf, width=140, force_terminal=False, no_color=True))
    return buf.getvalue()


def test_render_dispatches_pipeline_by_default(model: FrameDesignModel):
    out = _render_dispatch(Namespace(member=None, steps=False, values=False), model)
    assert "How the number gets made" in out


@pytest.mark.parametrize(
    "args,expected",
    [
        (Namespace(member="bracket", steps=False, values=False), "derivation"),
        (Namespace(member=None, steps=True, values=False), "Solver derivation"),
        (Namespace(member=None, steps=False, values=True), "Provenance"),
        (Namespace(member=None, steps=False, values=False), "How the number gets made"),
    ],
)
def test_render_selects_the_right_view(args, expected: str, model: FrameDesignModel):
    assert expected in _render_dispatch(args, model)


# --------------------------------------------------------------------------
# the solver log itself
# --------------------------------------------------------------------------
def test_calculation_log_covers_every_member(model: FrameDesignModel):
    """The log must name the field each step produced, for every member."""
    log = model and FramePhysicsSolver.solve(model).calculation_log
    joined = "\n".join(log)
    assert "floor_reactions[" in joined
    assert "armrests.left." in joined
    assert "arm_brackets.left." in joined
    assert "seat_frame.rail_safety_factor" in joined
    assert "all_safety_criteria_passed" in joined


def test_calculation_log_values_match_the_result_fields(model: FrameDesignModel):
    """Numbers quoted in the log must equal the fields they claim to produce."""
    result = FramePhysicsSolver.solve(model)
    joined = "\n".join(result.calculation_log)
    b = result.arm_brackets[0]
    assert f"{b.bracket_safety_factor:.2f}" in joined
    assert f"{b.combined_stress_mpa:.3f}" in joined
    a = result.armrests[0]
    assert f"{a.strut_base_moment_nm:.3f}" in joined
