"""
Unit tests for 3D Frame & Truss FEA Solver (Direct Stiffness Method)
"""

import math

from core.frame_model import STRUCTURAL_MATERIALS as CHAIR_MATERIALS
from core.frame_model import FrameDesignModel as ChairDesignModel
from physics.fea_3d import FEA3DSolver, build_chair_3d_fea_model


def test_cantilever_beam_3d_fea():
    """Validates 3D FEA solver against classical cantilever beam tip deflection: v = P * L^3 / (3 * E * I)."""
    solver = FEA3DSolver("Cantilever Validation")
    E = 200e9  # 200 GPa
    G = 77e9  # 77 GPa
    L = 2.0  # 2 meters
    P = -1000.0  # 1000 N downward

    # Solid round bar, diameter 50 mm
    d = 0.050
    A = math.pi * (d**2) / 4.0
    Ii = math.pi * (d**4) / 64.0
    J = 2.0 * Ii

    n1 = solver.add_node(0.0, 0.0, 0.0, "Root")
    n2 = solver.add_node(L, 0.0, 0.0, "Tip")

    # Fully fixed root
    solver.set_support(n1, tx=True, ty=True, tz=True, rx=True, ry=True, rz=True)
    # 1000 N downward load on tip
    solver.add_nodal_load(n2, fz=P)

    solver.add_member("Beam", n1, n2, E, G, A, Ii, Ii, J, d, yield_strength=350e6)

    res = solver.solve()
    assert res["passed"] is True

    # Analytical tip deflection
    v_analytical = abs(P) * (L**3) / (3.0 * E * Ii)
    v_fea = abs(n2.displacements[2])
    rel_error = abs(v_fea - v_analytical) / v_analytical
    assert rel_error < 0.001  # < 0.1% error!


def test_chair_3d_frame_fea():
    """Validates 3D space frame FEA on the armchair structure under seat and armrest loads."""
    chair = ChairDesignModel(name="FEA Test Chair", material=CHAIR_MATERIALS["STEEL_1018"])
    solver = build_chair_3d_fea_model(chair)
    res = solver.solve()

    assert res["num_nodes"] >= 8
    assert res["num_members"] >= 8
    assert res["max_displacement_mm"] > 0.0
    assert res["max_displacement_mm"] < 10.0  # Under 10 mm
    assert res["max_von_mises_mpa"] > 10.0
    assert res["min_safety_factor"] >= 1.5
    assert res["max_displacement_mm"] < 10.0  # Under 10 mm (includes backrest lateral thrust)


def test_space_frame_cad_export():
    """Validates OpenSCAD, STL, and STEP CAD generation for arbitrary 3D space frames."""
    from cad.space_frame_cad import SpaceFrameCADEngine
    from physics.fea_3d import build_space_truss_tower_model

    tower = build_space_truss_tower_model(height_m=5.0, wind_load_n=4000.0)
    tower.solve()

    # 1. OpenSCAD
    scad_code = SpaceFrameCADEngine.generate_openscad(tower)
    assert "module beam(" in scad_code
    assert "color(" in scad_code

    # 2. STL Binary
    stl_bytes = SpaceFrameCADEngine.export_binary_stl(tower)
    assert len(stl_bytes) > 1000
    assert stl_bytes[:5] == b"MDIE "

    # 3. STEP Solid Assembly
    step_code = SpaceFrameCADEngine.export_step_solid(tower)
    assert "ISO-10303-21;" in step_code
    assert "MANIFOLD_SOLID_BREP" in step_code
