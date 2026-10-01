"""
Test Suite: Domain Routing & Motor Mounting Bracket Mechanics
Verifies:
1. Accurate natural language domain classification (bracket, space_frame, frame, shaft, unsupported).
2. Deterministic physics solver calculations for mounting brackets (bending, bolt shear, bearing, safety factors).
3. Parametric CAD generation (OpenSCAD, Binary STL, ISO-10303 STEP).
4. End-to-end CLI prompt processing producing all local engineering deliverables.
"""

import os
from pathlib import Path
import pytest
from ai.classifier import DomainClassifier
from core.bracket_model import BracketModel, BracketGeometry, BracketLoads, BoltHolePattern
from core.frame_model import STRUCTURAL_MATERIALS
from physics.bracket_physics import BracketPhysicsSolver
from cad.bracket_cad import BracketCADEngine
from reporting.bracket_report import BracketReportGenerator
from cli import process_prompt


def test_domain_classifier_routing():
    """Verify that domain classification accurately disambiguates prompts without fragile fallbacks."""
    # 1. Bracket domain
    p1 = "motor mounting bracket with 4 bolt holes"
    d1, m1 = DomainClassifier.classify(p1)
    assert d1 == "bracket"

    p2 = "L-bracket 6mm thick for 5kg stepper motor with gusset"
    d2, m2 = DomainClassifier.classify(p2)
    assert d2 == "bracket"

    p3 = "flange plate adapter with bolt pattern"
    d3, m3 = DomainClassifier.classify(p3)
    assert d3 == "bracket"

    # 2. Structural frame domain
    d4, _ = DomainClassifier.classify("ergonomic chair with 4 splayed legs, steel")
    assert d4 == "frame"

    d5, _ = DomainClassifier.classify("heavy duty table workbench with 4 legs")
    assert d5 == "frame"

    # 3. Space frame / truss domain
    d6, _ = DomainClassifier.classify("transmission tower 8 meters high with 5 kN load")
    assert d6 == "space_frame"

    d7, _ = DomainClassifier.classify("cantilever truss box girder 4 m long")
    assert d7 == "space_frame"

    # 4. Shaft domain
    d8, _ = DomainClassifier.classify("stepped shaft 500 mm long, 25 kW at 1800 rpm")
    assert d8 == "shaft"

    # 5. Unsupported domains
    d9, m9 = DomainClassifier.classify("spur gear 20 teeth module 3 with 50 mm face width")
    assert d9 == "unsupported"
    assert "gear" in m9["keyword"]

    d10, m10 = DomainClassifier.classify("helical compression spring 10 coils 5 mm wire")
    assert d10 == "unsupported"
    assert "spring" in m10["keyword"]


def test_bracket_physics_determinism():
    """Verify deterministic calculations for overturning moment, bending, shear, and bolt safety factor."""
    model = BracketModel(
        name="Test 10kg Motor Bracket",
        geometry=BracketGeometry(
            base_length_mm=120.0,
            base_width_mm=100.0,
            thickness_mm=6.0,
            upright_height_mm=110.0,
            has_gussets=True,
            motor_bolt_pattern=BoltHolePattern(num_holes=4, hole_diameter_mm=8.5, bolt_circle_diameter_mm=75.0)
        ),
        loads=BracketLoads(
            motor_mass_kg=10.0,
            motor_torque_nm=25.0,
            cantilever_arm_mm=60.0,
            axial_thrust_n=200.0
        ),
        material=STRUCTURAL_MATERIALS["STEEL_1018"]
    )

    res = BracketPhysicsSolver.solve(model)

    # 1. Motor gravity weight check: 10 kg * 9.80665 m/s^2 = 98.07 N
    assert 97.0 < res.motor_weight_n < 99.0

    # 2. Overturning moment M = Fg * arm + F_thrust * (h*0.6) + Torque
    # Fg*arm = 98.07 * 0.060 = 5.88 N*m
    # F_thrust * h = 200 * 0.066 = 13.2 N*m
    # Torque = 25 N*m
    # Total ~ 44.08 N*m
    assert res.overturning_moment_nm > 40.0

    # 3. Root bending stress & Von Mises must be non-zero and physically plausible
    assert res.root_bending_stress_mpa > 0.0
    assert res.max_von_mises_mpa >= res.root_bending_stress_mpa

    # 4. Fastener shear & bearing
    assert res.motor_bolt_shear_stress_mpa > 0.0
    assert res.hole_bearing_stress_mpa > 0.0
    assert res.bolt_safety_factor > 1.0
    assert res.plate_yield_safety_factor > 1.0


def test_bracket_cad_generation(tmp_path):
    """Verify that OpenSCAD, STL binary, and STEP solids are properly synthesized."""
    model = BracketModel()

    # OpenSCAD
    scad = BracketCADEngine.generate_openscad(model)
    assert "module motor_bracket()" in scad
    assert "cube([base_l, base_w, thick]);" in scad
    assert "cylinder(d = pilot_d" in scad

    # Binary STL
    stl_bytes = BracketCADEngine.export_binary_stl(model)
    assert len(stl_bytes) > 84  # 80-byte header + 4-byte count + triangles

    # STEP Solid Assembly
    step_str = BracketCADEngine.export_step_solid(model)
    assert "ISO-10303-21;" in step_str
    assert "MANIFOLD_SOLID_BREP" in step_str
    assert "END-ISO-10303-21;" in step_str


def test_bracket_report_generation():
    """Verify that interactive HTML report contains SVG diagram, equations, and badges."""
    model = BracketModel()
    res = BracketPhysicsSolver.solve(model)
    html = BracketReportGenerator.generate_html_report(model, res)

    assert "<!DOCTYPE html>" in html
    assert "<svg" in html
    assert "Rigid Machine Bedplate" in html
    assert "Deterministic Mechanical Summary" in html
    assert "Physics Solver Execution Trace" in html


def test_end_to_end_bracket_cli_run(tmp_path):
    """Verify that invoking process_prompt with a bracket prompt generates all deliverables in the target folder."""
    out_dir = tmp_path / "test_bracket_out"
    prompt = "motor mounting bracket with 4 bolt holes, 10 kg, steel"
    success = process_prompt(prompt, output_dir=str(out_dir), auto_open=False)

    assert success is True
    assert (out_dir / "bracket.scad").exists()
    assert (out_dir / "bracket.stl").exists()
    assert (out_dir / "bracket.step").exists()
    assert (out_dir / "bracket_report.html").exists()

    # Verify non-empty files
    assert (out_dir / "bracket.scad").stat().st_size > 100
    assert (out_dir / "bracket.stl").stat().st_size > 100
    assert (out_dir / "bracket.step").stat().st_size > 1000
    assert (out_dir / "bracket_report.html").stat().st_size > 1000


def test_unsupported_domain_is_declined_by_cli(tmp_path):
    """A domain MDIE has no solver for must be declined, not silently synthesised."""
    out_dir = tmp_path / "pressure_vessel"
    ok = process_prompt(
        "design a pressure vessel 2 m diameter for 5 MPa internal pressure",
        output_dir=str(out_dir), auto_open=False,
    )
    assert ok is False
    assert not out_dir.exists()


def test_specialized_element_routes_through_cli(tmp_path):
    """Gears/springs/etc. have real solvers and must run through the generative path."""
    out_dir = tmp_path / "gear_pair"
    ok = process_prompt(
        "design a spur gear pair for 15 kW at 1500 rpm, steel",
        output_dir=str(out_dir), auto_open=False,
    )
    assert ok is True
    assert out_dir.exists()
    assert any(out_dir.iterdir())
