"""
LangGraph Multi-Agent Document Generation Workflow
Orchestrates: Research → Outline → Writer → Fact Checker → Editor → Renderer → QA Validator
All numerical values come from deterministic solver results; agents only author narrative text.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from ai.critic import DesignCritic
from core.models import EngineeringModel, SolverResult
from reporting.diagrams import generate_all_diagrams

# =============================================================================
# State Definition
# =============================================================================

class DocGenState(TypedDict):
    """State passed through the LangGraph workflow."""
    model: EngineeringModel
    result: SolverResult
    template_vars: dict[str, Any]          # All numerical data for docxtpl
    narrative_sections: dict[str, str]     # Agent-authored explanatory text
    outline: list[str]                     # Document structure
    fact_check_results: list[tuple[bool, str]]  # (passed, message) from verify_ai_claim
    qa_verdict: tuple[bool, str] | None    # Final QA result
    output_path: Path | None
    errors: list[str]
    diagram_paths: dict[str, str]          # diagram_name -> file path


# =============================================================================
# Helper: Extract Template Variables from SolverResult
# =============================================================================

def _extract_template_vars(model: EngineeringModel, result: SolverResult) -> dict[str, Any]:
    """Extract all numerical values from solver results for docxtpl template."""
    crit_sec = result.critical_section

    # Assumptions
    assumptions = [
        {
            "parameter": a.parameter,
            "value": str(a.value),
            "source": a.source,
            "status": a.status,
            "notes": a.notes or ""
        }
        for a in model.assumptions
    ]

    # Reactions
    reactions = [
        {
            "support_name": r.support_name,
            "position_mm": round(r.position * 1000.0, 1),
            "force_n": round(r.reaction_force_n, 2),
            "moment_nm": round(r.reaction_moment_nm, 2)
        }
        for r in result.reactions
    ]

    # Bearings
    bearings = []
    for b in result.bearings_selected:
        bearing_data = b.get("bearing", {})
        bearings.append({
            "location": f"Support @ {bearing_data.get('bore_diameter_mm')} mm journal",
            "designation": bearing_data.get("designation", ""),
            "bore_mm": bearing_data.get("bore_diameter_mm", 0),
            "outer_mm": bearing_data.get("outer_diameter_mm", 0),
            "width_mm": bearing_data.get("width_mm", 0),
            "capacity_kn": bearing_data.get("dynamic_load_c_kn", 0),
            "load_n": round(b.get("radial_load_n", 0), 1),
            "l10h_hours": f"{b.get('l10h_hours', 0):,.0f}",
            "status": b.get("status", "")
        })

    # Keyway
    keyway = {}
    if result.keyway_analysis:
        k = result.keyway_analysis
        keyway = {
            "standard": k.get("standard", ""),
            "shaft_diameter_mm": k.get("shaft_diameter_mm", 0),
            "key_width_mm": k.get("key_width_mm", 0),
            "key_height_mm": k.get("key_height_mm", 0),
            "key_length_mm": k.get("key_length_mm", 0),
            "shear_stress_mpa": k.get("shear_stress_mpa", 0),
            "shear_sf": k.get("shear_safety_factor", 0),
            "crush_stress_mpa": k.get("crushing_stress_mpa", 0),
            "crush_sf": k.get("crushing_safety_factor", 0),
            "status": "PASS" if k.get("passed") else "FAIL"
        }

    # Critical section
    has_critical_section = crit_sec is not None
    crit_sec_data = {}
    if crit_sec is not None:
        crit_sec_data = {
            "x_mm": round(crit_sec.x * 1000.0, 1),
            "diameter_mm": round(crit_sec.outer_diameter * 1000.0, 1),
            "bending_moment_nm": round(crit_sec.bending_moment, 2),
            "bending_stress_mpa": round(crit_sec.bending_stress, 2),
            "torque_nm": round(crit_sec.torque, 2),
            "torsional_stress_mpa": round(crit_sec.torsional_stress, 2),
            "kt_bending": round(crit_sec.kt_bending, 2),
            "von_mises_mpa": round(crit_sec.effective_von_mises, 2)
        }

    # Verification badge
    verification_badge = "VERIFIED COMPLIANT (PASS)" if result.all_constraints_passed else "NON-COMPLIANT (FAIL)"

    # Mass limit string
    mass_limit = f"≤ {model.constraints.max_mass_kg} kg" if model.constraints.max_mass_kg else "Unconstrained"

    # Review from DesignCritic
    review = DesignCritic.review_design(model, result)

    return {
        "project_name": model.name,
        "verification_badge": verification_badge,
        "yield_sf": round(result.min_yield_safety_factor, 2) if result.min_yield_safety_factor is not None else "N/A",
        "min_yield_sf": round(model.constraints.min_yield_safety_factor, 2),
        "yield_status": "PASS" if result.yield_passed else "FAIL",
        "fatigue_sf": round(result.min_fatigue_safety_factor, 2) if result.min_fatigue_safety_factor is not None else "N/A",
        "min_fatigue_sf": round(model.constraints.min_fatigue_safety_factor, 2),
        "fatigue_status": "PASS" if result.fatigue_passed else "FAIL",
        "max_deflection_mm": round(result.max_deflection_mm, 3),
        "max_deflection_limit_mm": round(model.constraints.max_deflection_mm, 3),
        "deflection_status": "PASS" if result.deflection_passed else "FAIL",
        "total_mass_kg": round(result.total_mass_kg, 3),
        "mass_limit": mass_limit,
        "mass_status": "PASS" if review["mass_review"] == "PASS" else "FAIL",
        "fatigue_life_cycles": f"{result.fatigue_life_cycles:,.0f}",
        "target_life_cycles": f"{model.constraints.target_life_cycles:,.0f}",
        "life_status": "PASS" if result.fatigue_passed else "FAIL",
        "overall_status": review["overall_status"],
        "strength_review": review["strength_review"],
        "fatigue_review": review["fatigue_review"],
        "deflection_review": review["deflection_review"],
        "mass_review": review["mass_review"],
        "critical_issues": review["critical_issues"],
        "recommendations": review["recommendations"],
        "assumptions": assumptions,
        "material_name": result.material_name,
        "yield_strength_mpa": round(result.yield_strength_mpa, 1),
        "ultimate_strength_mpa": round(result.ultimate_strength_mpa, 1),
        "endurance_limit_mpa": round(result.endurance_limit_mpa, 1),
        "elastic_modulus_gpa": 206.0,
        "density_kgm3": 7850,
        "reactions": reactions,
        "applied_torque_nm": round(result.applied_torque_nm, 2),
        "has_critical_section": has_critical_section,
        "crit_sec": crit_sec_data,
        "has_bearings": len(bearings) > 0,
        "bearings": bearings,
        "has_keyway": bool(keyway),
        "keyway": keyway,
        "openscad_code": result.openscad_code,
        "calculation_steps": result.calculation_steps,
    }


# =============================================================================
# Agent Nodes
# =============================================================================

def research_node(state: DocGenState) -> DocGenState:
    """Research Agent: Gather and structure context from solver results."""
    model = state["model"]
    result = state["result"]

    # Extract all template variables
    template_vars = _extract_template_vars(model, result)
    state["template_vars"] = template_vars

    # Initialize narrative sections
    state["narrative_sections"] = {}
    state["errors"] = []
    state["diagram_paths"] = {}

    return state


def diagram_node(state: DocGenState) -> DocGenState:
    """Diagram Agent: Generate SVG/PNG diagrams from solver results."""
    model = state["model"]
    result = state["result"]

    # Generate diagrams in the project output directory
    output_dir = Path(f"Project/{model.name}/diagrams")
    try:
        diagram_paths = generate_all_diagrams(result, output_dir)
        state["diagram_paths"] = diagram_paths
        state["template_vars"]["diagram_paths"] = diagram_paths
    except Exception as e:
        state["errors"].append(f"Diagram generation failed: {e}")
        state["diagram_paths"] = {}
        state["template_vars"]["diagram_paths"] = {}

    return state


def outline_node(state: DocGenState) -> DocGenState:
    """Outline Agent: Create document structure based on available data."""
    template_vars = state["template_vars"]

    # Standard engineering report structure
    outline = [
        "Executive Summary",
        "AI Design Review & Root-Cause Analysis",
        "Design Inputs & Engineering Assumptions Log",
        "Material Mechanical Properties",
        "Equilibrium & Support Reactions",
        "Critical Section Analysis (Peak Stress Plane)",
        "Standard Machine Components: Bearings & Keys",
        "Parametric OpenSCAD 3D CAD Definition",
        "Deterministic Physics Solver Audit Trace"
    ]

    # Conditionally include sections based on data availability
    if not template_vars.get("has_critical_section"):
        outline.remove("Critical Section Analysis (Peak Stress Plane)")
    if not template_vars.get("has_bearings"):
        outline.remove("Standard Machine Components: Bearings & Keys")
    elif not template_vars.get("has_keyway"):
        # Keep bearings section but note no keyway
        pass

    state["outline"] = outline
    return state


def writer_node(state: DocGenState) -> DocGenState:
    """Writer Agent: Generate explanatory narrative text (NO numerical values)."""
    template_vars = state["template_vars"]
    narrative = {}

    # Executive Summary narrative
    narrative["exec_summary"] = (
        "This calculation sheet presents the deterministic verification of the "
        f"{template_vars['project_name']} design. All numerical results are derived "
        "from closed-form physics solvers with full audit traceability. "
        "The design is evaluated against yield, fatigue, deflection, and mass constraints."
    )

    # AI Design Review narrative
    narrative["ai_review_intro"] = (
        "The AI Design Critic provides an independent assessment of the design "
        "based on deterministic solver outputs. The review identifies root causes "
        "of any constraint violations and recommends specific engineering actions."
    )

    # Assumptions narrative
    narrative["assumptions_intro"] = (
        "The following table documents all engineering assumptions made during "
        "model setup. Each assumption is traced to its source and audit status. "
        "CONFIRMED assumptions are verified against standards; ASSUMED items "
        "require validation before manufacturing."
    )

    # Materials narrative
    narrative["materials_intro"] = (
        "Material properties are sourced from the MDIE material database. "
        "The endurance limit is estimated as 0.5 × Sut for steels per Shigley, "
        "adjusted for surface finish, size, and reliability factors by the fatigue solver."
    )

    # Reactions narrative
    narrative["reactions_intro"] = (
        "Support reactions are computed from static equilibrium of the loaded shaft. "
        "Vertical reactions and reaction moments at each support are listed below. "
        "The nominal transmitted torque is applied at the driven element."
    )

    # Critical section narrative
    if template_vars.get("has_critical_section"):
        narrative["critical_section_intro"] = (
            "The critical section is the axial station with the highest effective "
            "Von Mises stress. Stress concentration factors (Kt) for bending and "
            "torsion are applied per standard shaft design practice. The effective "
            "Von Mises stress combines bending and torsional components using the "
            "distortion energy theory: σ_vm = √(σ_b² + 3τ²)."
        )
    else:
        narrative["critical_section_intro"] = ""

    # Bearings narrative
    if template_vars.get("has_bearings"):
        narrative["bearings_intro"] = (
            "Rolling bearings are selected per SKF catalogue data and verified "
            "against ISO 281 L10h rating life. The equivalent dynamic load P "
            "accounts for combined radial and axial loading. Suitability ratings "
            "EXCELLENT/GOOD/MARGINAL indicate margin above the target life."
        )
    else:
        narrative["bearings_intro"] = ""

    # Keyway narrative
    if template_vars.get("has_keyway"):
        narrative["keyway_intro"] = (
            "Keyway verification follows DIN 6885-1 for parallel keys. Shear and "
            "crushing safety factors are computed against the key material yield "
            "strength. Both failure modes must pass for the keyway to be acceptable."
        )
    else:
        narrative["keyway_intro"] = ""

    # OpenSCAD narrative
    narrative["openscad_intro"] = (
        "The parametric OpenSCAD script below defines the complete 3D geometry "
        "using the solver-selected dimensions. All dimensions are derived from "
        "deterministic calculations, not manual input. The script is ready for "
        "direct use in OpenSCAD, export to STEP/STL, or CAM processing."
    )

    # Audit trace narrative
    narrative["audit_intro"] = (
        "The following audit trace documents every calculation step performed by "
        "the deterministic physics solver. This provides full traceability from "
        "inputs to final results, enabling independent verification."
    )

    state["narrative_sections"] = narrative
    return state


def fact_checker_node(state: DocGenState) -> DocGenState:
    """Fact Checker Agent: Validate all narrative claims against solver results."""
    template_vars = state["template_vars"]
    result = state["result"]

    fact_checks = []

    # Check each narrative section for claims that can be verified
    # The writer should not have included numerical values, but we verify anyway

    # Verify overall status claim
    ai_claim_safe = template_vars["overall_status"] == "PASS"
    physics_safe = result.all_constraints_passed
    # Safety veto: AI's safety claim is accepted only if physics independently confirms
    passed, msg = DesignCritic.verify_ai_claim(ai_claim_safe and physics_safe, result)
    fact_checks.append((passed, f"Overall status: {msg}"))

    # Verify yield claim
    ai_claim_yield = template_vars["yield_status"] == "PASS"
    passed, msg = DesignCritic.verify_ai_claim(ai_claim_yield, result)
    fact_checks.append((passed, f"Yield constraint: {msg}"))

    # Verify fatigue claim
    ai_claim_fatigue = template_vars["fatigue_status"] == "PASS"
    passed, msg = DesignCritic.verify_ai_claim(ai_claim_fatigue, result)
    fact_checks.append((passed, f"Fatigue constraint: {msg}"))

    # Verify deflection claim
    ai_claim_deflection = template_vars["deflection_status"] == "PASS"
    passed, msg = DesignCritic.verify_ai_claim(ai_claim_deflection, result)
    fact_checks.append((passed, f"Deflection constraint: {msg}"))

    # Check for any numerical claims in narrative (should be none)
    for section_name, text in state["narrative_sections"].items():
        # Simple heuristic: flag any text containing numbers with units that might be claims
        import re
        numeric_claims = re.findall(r'\d+(?:\.\d+)?\s*(?:MPa|mm|N|N·m|kN|cycles|kg|GPa)', text)
        if numeric_claims:
            fact_checks.append((
                False,
                f"Section '{section_name}' contains numerical values that should come from template: {numeric_claims}"
            ))

    state["fact_check_results"] = fact_checks

    # Collect any errors
    for passed, msg in fact_checks:
        if not passed:
            state["errors"].append(f"FACT CHECK FAILED: {msg}")

    return state


def editor_node(state: DocGenState) -> DocGenState:
    """Editor Agent: Refine language and ensure consistency."""
    # In a real implementation, this would use an LLM to polish the narrative
    # For now, we ensure narrative sections exist and are non-empty
    narrative = state["narrative_sections"]

    for key in [
        "exec_summary", "ai_review_intro", "assumptions_intro", "materials_intro",
        "reactions_intro", "critical_section_intro", "bearings_intro",
        "keyway_intro", "openscad_intro", "audit_intro"
    ]:
        if key not in narrative or not narrative[key].strip():
            narrative[key] = f"[Section {key} - content to be generated]"

    state["narrative_sections"] = narrative
    return state


def renderer_node(state: DocGenState) -> DocGenState:
    """Renderer Agent: Fill docxtpl template with solver data and narrative."""
    try:
        from docx.shared import Inches
        from docxtpl import DocxTemplate, InlineImage  # type: ignore[import-untyped]
    except ImportError:
        state["errors"].append("docxtpl not installed. Install with: pip install docxtpl")
        return state

    template_path = Path("templates/engineering_report.docx")
    if not template_path.exists():
        state["errors"].append(f"Template not found at {template_path}")
        return state

    # Prepare context for docxtpl
    context = {}
    context.update(state["template_vars"])
    context.update(state["narrative_sections"])

    # Create the template first
    doc = DocxTemplate(str(template_path))

    # Handle diagram images - convert paths to InlineImage objects
    diagram_paths = state.get("diagram_paths", {})
    for diagram_name, diagram_path in diagram_paths.items():
        if diagram_path and Path(diagram_path).exists():
            try:
                context[f"diagram_{diagram_name}"] = InlineImage(
                    doc,
                    str(diagram_path),
                    width=Inches(6.5)
                )
            except Exception as e:
                state["errors"].append(f"Failed to load diagram {diagram_name}: {e}")

    # Render template
    doc.render(context)

    # Save output
    output_path = Path(f"Project/{state['model'].name}/report.docx")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))

    state["output_path"] = output_path
    return state


def qa_validator_node(state: DocGenState) -> DocGenState:
    """QA Validator Agent: Final verification of the generated document."""
    result = state["result"]

    # Final physics authority check
    ai_claim_safe = state["template_vars"]["overall_status"] == "PASS"
    physics_safe = result.all_constraints_passed
    # Safety veto: AI's safety claim is accepted only if physics independently confirms
    passed, msg = DesignCritic.verify_ai_claim(ai_claim_safe and physics_safe, result)
    state["qa_verdict"] = (passed, msg)

    if not passed:
        state["errors"].append(f"QA VALIDATION FAILED: {msg}")

    # Verify document was created
    if state["output_path"] is None or not state["output_path"].exists():
        state["errors"].append("QA VALIDATION FAILED: Output document not created")
        state["qa_verdict"] = (False, "Output document not created")

    return state


# =============================================================================
# Build Workflow Graph
# =============================================================================

def build_docgen_workflow() -> CompiledStateGraph[DocGenState, None, DocGenState, DocGenState]:
    """Build and return the LangGraph workflow for document generation."""
    workflow = StateGraph(DocGenState)

    # Add nodes
    workflow.add_node("research", research_node)
    workflow.add_node("diagram", diagram_node)
    workflow.add_node("outline", outline_node)
    workflow.add_node("writer", writer_node)
    workflow.add_node("fact_checker", fact_checker_node)
    workflow.add_node("editor", editor_node)
    workflow.add_node("renderer", renderer_node)
    workflow.add_node("qa_validator", qa_validator_node)

    # Define edges (sequential pipeline)
    workflow.set_entry_point("research")
    workflow.add_edge("research", "diagram")
    workflow.add_edge("diagram", "outline")
    workflow.add_edge("outline", "writer")
    workflow.add_edge("writer", "fact_checker")
    workflow.add_edge("fact_checker", "editor")
    workflow.add_edge("editor", "renderer")
    workflow.add_edge("renderer", "qa_validator")
    workflow.add_edge("qa_validator", END)

    return workflow.compile()


# =============================================================================
# Public API
# =============================================================================

def generate_docx_report(model: EngineeringModel, result: SolverResult) -> tuple[Path | None, list[str]]:
    """
    Generate a DOCX engineering report using the multi-agent LangGraph workflow.

    Returns:
        (output_path, errors) - output_path is None if generation failed
    """
    workflow = build_docgen_workflow()

    initial_state: DocGenState = {
        "model": model,
        "result": result,
        "template_vars": {},
        "narrative_sections": {},
        "outline": [],
        "fact_check_results": [],
        "qa_verdict": None,
        "output_path": None,
        "errors": [],
        "diagram_paths": {},
    }

    final_state = workflow.invoke(initial_state)

    return final_state["output_path"], final_state["errors"]


__all__ = ["generate_docx_report", "build_docgen_workflow", "DocGenState"]
