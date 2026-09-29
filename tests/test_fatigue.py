"""
Tests for Fatigue & Lifecycle Analysis
"""

import pytest
from mdie.core.models import SectionStress, EngineeringModel, ShaftSegment, Support, PointLoad
from mdie.materials.database import MaterialDatabase
from mdie.physics.fatigue import MarinFactors, FatigueSolver
from mdie.physics.solver import PhysicsSolver

def test_marin_factors():
    # Steel with Sut = 600 MPa, diameter 25 mm
    ka = MarinFactors.surface_factor(600.0, "machined")
    assert 0.7 <= ka <= 0.9

    kb = MarinFactors.size_factor(0.025)
    # kb = 1.24 * 25^(-0.107) ~ 0.87
    assert 0.8 <= kb <= 0.95

    ke = MarinFactors.reliability_factor(0.99)
    assert pytest.approx(ke, 0.001) == 0.814

def test_infinite_life_prediction():
    # Low stress condition: 50mm shaft with light 100N load -> should easily be infinite life
    model = EngineeringModel(
        name="Infinite Life Shaft",
        total_length=0.4,
        material_id="AISI_1045_CD",
        segments=[ShaftSegment(start_pos=0.0, end_pos=0.4, outer_diameter=0.05)],
        supports=[Support(position=0.05), Support(position=0.35)],
        point_loads=[PointLoad(position=0.2, magnitude=100.0)]
    )
    res = PhysicsSolver.solve(model)
    assert res.success is True
    assert res.is_infinite_life is True
    assert res.min_fatigue_safety_factor > 5.0
