"""
Test Suite: AGMA 2001-D04 / ISO 6336 Gear Physics & CAD
"""

import pytest
from mdie.components.gears import GearPairSpecification
from mdie.physics.gears import GearSolver
from mdie.cad.gears_cad import GearCADGenerator


def test_spur_gear_physics_solver():
    spec = GearPairSpecification(
        name="Test_Spur_Pair",
        gear_type="spur",
        power_kw=10.0,
        pinion_speed_rpm=1500.0,
        pinion_teeth=20,
        gear_teeth=60,
        normal_module_mm=3.0,
        helix_angle_deg=0.0,
        material_id="AISI_4140_QT"
    )

    res = GearSolver.solve(spec)

    assert res.geometry.pitch_diameter_pinion_mm == 60.0
    assert res.geometry.pitch_diameter_gear_mm == 180.0
    assert res.geometry.center_distance_mm == 120.0
    assert res.geometry.gear_ratio == 3.0
    assert res.stress.pitch_line_velocity_m_s > 0
    assert res.stress.tangential_force_wt_n > 0
    assert res.stress.bending_safety_factor_pinion > 0
    assert res.stress.contact_safety_factor > 0


def test_helical_gear_physics_and_cad():
    spec = GearPairSpecification(
        name="Test_Helical_Pair",
        gear_type="helical",
        power_kw=25.0,
        pinion_speed_rpm=1800.0,
        pinion_teeth=24,
        gear_teeth=72,
        normal_module_mm=4.0,
        helix_angle_deg=20.0,
        material_id="AISI_4140_QT"
    )

    res = GearSolver.solve(spec)
    assert res.geometry.transverse_module_mm > spec.normal_module_mm
    assert res.stress.axial_thrust_wa_n > 0  # Helical thrust

    scad = GearCADGenerator.generate_scad(res)
    assert "involute_gear" in scad
    assert f"center_distance = {res.geometry.center_distance_mm}" not in scad  # in code
    assert "$fn" in scad
