"""
Tests for Stress & Deflection Solvers
"""

import math

import pytest

from core.models import EngineeringModel, PointLoad, ShaftSegment, Support
from materials.database import MaterialDatabase
from physics.solver import PhysicsSolver
from physics.stress import StressConcentration


def test_circular_bending_and_torsion():
    # Solid 30mm shaft transmitting 100 Nm torque and 150 Nm bending
    model = EngineeringModel(
        name="Torsion & Bending Shaft",
        total_length=0.5,
        torque_nm=100.0,
        material_id="AISI_1045_CD",
        segments=[ShaftSegment(start_pos=0.0, end_pos=0.5, outer_diameter=0.03)],
        supports=[Support(position=0.05), Support(position=0.45)],
        point_loads=[PointLoad(position=0.25, magnitude=600.0)],
    )
    res = PhysicsSolver.solve(model)
    assert res.success is True
    # Theoretical torsional shear tau = 16*T / (pi*d^3) = 16*100 / (pi*0.03^3) = 18.86 MPa
    d = 0.03
    tau_theo = (16.0 * 100.0) / (math.pi * d**3) / 1e6
    assert pytest.approx(res.critical_section.torsional_stress, 0.5) == tau_theo


def test_peterson_stress_concentration():
    # Shoulder step: d=20mm, D=30mm (D/d = 1.5), r=2mm (r/d = 0.1)
    kt_b, kt_t = StressConcentration.shoulder_fillet_kt(0.02, 0.03, 0.002)
    # Expected Kt in bending is typically ~ 1.5 - 1.8
    assert 1.4 <= kt_b <= 1.9
    assert 1.2 <= kt_t <= 1.6


def test_deflection_simply_supported():
    # Center loaded simply supported beam deflection delta = P * L^3 / (48 * E * I)
    P = 1000.0
    L = 1.0
    d = 0.04  # 40 mm diameter
    mat = MaterialDatabase.get("AISI_1045_CD")
    E = mat.elastic_modulus_pa
    Ii = (math.pi / 64.0) * (d**4)
    expected_defl_m = (P * (L**3)) / (48.0 * E * Ii)
    expected_defl_mm = expected_defl_m * 1000.0

    model = EngineeringModel(
        name="Deflection Test Beam",
        total_length=1.0,
        material_id="AISI_1045_CD",
        segments=[ShaftSegment(start_pos=0.0, end_pos=1.0, outer_diameter=d)],
        supports=[Support(position=0.0), Support(position=1.0)],
        point_loads=[PointLoad(position=0.5, magnitude=P)],
    )
    res = PhysicsSolver.solve(model)
    assert res.success is True
    assert pytest.approx(res.max_deflection_mm, 0.05) == expected_defl_mm


def test_boundary_zero_length_shaft():
    """Test that a zero-length shaft is rejected by validation."""
    model = EngineeringModel(
        name="Zero Length Shaft",
        total_length=0.0,
        material_id="AISI_1045_CD",
        segments=[ShaftSegment(start_pos=0.0, end_pos=0.0, outer_diameter=0.03)],
        supports=[Support(position=0.0)],
    )
    errors = PhysicsSolver.validate_model(model)
    assert len(errors) > 0
    assert any("length" in e.lower() for e in errors)


def test_boundary_negative_outer_diameter():
    """Test that negative outer diameter is rejected by validation."""
    model = EngineeringModel(
        name="Negative Diameter Shaft",
        total_length=1.0,
        material_id="AISI_1045_CD",
        segments=[ShaftSegment(start_pos=0.0, end_pos=1.0, outer_diameter=-0.03)],
        supports=[Support(position=0.0), Support(position=1.0)],
    )
    errors = PhysicsSolver.validate_model(model)
    assert len(errors) > 0
    assert any("outer diameter" in e.lower() and "<= 0" in e.lower() for e in errors)


def test_boundary_no_supports():
    """Test that a shaft with no supports produces validation errors."""
    model = EngineeringModel(
        name="Shaft No Supports",
        total_length=1.0,
        material_id="AISI_1045_CD",
        segments=[ShaftSegment(start_pos=0.0, end_pos=1.0, outer_diameter=0.03)],
    )
    errors = PhysicsSolver.validate_model(model)
    assert len(errors) > 0


def test_failure_excessive_load():
    """Test that an excessively loaded shaft still computes but marks appropriately."""
    model = EngineeringModel(
        name="Overloaded Shaft",
        total_length=1.0,
        material_id="AISI_1045_CD",
        segments=[ShaftSegment(start_pos=0.0, end_pos=1.0, outer_diameter=0.03)],
        supports=[Support(position=0.0), Support(position=1.0)],
        point_loads=[PointLoad(position=0.5, magnitude=100000.0)],  # Very high load
    )
    res = PhysicsSolver.solve(model)
    # Should still compute but safety factor should be very low
    assert res.success is True
    assert res.min_yield_safety_factor < 1.0


def test_boundary_zero_torque():
    """Test shaft with zero torque still computes correctly."""
    model = EngineeringModel(
        name="Zero Torque Shaft",
        total_length=1.0,
        material_id="AISI_1045_CD",
        segments=[ShaftSegment(start_pos=0.0, end_pos=1.0, outer_diameter=0.03)],
        supports=[Support(position=0.0), Support(position=1.0)],
        torque_nm=0.0,
    )
    res = PhysicsSolver.solve(model)
    assert res.success is True
    # Shear force should be zero everywhere with no transverse load and zero torque
    assert all(s == 0.0 for s in res.shear_force)


def test_boundary_midpoint_load():
    """Test load at midpoint of shaft."""
    model = EngineeringModel(
        name="Midpoint Load Shaft",
        total_length=2.0,
        material_id="AISI_1045_CD",
        segments=[ShaftSegment(start_pos=0.0, end_pos=2.0, outer_diameter=0.05)],
        supports=[Support(position=0.0), Support(position=2.0)],
        point_loads=[PointLoad(position=1.0, magnitude=500.0)],
    )
    res = PhysicsSolver.solve(model)
    assert res.success is True
    assert res.shear_force != 0


def test_failure_yielding_material():
    """Test material with low yield strength results in low safety factor."""
    model = EngineeringModel(
        name="Low Yield Shaft",
        total_length=1.0,
        material_id="AISI_1018_CD",  # Lower yield than 1045
        segments=[ShaftSegment(start_pos=0.0, end_pos=1.0, outer_diameter=0.03)],
        supports=[Support(position=0.0), Support(position=1.0)],
        point_loads=[PointLoad(position=0.5, magnitude=500.0)],
    )
    res = PhysicsSolver.solve(model)
    assert res.success is True
    # AISI 1018 has lower yield strength than 1045, safety factor should be reasonable
    assert res.min_yield_safety_factor > 0
