"""
End-to-End Pipeline Tests:
Natural Language -> Structured Engineering Model -> Assumptions Audit -> Physics Verification -> CAD -> Report
"""

import pytest
from mdie.ai.parser import NLParser
from mdie.ai.assumptions import AssumptionManager
from mdie.ai.critic import DesignCritic
from mdie.physics.solver import PhysicsSolver
from mdie.cad.openscad import OpenSCADGenerator
from mdie.optimizer.design_search import DesignOptimizer
from mdie.reporting.generator import ReportGenerator

def test_full_pipeline_prompt():
    prompt = (
        "Design a shaft that transmits 5 kW at 1500 rpm, supports a 200 N radial load, "
        "weighs less than 5 kg, has a safety factor above 2, and survives at least 10 million cycles."
    )

    # 1. AI Parser
    model, logs = NLParser.parse(prompt)
    assert model.total_length > 0
    assert model.power_watts == 5000.0
    assert model.speed_rpm == 1500.0

    # 2. Assumption Audit
    assert len(model.assumptions) >= 4
    confirmed_params = [a.parameter for a in model.assumptions if a.status == "CONFIRMED"]
    assert "Motor Power & Speed" in confirmed_params

    # 3. Physics Verification
    result = PhysicsSolver.solve(model)
    assert result.success is True
    assert result.min_yield_safety_factor > 0
    assert result.total_mass_kg > 0

    # 4. OpenSCAD CAD Generation
    assert "module machine_shaft()" in result.openscad_code
    assert "cylinder(" in result.openscad_code

    # 5. AI Critic Review
    review = DesignCritic.review_design(model, result)
    assert review["overall_status"] in ["PASS", "FAIL"]
    assert "stress_breakdown" in review

    # 6. Safety boundary check (AI cannot override physics)
    safe, msg = DesignCritic.verify_ai_claim(True, result)
    if not result.all_constraints_passed:
        assert safe is False
        assert "SAFETY OVERRIDE: FAIL" in msg

    # 7. Optimization
    cand, opt_logs = DesignOptimizer.optimize_diameter_for_minimum_mass(model, target_sf_yield=2.0)
    assert cand is not None
    assert cand.result.all_constraints_passed is True

    # 8. Report Generator
    html_rep = ReportGenerator.generate_html_report(model, result)
    assert "Machine Design Intelligence Engine" in html_rep
    assert "Shear Force Diagram" in html_rep
    assert "Bending Moment Diagram" in html_rep
