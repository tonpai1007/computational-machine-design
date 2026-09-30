"""
MDIE AI Design Critic & Explainable Engineering Copilot
Generates formal design reviews, diagnoses structural failures using exact deterministic physics results,
recommends verified redesigns, and enforces safety boundaries between AI claims and physics ground truth.
"""

from typing import Dict, Any, List, Optional, Tuple
from core.models import EngineeringModel, SolverResult, SectionStress
from materials.database import MaterialDatabase

class DesignCritic:
    @staticmethod
    def review_design(model: EngineeringModel, result: SolverResult) -> Dict[str, Any]:
        """
        Produce a structured design review with PASS / WARNING / FAIL ratings,
        root-cause decomposition, and concrete engineering recommendations.
        """
        c = model.constraints
        crit_sec = result.critical_section

        # 1. Component Reviews
        strength_status = "PASS" if result.yield_passed else "FAIL"
        fatigue_status = "PASS" if result.fatigue_passed else ("WARNING" if result.min_fatigue_safety_factor >= 1.0 else "FAIL")
        deflection_status = "PASS" if result.deflection_passed else "FAIL"
        
        mass_status = "PASS"
        if c.max_mass_kg is not None:
            mass_status = "PASS" if result.total_mass_kg <= c.max_mass_kg else "FAIL"

        overall_status = "PASS" if (result.all_constraints_passed and mass_status == "PASS") else "FAIL"

        # 2. Stress & Failure Decomposition
        issues: List[str] = []
        recommendations: List[str] = []
        stress_breakdown: Dict[str, Any] = {}

        if crit_sec:
            # Contribution percentages to unnotched Von Mises
            # vm = sqrt(sig_b^2 + 3*tau^2)
            sig_b = crit_sec.bending_stress
            tau_t = crit_sec.torsional_stress
            vm_sq = sig_b**2 + 3.0 * (tau_t**2)
            if vm_sq > 0:
                pct_bending = (sig_b**2 / vm_sq) * 100.0
                pct_torsion = (3.0 * (tau_t**2) / vm_sq) * 100.0
            else:
                pct_bending = 0.0
                pct_torsion = 0.0

            stress_breakdown = {
                "critical_station_x_mm": round(crit_sec.x * 1000.0, 1),
                "bending_stress_mpa": round(sig_b, 1),
                "bending_percentage": round(pct_bending, 1),
                "torsional_shear_mpa": round(tau_t, 1),
                "torsion_percentage": round(pct_torsion, 1),
                "kt_bending": round(crit_sec.kt_bending, 2),
                "kt_torsion": round(crit_sec.kt_torsion, 2),
                "effective_von_mises_mpa": round(crit_sec.effective_von_mises, 1),
                "material_yield_mpa": result.yield_strength_mpa,
                "material_endurance_mpa": result.endurance_limit_mpa,
            }

            if not result.yield_passed:
                issues.append(
                    f"Von Mises stress ({crit_sec.effective_von_mises:.1f} MPa) exceeds allowable yield limit "
                    f"({result.yield_strength_mpa / c.min_yield_safety_factor:.1f} MPa) with SF_y = {result.min_yield_safety_factor:.2f}."
                )

            if not result.fatigue_passed:
                issues.append(
                    f"Fatigue endurance safety factor ({result.min_fatigue_safety_factor:.2f}) falls below required "
                    f"threshold ({c.min_fatigue_safety_factor:.2f}). Life prediction: {result.fatigue_life_cycles:,.0f} cycles."
                )

            if not result.deflection_passed:
                issues.append(
                    f"Shaft deflection ({result.max_deflection_mm:.3f} mm) exceeds allowable tolerance ({c.max_deflection_mm:.3f} mm)."
                )

            if mass_status == "FAIL":
                issues.append(
                    f"Component mass ({result.total_mass_kg:.2f} kg) exceeds specified budget ({c.max_mass_kg:.2f} kg)."
                )

            # Recommendations based on root-cause physics
            if pct_bending > 60.0:
                recommendations.append(
                    f"Bending moment is the primary driver ({pct_bending:.0f}% of stress). "
                    "Increasing diameter or reducing distance between bearings will yield high stress reduction (sigma ~ 1/d^3)."
                )
            elif pct_torsion > 60.0:
                recommendations.append(
                    f"Transmitted torque is the primary driver ({pct_torsion:.0f}% of stress). "
                    "Increase shaft diameter or consider hollow shafting with higher polar section modulus J/c."
                )

            if crit_sec.kt_bending > 1.4 or crit_sec.kt_torsion > 1.4:
                recommendations.append(
                    f"High geometric stress concentration detected at x={crit_sec.x*1000:.0f} mm (Kt = {crit_sec.kt_bending:.2f}). "
                    "Increase transition fillet radius r to reduce peak stress without increasing total shaft mass."
                )

            if not result.yield_passed or not result.fatigue_passed:
                # Suggest material upgrade
                better_materials = MaterialDatabase.find_candidates_for_safety_factor(
                    result.max_von_mises_mpa,
                    c.min_yield_safety_factor
                )
                if better_materials:
                    recommendations.append(
                        f"Consider upgrading alloy to {better_materials[0].name} (Sy = {better_materials[0].yield_strength_mpa} MPa)."
                    )

        return {
            "overall_status": overall_status,
            "strength_review": strength_status,
            "fatigue_review": fatigue_status,
            "deflection_review": deflection_status,
            "mass_review": mass_status,
            "critical_issues": issues,
            "recommendations": recommendations,
            "stress_breakdown": stress_breakdown,
        }

    @staticmethod
    def verify_ai_claim(ai_claim_is_safe: bool, solver_result: SolverResult) -> Tuple[bool, str]:
        """
        Enforce Section 2: AI is not the physics engine.
        If AI claims safe but solver calculates failure, solver vetoes AI.
        """
        physics_safe = solver_result.all_constraints_passed

        if ai_claim_is_safe and not physics_safe:
            msg = (
                "SAFETY OVERRIDE: FAIL\n"
                "AI proposal or natural language claim asserts system is safe, "
                f"but deterministic physics solver calculates min SF = {solver_result.min_yield_safety_factor:.2f} "
                f"(max deflection = {solver_result.max_deflection_mm:.3f} mm).\n"
                "Deterministic physics solver takes precedence."
            )
            return False, msg

        if not ai_claim_is_safe and physics_safe:
            msg = (
                "NOTE: AI estimated failure, but deterministic physics solver confirms all constraints are satisfied "
                f"(SF_y = {solver_result.min_yield_safety_factor:.2f}, SF_f = {solver_result.min_fatigue_safety_factor:.2f})."
            )
            return True, msg

        return physics_safe, "Physics solver and AI evaluation are consistent."
