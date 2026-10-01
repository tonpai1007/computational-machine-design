"""
Test Suite: Automated 2D Technical Drawing Blueprint Generator
"""

from components.gears import GearPairSpecification
from core.models import EngineeringModel, KeywaySpec, ShaftSegment
from drafting.blueprint_2d import Blueprint2DGenerator
from physics.gears import GearSolver
from physics.solver import PhysicsSolver


def test_shaft_blueprint_svg_generation():
    model = EngineeringModel(
        name="Blueprint_Test_Shaft",
        total_length=0.4,
        material_id="AISI_4140_QT",
        segments=[
            ShaftSegment(
                start_pos=0.0, end_pos=0.1, outer_diameter=0.025, feature_type="bearing_seat"
            ),
            ShaftSegment(
                start_pos=0.1, end_pos=0.3, outer_diameter=0.035, feature_type="gear_mount"
            ),
            ShaftSegment(
                start_pos=0.3, end_pos=0.4, outer_diameter=0.025, feature_type="bearing_seat"
            ),
        ],
    )
    result = PhysicsSolver.solve(model)

    svg = Blueprint2DGenerator.generate_shaft_blueprint_svg(model, result, theme="blueprint")

    assert "<svg" in svg
    assert "</svg>" in svg
    assert "MACHINE DESIGN INTELLIGENCE ENGINE" in svg
    assert "BLUEPRINT TEST SHAFT" in svg
    assert "&#x2205;" in svg  # Diameter symbol
    assert "VIEW A-A" in svg  # End projection

    html = Blueprint2DGenerator.generate_html_blueprint_page(svg, title="Test Shaft Blueprint")
    assert "<!DOCTYPE html>" in html
    assert "@media print" in html


def test_shaft_blueprint_renders_keyway():
    """Regression: a keyed shaft must render, with mm-converted keyway values.

    KeywaySpec stores length/width/depth in meters. The blueprint previously
    read non-existent ``length_mm``/``depth_mm``/``width_mm`` attributes, so
    any keyed shaft raised AttributeError instead of drawing its keyway slot.
    """
    model = EngineeringModel(
        name="Keyed_Shaft",
        total_length=0.3,
        material_id="AISI_4140_QT",
        segments=[
            ShaftSegment(
                start_pos=0.0,
                end_pos=0.1,
                outer_diameter=0.025,
                feature_type="bearing_seat",
            ),
            ShaftSegment(
                start_pos=0.1,
                end_pos=0.3,
                outer_diameter=0.035,
                feature_type="gear_mount",
                keyway=KeywaySpec(
                    position=0.12,
                    length=0.014,
                    width=0.008,
                    depth=0.004,
                ),
            ),
        ],
    )
    result = PhysicsSolver.solve(model)

    svg = Blueprint2DGenerator.generate_shaft_blueprint_svg(model, result, theme="technical")

    assert "<!-- Keyway Slot -->" in svg
    # 8 x 4.0 mm, converted from the model's meters.
    assert "DIN 6885-1 (8x4.0)" in svg
    # The slot is a real element with a positive width, not a degenerate one.
    rect = [ln for ln in svg.splitlines() if "<rect" in ln and 'stroke-dasharray="4,2"' in ln]
    assert rect, "keyway slot rect not emitted"


def test_gear_blueprint_svg_generation():
    spec = GearPairSpecification(power_kw=10.0, pinion_speed_rpm=1500.0)
    res = GearSolver.solve(spec)
    svg = Blueprint2DGenerator.generate_gear_blueprint_svg(res, theme="blueprint")

    assert "<svg" in svg
    assert "GEAR MESH SPECIFICATIONS" in svg
    assert "PINION" in svg
    assert "DRIVEN GEAR" in svg
