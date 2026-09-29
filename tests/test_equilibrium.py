"""
Tests for Static Equilibrium & Reactions Solver
"""

import pytest
from mdie.core.models import EngineeringModel, Support, PointLoad, DistributedLoad, ShaftSegment
from mdie.physics.equilibrium import EquilibriumSolver

def test_simply_supported_center_load():
    # Beam length 1.0m, supports at 0 and 1.0, point load 1000 N at center 0.5m
    model = EngineeringModel(
        name="Center Load Beam",
        total_length=1.0,
        segments=[ShaftSegment(start_pos=0.0, end_pos=1.0, outer_diameter=0.03)],
        supports=[
            Support(name="A", position=0.0),
            Support(name="B", position=1.0)
        ],
        point_loads=[PointLoad(position=0.5, magnitude=1000.0)]
    )
    reactions, logs = EquilibriumSolver.solve_reactions(model)
    assert len(reactions) == 2
    # By symmetry, each reaction must be 500 N
    assert pytest.approx(reactions[0].reaction_force_n, 0.01) == 500.0
    assert pytest.approx(reactions[1].reaction_force_n, 0.01) == 500.0

    dist = EquilibriumSolver.calculate_internal_distributions(model, reactions)
    # Max bending moment at center M = P*L / 4 = 1000 * 1.0 / 4 = 250 N*m
    assert pytest.approx(dist["max_bending_moment"], 0.5) == 250.0
    assert pytest.approx(dist["max_shear_force"], 0.1) == 500.0

def test_cantilever_point_load():
    # Cantilever 2m length, fixed at x=0, point load 500 N at tip x=2m
    model = EngineeringModel(
        name="Cantilever Beam",
        total_length=2.0,
        segments=[ShaftSegment(start_pos=0.0, end_pos=2.0, outer_diameter=0.04)],
        supports=[Support(name="Fixed Root", support_type="fixed", position=0.0)],
        point_loads=[PointLoad(position=2.0, magnitude=500.0)]
    )
    reactions, logs = EquilibriumSolver.solve_reactions(model)
    assert len(reactions) == 1
    # Reaction force = 500 N, Reaction moment = 500 * 2 = 1000 N*m
    assert pytest.approx(reactions[0].reaction_force_n, 0.01) == 500.0
    assert pytest.approx(reactions[0].reaction_moment_nm, 0.01) == 1000.0

    dist = EquilibriumSolver.calculate_internal_distributions(model, reactions)
    assert pytest.approx(dist["max_bending_moment"], 0.5) == 1000.0
