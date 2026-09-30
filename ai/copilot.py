"""
MDIE Engineering Copilot Engine
Provides interactive engineering dialogue, iterative redesign, what-if sensitivity analysis,
and verification loops where the physics solver is the sole ground truth.
"""

import copy
import math
import os
from typing import Dict, Any, List, Optional, Tuple
from core.models import EngineeringModel, SolverResult
from physics.solver import PhysicsSolver
from ai.critic import DesignCritic
from materials.database import MaterialDatabase
from ai.llm_router import LLMRouter

class EngineeringCopilot:
    @staticmethod
    def answer_query(
        query: str,
        model: EngineeringModel,
        result: SolverResult
    ) -> Dict[str, Any]:
        """
        Answer engineering questions regarding the current model and solver result.
        Strictly grounds all answers in the deterministic physics solver data.
        """
        q = query.lower()
        critic_review = DesignCritic.review_design(model, result)
        response_text = ""
        modified_model: Optional[EngineeringModel] = None
        new_result: Optional[SolverResult] = None

        # 1. "Why is it failing?" or "Why did it pass?"
        if "why" in q and ("fail" in q or "pass" in q or "stress" in q):
            br = critic_review["stress_breakdown"]
            response_text = (
                f"### Engineering Stress Breakdown (at critical section x = {br.get('critical_station_x_mm')} mm):\n\n"
                f"* **Von Mises Equivalent Stress:** {br.get('effective_von_mises_mpa')} MPa\n"
                f"* **Material Yield Strength:** {br.get('material_yield_mpa')} MPa\n"
                f"* **Yield Safety Factor:** {result.min_yield_safety_factor:.2f} (Required: {model.constraints.min_yield_safety_factor:.2f})\n"
                f"* **Fatigue Safety Factor (Goodman):** {result.min_fatigue_safety_factor:.2f} (Required: {model.constraints.min_fatigue_safety_factor:.2f})\n"
                f"* **Max Deflection:** {result.max_deflection_mm:.3f} mm (Allowable: {model.constraints.max_deflection_mm:.3f} mm)\n\n"
                f"**Primary Stress Contributors:**\n"
                f"1. Bending Stress: {br.get('bending_stress_mpa')} MPa ({br.get('bending_percentage')} % of total)\n"
                f"2. Torsional Shear Stress: {br.get('torsional_shear_mpa')} MPa ({br.get('torsion_percentage')} % of total)\n"
                f"3. Geometric Stress Concentration (Kt): Bending = {br.get('kt_bending')}, Torsion = {br.get('kt_torsion')}\n\n"
                f"**Conclusion:** {'Design satisfies all constraints.' if result.all_constraints_passed else 'Design is NON-COMPLIANT.'}\n"
            )
            if critic_review["recommendations"]:
                response_text += "\n**Recommended Physics-Guided Actions:**\n"
                for r in critic_review["recommendations"]:
                    response_text += f"* {r}\n"

        # 2. "Make it X% lighter" (Iterative design loop)
        elif "lighter" in q or "reduce mass" in q or "reduce weight" in q:
            # Extract percentage or default to 20%
            import re
            pct_match = re.search(r'(\d+)\s*%', q)
            pct = float(pct_match.group(1)) if pct_match else 20.0
            target_mass = result.total_mass_kg * (1.0 - pct / 100.0)

            # Test hollow shaft or reduced diameter through verification loop
            mod_model = copy.deepcopy(model)
            # Try hollow bore: solve for inner diameter that achieves target mass
            # m = rho * L * pi/4 * (do^2 - di^2)
            d_out = mod_model.segments[0].outer_diameter
            mat = MaterialDatabase.get(mod_model.material_id)
            L = mod_model.total_length
            
            # Target area = target_mass / (rho * L)
            target_area = target_mass / (mat.density_kg_m3 * L)
            # target_area = pi/4 * (do^2 - di^2) => di = sqrt(do^2 - 4*target_area/pi)
            term = d_out**2 - (4.0 * target_area / 3.14159265)
            if term > 0:
                d_in = math.sqrt(term)
                for seg in mod_model.segments:
                    seg.inner_diameter = d_in
                
                # Re-verify through Physics Solver
                test_res = PhysicsSolver.solve(mod_model)
                modified_model = mod_model
                new_result = test_res

                response_text = (
                    f"### Mass Reduction Simulation (-{pct:.0f}% Mass Target):\n\n"
                    f"* **Original Mass:** {result.total_mass_kg:.3f} kg\n"
                    f"* **New Target Mass:** {test_res.total_mass_kg:.3f} kg\n"
                    f"* **Bore Added:** Inner diameter di = {d_in * 1000.0:.1f} mm (Outer diameter = {d_out * 1000.0:.1f} mm)\n"
                    f"* **Safety Factor (Yield):** {result.min_yield_safety_factor:.2f} -> {test_res.min_yield_safety_factor:.2f}\n"
                    f"* **Safety Factor (Fatigue):** {result.min_fatigue_safety_factor:.2f} -> {test_res.min_fatigue_safety_factor:.2f}\n"
                    f"* **Max Deflection:** {result.max_deflection_mm:.3f} mm -> {test_res.max_deflection_mm:.3f} mm\n"
                    f"* **Status:** {'PASS - All constraints satisfied.' if test_res.all_constraints_passed else 'FAIL - Exceeds allowable limits. Consider solid shaft with higher-strength alloy.'}\n"
                )
            else:
                response_text = (
                    f"Cannot achieve -{pct:.0f}% mass reduction solely through bore modification without violating outer wall limits. "
                    "Recommend switching to high-strength Aluminum 7075-T6 (density 2810 kg/m³ vs steel 7850 kg/m³)."
                )

        # 3. Material switch query (e.g. "What if I switch to 7075 aluminum?")
        elif "switch" in q or "material" in q or "aluminum" in q or "titanium" in q:
            # Detect target material
            target_mat_id = "AL_7075_T6" if "7075" in q or "aluminum" in q else ("TI_6AL_4V" if "titanium" in q else "AISI_4140_QT")
            mod_model = copy.deepcopy(model)
            mod_model.material_id = target_mat_id
            test_res = PhysicsSolver.solve(mod_model)
            modified_model = mod_model
            new_result = test_res

            response_text = (
                f"### Material Tradeoff Analysis: {test_res.material_name}\n\n"
                f"* **Mass:** {result.total_mass_kg:.3f} kg -> {test_res.total_mass_kg:.3f} kg ({((test_res.total_mass_kg - result.total_mass_kg)/result.total_mass_kg)*100:+.1f}%)\n"
                f"* **Yield Safety Factor:** {result.min_yield_safety_factor:.2f} -> {test_res.min_yield_safety_factor:.2f}\n"
                f"* **Fatigue Safety Factor:** {result.min_fatigue_safety_factor:.2f} -> {test_res.min_fatigue_safety_factor:.2f}\n"
                f"* **Max Deflection:** {result.max_deflection_mm:.3f} mm -> {test_res.max_deflection_mm:.3f} mm\n"
                f"* **Status:** {'FEASIBLE' if test_res.all_constraints_passed else 'NON-COMPLIANT'}\n"
            )

        # 4. General Engineering dialogue via LLMRouter (Groq, OpenRouter, Gemini, Ollama)
        else:
            configured = LLMRouter.get_configured_providers()
            if configured:
                sys_prompt = (
                    "You are the AI Engineering Copilot for the Machine Design Intelligence Engine (MDIE).\n"
                    "Fundamental Rule: AI is NOT the physics engine. Ground all responses in the provided verified solver results.\n"
                    f"Current Model: {model.name}\n"
                    f"Material: {result.material_name}, Sy={result.yield_strength_mpa} MPa, Sut={result.ultimate_strength_mpa} MPa, Se={result.endurance_limit_mpa:.1f} MPa\n"
                    f"Max Von Mises: {result.max_von_mises_mpa:.2f} MPa at x={result.max_von_mises_x:.3f} m\n"
                    f"Yield SF: {result.min_yield_safety_factor:.2f}, Fatigue SF: {result.min_fatigue_safety_factor:.2f}, Deflection: {result.max_deflection_mm:.3f} mm\n"
                    f"Total Mass: {result.total_mass_kg:.3f} kg, Applied Torque: {result.applied_torque_nm:.1f} N*m\n"
                    f"All Constraints Passed: {result.all_constraints_passed}\n"
                )
                try:
                    raw_res, provider, logs = LLMRouter.call_chat_completion(
                        system_prompt=sys_prompt,
                        user_prompt=query,
                        response_format_json=False,
                        max_tokens=1000,
                        temperature=0.2
                    )
                    if raw_res:
                        response_text = raw_res
                    else:
                        raise RuntimeError("No response from LLM providers.")
                except Exception:
                    response_text = (
                        f"Verified Engineering Summary for '{model.name}':\n"
                        f"- Status: {'PASS' if result.all_constraints_passed else 'FAIL'}\n"
                        f"- Max Stress: {result.max_von_mises_mpa:.1f} MPa (Yield SF: {result.min_yield_safety_factor:.2f})\n"
                        f"- Fatigue Life: {result.fatigue_life_cycles:,.0f} cycles (Fatigue SF: {result.min_fatigue_safety_factor:.2f})\n"
                        f"- Deflection: {result.max_deflection_mm:.3f} mm\n"
                        f"- Mass: {result.total_mass_kg:.3f} kg"
                    )
            else:
                response_text = (
                    f"### Engineering Status Summary for '{model.name}':\n\n"
                    f"* **Status:** {'PASS' if result.all_constraints_passed else 'FAIL'}\n"
                    f"* **Max Stress:** {result.max_von_mises_mpa:.1f} MPa (SF_y: {result.min_yield_safety_factor:.2f})\n"
                    f"* **Fatigue SF:** {result.min_fatigue_safety_factor:.2f} ({'Infinite Life' if result.is_infinite_life else f'{result.fatigue_life_cycles:,.0f} cycles'})\n"
                    f"* **Deflection:** {result.max_deflection_mm:.3f} mm (Allowable: {model.constraints.max_deflection_mm:.3f} mm)\n"
                    f"* **Mass:** {result.total_mass_kg:.3f} kg\n"
                )

        return {
            "response": response_text,
            "modified_model": modified_model,
            "new_result": new_result,
            "design_review": critic_review,
        }
