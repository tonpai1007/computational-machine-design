"""
Tests for Component Engines (SKF Bearings + DIN 6885 Keys) and ISO 10303 STEP CAD Exporter
"""

import pytest
from core.models import EngineeringModel, ShaftSegment, KeywaySpec, Support, PointLoad
from components.bearings import BearingCatalog, BearingLifeResult
from components.keys import KeyEngine, KeyCheckResult
from cad.step_exporter import STEPExporter
from physics.solver import PhysicsSolver

def test_skf_bearing_selection():
    # 30 mm shaft, 1200 N load, 1800 rpm
    res = BearingCatalog.select_bearing(shaft_diameter_m=0.030, radial_load_n=1200.0, speed_rpm=1800.0)
    assert isinstance(res, BearingLifeResult)
    assert res.bearing.bore_diameter_mm == 30.0
    assert "6206" in res.bearing.designation or "6006" in res.bearing.designation
    assert res.l10h_hours > 10000.0
    assert res.status in ["PASS", "ADEQUATE", "EXCELLENT"]

def test_din_6885_keyway_verification():
    # 35 mm shaft, 250 Nm torque
    res = KeyEngine.verify_key(shaft_diameter_m=0.035, torque_nm=250.0, key_length_m=0.045)
    assert isinstance(res, KeyCheckResult)
    assert res.key_width_mm == 10.0
    assert res.key_height_mm == 8.0
    assert res.shear_safety_factor > 1.5
    assert res.crushing_safety_factor > 1.5
    assert res.passed is True

def test_step_solid_exporter_iso_10303():
    model = EngineeringModel(
        name="STEP Test Shaft",
        total_length=0.45,
        power_watts=12000.0,
        speed_rpm=1440.0,
        segments=[
            ShaftSegment(start_pos=0.0, end_pos=0.10, outer_diameter=0.030, feature_type="bearing_seat"),
            ShaftSegment(
                start_pos=0.10, end_pos=0.35, outer_diameter=0.045, feature_type="gear_seat",
                keyway=KeywaySpec(position=0.15, length=0.05, width=0.012, depth=0.005)
            ),
            ShaftSegment(start_pos=0.35, end_pos=0.45, outer_diameter=0.030, feature_type="bearing_seat")
        ],
        supports=[Support(position=0.05), Support(position=0.40)],
        point_loads=[PointLoad(position=0.22, magnitude=3000.0)]
    )

    step_content = STEPExporter.export_step(model, n_slices=24)

    # Validate ISO 10303-21 compliance syntax
    assert "ISO-10303-21;" in step_content
    assert "HEADER;" in step_content
    assert "FILE_DESCRIPTION(('MDIE Parametric 3D Solid Model'" in step_content
    assert "DATA;" in step_content
    assert "CLOSED_SHELL(" in step_content
    assert "MANIFOLD_SOLID_BREP(" in step_content
    assert "ADVANCED_FACE(" in step_content
    assert "CARTESIAN_POINT(" in step_content
    assert "END-ISO-10303-21;" in step_content

def test_solver_integration_with_components():
    model = EngineeringModel(
        name="Integrated Shaft Test",
        total_length=0.5,
        power_watts=10000.0,
        speed_rpm=1500.0,
        segments=[
            ShaftSegment(start_pos=0.0, end_pos=0.1, outer_diameter=0.030),
            ShaftSegment(
                start_pos=0.1, end_pos=0.4, outer_diameter=0.040,
                keyway=KeywaySpec(position=0.2, length=0.05, width=0.012, depth=0.005)
            ),
            ShaftSegment(start_pos=0.4, end_pos=0.5, outer_diameter=0.030)
        ],
        supports=[Support(position=0.05), Support(position=0.45)],
        point_loads=[PointLoad(position=0.25, magnitude=2500.0)]
    )
    result = PhysicsSolver.solve(model)
    assert result.success is True
    assert len(result.bearings_selected) == 2
    assert result.bearings_selected[0]["bearing"]["bore_diameter_mm"] == 30.0
    assert result.keyway_analysis is not None
    assert "DIN 6885-1" in result.keyway_analysis["standard"]
