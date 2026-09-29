"""
Tests for Stress & Deflection Solvers
"""

import math
import pytest
from mdie.core.models import EngineeringModel, Support, PointLoad, ShaftSegment
from mdie.materials.database import MaterialDatabase
from mdie.physics.solver import PhysicsSolver
from mdie.physics.stress import StressConcentration

def test_circular_bending_and_torsion():
    # Solid 30mm shaft transmitting 100 Nm torque and 150 Nm bending
    model = EngineeringModel(
        name="Torsion & Bending Shaft",
        total_length=0.5,
        torque_nm=100.0,
        material_id="AISI_1045_CD",
        segments=[ShaftSegment(start_pos=0.0, end_pos=0.5, outer_diameter=0.03)],
        supports=[Support(position=0.05), Support(position=0.45)],
        point_loads=[PointLoad(position=0.25, magnitude=600.0)]
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
    I = (math.pi / 64.0) * (d**4)
    expected_defl_m = (P * (L**3)) / (48.0 * E * I)
    expected_defl_mm = expected_defl_m * 1000.0

    model = EngineeringModel(
        name="Deflection Test Beam",
        total_length=1.0,
        material_id="AISI_1045_CD",
        segments=[ShaftSegment(start_pos=0.0, end_pos=1.0, outer_diameter=d)],
        supports=[Support(position=0.0), Support(position=1.0)],
        point_loads=[PointLoad(position=0.5, magnitude=P)]
    )
    res = PhysicsSolver.solve(model)
    assert res.success is True
    assert pytest.approx(res.max_deflection_mm, 0.05) == expected_defl_mm
