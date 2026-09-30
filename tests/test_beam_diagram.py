"""Tests for the Mermaid beam-diagram generator."""

import re

import pytest

from mdie.core.frame_model import FrameDesignModel
from mdie.physics.frame_physics import FramePhysicsSolver
from mdie.drafting.beam_diagram import SimplySupportedRail, build_blocks


@pytest.fixture
def rail():
    return SimplySupportedRail(span_mm=480.0, point_load_n=650.0)


def test_reactions_are_half_the_load(rail):
    assert rail.r1_n == pytest.approx(325.0)
    assert rail.r2_n == pytest.approx(325.0)


def test_equilibrium_closes(rail):
    sum_fy, sum_m = rail.verify_equilibrium()
    assert sum_fy == pytest.approx(0.0, abs=1e-9)
    assert sum_m == pytest.approx(0.0, abs=1e-9)


def test_shear_jumps_at_load_and_support(rail):
    # Just inside the left support the reaction is already applied.
    assert rail.shear(0.0) == pytest.approx(325.0)
    # Continuous up to the load, then drops by P.
    assert rail.shear(239.0) == pytest.approx(325.0)
    assert rail.shear(241.0) == pytest.approx(-325.0)
    # Right-hand reaction closes the diagram back to zero.
    assert rail.shear(480.0) == pytest.approx(0.0)


def test_moment_peaks_at_midspan(rail):
    assert rail.moment(0.0) == pytest.approx(0.0)
    assert rail.moment(480.0) == pytest.approx(0.0)
    assert rail.moment(240.0) == pytest.approx(rail.moment_max())
    assert rail.moment_max() == pytest.approx(650.0 * 480.0 / 4.0)
    for x in (0, 60, 120, 180, 300, 360, 420, 480):
        assert rail.moment(x) <= rail.moment_max() + 1e-9


def test_shear_integrates_to_moment(rail):
    """dM/dx = V, checked numerically over each half-span."""
    for lo, hi in ((0.0, 240.0), (240.0, 480.0)):
        n = 2000
        dx = (hi - lo) / n
        area = sum(rail.shear(lo + (i + 0.5) * dx) for i in range(n)) * dx
        assert area == pytest.approx(rail.moment(hi) - rail.moment(lo), rel=1e-3)


def test_stations_evenly_spaced(rail):
    xs = rail.stations(8)
    assert len(xs) == 9
    assert xs[0] == pytest.approx(0.0)
    assert xs[-1] == pytest.approx(480.0)
    steps = [round(b - a, 6) for a, b in zip(xs, xs[1:])]
    assert len(set(steps)) == 1


def test_build_blocks_matches_deterministic_solver():
    """The generated ordinates must agree with the real solver."""
    v_block, m_block, fbd_block, gen_rail = build_blocks(8)

    model = FrameDesignModel()
    result = FramePhysicsSolver.solve(model)

    # M_max cross-check
    assert gen_rail.moment_max() / 1e3 == pytest.approx(
        result.seat_frame.rail_bending_moment_nm, abs=1e-6
    )
    # Stress cross-check
    z_mm3 = model.geometry.frame_profile.section_modulus_m3 * 1e9
    assert gen_rail.moment_max() / z_mm3 == pytest.approx(
        result.seat_frame.rail_bending_stress_mpa, abs=1e-6
    )
    # M_max lands on the solver's stress ratio
    assert gen_rail.p_n == pytest.approx(model.loads.seat_vertical_load_n / 2.0)

    for block in (v_block, m_block):
        assert block.startswith("```mermaid\nxychart-beta\n")
        assert block.rstrip().endswith("```")
        assert block.count("```") == 2


def test_blocks_are_wellformed_xychart():
    v_block, m_block, _fbd_block, _ = build_blocks(8)
    for block in (v_block, m_block):
        body = block.split("xychart-beta\n", 1)[1]
        assert re.search(r'^\s*title "', body, re.M)
        assert re.search(r'^\s*x-axis "', body, re.M)
        assert re.search(r"^\s*y-axis .*-->", body, re.M)
        line = re.search(r"^\s*line \[([^\]]*)\]$", body, re.M)
        assert line, "missing line series"
        values = [float(v) for v in line.group(1).split(",")]
        # Series length must equal the number of x categories.
        xaxis = re.search(r'^\s*x-axis "[^"]*" \[([^\]]*)\]$', body, re.M)
        xs = [float(v) for v in xaxis.group(1).split(",")]
        assert len(values) == len(xs)


def test_shear_series_magnitude_within_plot_range():
    """Shear ordinates must sit inside the declared y-axis window."""
    v_block, _, _, _ = build_blocks(8)
    body = v_block.split("xychart-beta\n", 1)[1]
    values = [float(v) for v in
              re.search(r"^\s*line \[([^\]]*)\]$", body, re.M).group(1).split(",")]
    yaxis = re.search(r"^\s*y-axis \"[^\"]*\" (-?[\d.]+) --> (-?[\d.]+)$",
                      body, re.M)
    lo, hi = float(yaxis.group(1)), float(yaxis.group(2))
    assert lo < 0 < hi
    assert all(lo <= v <= hi for v in values)
    assert max(values) == pytest.approx(325.0)
    assert min(values) == pytest.approx(-325.0)


def test_moment_series_starts_and_ends_at_zero():
    _, m_block, _, _ = build_blocks(8)
    body = m_block.split("xychart-beta\n", 1)[1]
    values = [float(v) for v in
              re.search(r"^\s*line \[([^\]]*)\]$", body, re.M).group(1).split(",")]
    assert values[0] == pytest.approx(0.0)
    assert values[-1] == pytest.approx(0.0)
    assert max(values) == pytest.approx(78000.0)


def test_mermaid_pair_present_in_report():
    from mdie.drafting.beam_diagram import REPORT_MD

    text = REPORT_MD.read_text(encoding="utf-8")
    # Only the shear and moment charts are Mermaid; the FBD is a plotted image.
    assert text.count("```mermaid") == 2
    assert "xychart-beta" in text
    assert "diagrams/fbd_cross_rail.png" in text
    # No stray ASCII free-body diagram left behind.
    assert "─────┬" not in text


def test_fbd_is_a_rendered_image_not_mermaid():
    """The FBD must be a real plot; a Mermaid flowchart is not an FBD."""
    from mdie.drafting.beam_diagram import REPORT_MD

    text = REPORT_MD.read_text(encoding="utf-8")
    assert "flowchart TB" not in text
    assert (REPORT_MD.parent / "diagrams" / "fbd_cross_rail.png").exists()
