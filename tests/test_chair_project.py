"""
Unit Tests for Chair Structural Engineering Project (Project/chair)
Verifies:
1. Static equilibrium and floor reaction calculation under seat and dual armrest loads.
2. Euler/Johnson column buckling safety factors on the 4 legs.
3. Overturning and tipping stability margins (all feet in compression).
4. Armrest combined stresses (axial + lateral bending).
5. OpenSCAD, STL, and STEP CAD generation.
"""

import pytest
from mdie.core.frame_model import FrameDesignModel, FrameGeometry, FrameLoads, STRUCTURAL_MATERIALS
from mdie.physics.frame_physics import FramePhysicsSolver
from mdie.cad.assembly import FrameCADEngine

ChairDesignModel = FrameDesignModel
ChairGeometry = FrameGeometry
ChairLoads = FrameLoads
CHAIR_MATERIALS = STRUCTURAL_MATERIALS
ChairPhysicsSolver = FramePhysicsSolver
ChairCADEngine = FrameCADEngine

def test_chair_physics_equilibrium():
    model = ChairDesignModel(
        name="Test Chair Model",
        material=CHAIR_MATERIALS["STEEL_1018"]
    )
    result = ChairPhysicsSolver.solve(model)

    assert result.is_statically_stable is True
    assert len(result.floor_reactions) == 4

    # Equilibrium check: Sum of vertical reactions == Total downward load
    sum_rz = sum(leg.axial_reaction_n for leg in result.floor_reactions)
    assert abs(sum_rz - result.total_downward_load_n) < 0.1

    # Verify all 4 legs are in compression (no tipping uplift)
    for leg in result.floor_reactions:
        assert leg.axial_reaction_n > 0
        assert leg.buckling_passed is True
        assert leg.yield_passed is True
        assert leg.buckling_safety_factor >= 2.0

def test_chair_armrest_mechanics():
    model = ChairDesignModel(
        name="Armrest Test",
        loads=ChairLoads(
            seat_vertical_load_n=1200.0,
            left_arm_vertical_n=600.0,
            right_arm_vertical_n=600.0,
            left_arm_lateral_n=-200.0,
            right_arm_lateral_n=200.0
        )
    )
    result = ChairPhysicsSolver.solve(model)
    assert len(result.armrests) == 2
    for arm in result.armrests:
        assert arm.passed is True
        assert arm.arm_safety_factor >= 2.0
        assert arm.strut_combined_stress_mpa < model.material.yield_strength_mpa / 2.0

def test_chair_cad_generation():
    model = ChairDesignModel(name="CAD Validation Chair")
    
    # 1. OpenSCAD code
    scad = ChairCADEngine.generate_openscad(model)
    assert "module chair_assembly()" in scad
    assert "module leg(" in scad
    assert "module armrest_assembly(" in scad
    assert "module seat_pan()" in scad

    # 2. Binary STL
    stl_bytes = ChairCADEngine.export_binary_stl(model)
    assert len(stl_bytes) > 84
    assert len(stl_bytes) == 41684

    # 3. ISO-10303 STEP solid
    step_str = ChairCADEngine.export_step_solid(model)
    assert "ISO-10303-21;" in step_str
    assert "MANIFOLD_SOLID_BREP" in step_str
    assert "CLOSED_SHELL" in step_str
    assert "END-ISO-10303-21;" in step_str
