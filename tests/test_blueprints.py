"""
Test Suite: Automated 2D Technical Drawing Blueprint Generator
"""

import pytest
from mdie.core.models import EngineeringModel, ShaftSegment
from mdie.physics.solver import PhysicsSolver
from mdie.reports.blueprint_2d import Blueprint2DGenerator
from mdie.components.gears import GearPairSpecification
from mdie.physics.gears import GearSolver


def test_shaft_blueprint_svg_generation():
    model = EngineeringModel(
        name="Blueprint_Test_Shaft",
        total_length=0.4,
        material_id="AISI_4140_QT",
        segments=[
            ShaftSegment(start_pos=0.0, end_pos=0.1, outer_diameter=0.025, feature_type="bearing_seat"),
            ShaftSegment(start_pos=0.1, end_pos=0.3, outer_diameter=0.035, feature_type="gear_mount"),
            ShaftSegment(start_pos=0.3, end_pos=0.4, outer_diameter=0.025, feature_type="bearing_seat"),
        ]
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


def test_gear_blueprint_svg_generation():
    spec = GearPairSpecification(power_kw=10.0, pinion_speed_rpm=1500.0)
    res = GearSolver.solve(spec)
    svg = Blueprint2DGenerator.generate_gear_blueprint_svg(res, theme="blueprint")

    assert "<svg" in svg
    assert "GEAR MESH SPECIFICATIONS" in svg
    assert "PINION" in svg
    assert "DRIVEN GEAR" in svg
