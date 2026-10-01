"""Library-level end-to-end checks for the domain pipelines.

These assertions were previously exercised through the (now removed) FastAPI
surface (``web/app.py``). They are reproduced here as direct library calls so
the coverage survives the web-layer removal - the CLI and the Python library
are now the only supported interfaces.
"""


def test_shaft_pipeline_produces_result_and_scad():
    from ai.parser import NLParser
    from physics.solver import PhysicsSolver

    model, _ = NLParser.parse(
        "Design a stepped shaft 500 mm long with 30 mm diameter, power 10 kW"
    )
    result = PhysicsSolver.solve(model)

    assert result.success
    assert result.openscad_code.strip()


def test_chair_pipeline_exports_step_stl_scad_and_report():
    from core.frame_model import FrameDesignModel, STRUCTURAL_MATERIALS
    from physics.frame_physics import FramePhysicsSolver
    from physics.fea_3d import build_chair_3d_fea_model
    from cad.assembly import FrameCADEngine
    from reporting.frame_report import FrameReportGenerator

    chair = FrameDesignModel(
        name="MDIE Ergonomic Armchair",
        material=STRUCTURAL_MATERIALS["STEEL_1018"],
    )
    chair.loads.seat_vertical_load_n = 1400.0
    chair.loads.left_arm_vertical_n = 600.0
    chair.loads.right_arm_vertical_n = 600.0
    chair.geometry.leg_profile.outer_dimension_mm = 30.0
    chair.geometry.leg_splay_angle_deg = 3.5

    result = FramePhysicsSolver.solve(chair)
    fea = build_chair_3d_fea_model(chair).solve()

    assert result.all_safety_criteria_passed is True
    assert fea["min_safety_factor"] > 1.0
    assert fea["max_displacement_mm"] > 0.0

    step_text = FrameCADEngine.export_step_solid(chair)
    assert "ISO-10303-21;" in step_text
    assert "MANIFOLD_SOLID_BREP" in step_text
    assert "NEXT_ASSEMBLY_USAGE_OCCURRENCE" in step_text

    assert len(FrameCADEngine.export_stl(chair)) > 1000
    assert "chair_assembly()" in FrameCADEngine.generate_openscad(chair)

    report_html = FrameReportGenerator.generate_html_report(chair, result)
    assert "ANSI/BIFMA X5.1" in report_html


def test_space_frame_fea_pipelines():
    from physics.fea_3d import (
        build_space_truss_tower_model,
        build_cantilever_space_frame_model,
    )

    tower = build_space_truss_tower_model().solve()
    assert tower["num_nodes"] >= 8
    assert tower["num_members"] >= 12
    assert tower["max_displacement_mm"] > 0.0

    girder = build_cantilever_space_frame_model().solve()
    assert girder["num_members"] > 0
