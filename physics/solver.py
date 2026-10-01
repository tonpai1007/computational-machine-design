"""
MDIE Unified Deterministic Physics Solver
Orchestrates static equilibrium, stress concentration analysis, Euler-Bernoulli deflection,
and Marin/Goodman fatigue life verification. Generates verified results with full audit traces.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from cad.openscad import OpenSCADGenerator
from core.models import (
    EngineeringModel,
    SectionStress,
    ShaftSegment,
    SolverResult,
)
from materials.database import MaterialDatabase
from physics.deflection import DeflectionSolver
from physics.equilibrium import EquilibriumSolver
from physics.fatigue import FatigueSolver
from physics.stress import StressSolver


class PhysicsSolver:
    @staticmethod
    def validate_model(model: EngineeringModel) -> list[str]:
        """Verify model sanity and raise or report physical impossibilities."""
        errors: list[str] = []
        if model.total_length <= 0:
            errors.append(f"Invalid total length: {model.total_length} m <= 0")

        # If no segments, create a default uniform segment
        if not model.segments:
            model.segments.append(
                ShaftSegment(
                    start_pos=0.0,
                    end_pos=model.total_length,
                    outer_diameter=0.030,
                    inner_diameter=0.0,
                    feature_type="smooth",
                )
            )

        for idx, seg in enumerate(model.segments):
            if seg.outer_diameter <= 0:
                errors.append(f"Segment {idx + 1}: Outer diameter {seg.outer_diameter} m <= 0")
            if seg.inner_diameter >= seg.outer_diameter:
                errors.append(
                    f"Segment {idx + 1}: Inner diameter ({seg.inner_diameter * 1000:.1f} mm) >= "
                    f"outer diameter ({seg.outer_diameter * 1000:.1f} mm). Geometry is physically invalid."
                )
            if seg.start_pos < 0 or seg.end_pos > model.total_length * 1.001:
                errors.append(
                    f"Segment {idx + 1} bounds [{seg.start_pos}, {seg.end_pos}] outside total length {model.total_length}"
                )

        for idx, sup in enumerate(model.supports):
            if sup.position < 0 or sup.position > model.total_length * 1.001:
                errors.append(
                    f"Support {idx + 1} at x={sup.position}m outside shaft span [0, {model.total_length}]m"
                )

        for idx, p in enumerate(model.point_loads):
            if p.position < 0 or p.position > model.total_length * 1.001:
                errors.append(
                    f"Point load {idx + 1} at x={p.position}m outside shaft span [0, {model.total_length}]m"
                )

        return errors

    @classmethod
    def solve(cls, model: EngineeringModel) -> SolverResult:
        """
        Execute deterministic physics verification on engineering model.
        Guaranteed deterministic execution: no LLM or heuristics in this path.
        """
        timestamp_str = datetime.now().isoformat()
        calc_steps: list[str] = []
        calc_steps.append(f"MDIE Physics Solver initiated for '{model.name}'.")

        # 1. Geometry & boundary validation
        validation_errors = cls.validate_model(model)
        if validation_errors:
            err_msg = "; ".join(validation_errors)
            calc_steps.append(f"VALIDATION FAILED: {err_msg}")
            return SolverResult(
                model_name=model.name,
                timestamp=timestamp_str,
                success=False,
                error_message=err_msg,
                calculation_steps=calc_steps,
            )

        # 2. Material lookup
        try:
            material = MaterialDatabase.get(model.material_id)
            calc_steps.append(
                f"Material loaded: {material.name} (Sy={material.yield_strength_mpa} MPa, Sut={material.ultimate_strength_mpa} MPa)"
            )
        except Exception as e:
            return SolverResult(
                model_name=model.name,
                timestamp=timestamp_str,
                success=False,
                error_message=f"Material Error: {str(e)}",
                calculation_steps=calc_steps,
            )

        # 3. Static Equilibrium & Internal Distributions
        try:
            reactions, eq_logs = EquilibriumSolver.solve_reactions(model)
            calc_steps.extend(eq_logs)
            internal_dist = EquilibriumSolver.calculate_internal_distributions(model, reactions)
        except Exception as e:
            return SolverResult(
                model_name=model.name,
                timestamp=timestamp_str,
                success=False,
                error_message=f"Equilibrium Solver Error: {str(e)}",
                calculation_steps=calc_steps,
            )

        # 4. Stress and Stress Concentrations
        try:
            stress_data = StressSolver.calculate_stresses(model, internal_dist, material)
            crit_sec: SectionStress = stress_data["critical_section"]
            calc_steps.append(
                f"Peak Von Mises stress: {stress_data['max_von_mises_mpa']:.2f} MPa at x={stress_data['max_von_mises_x']:.3f}m "
                f"(Kt_bending={crit_sec.kt_bending:.2f}, Kt_torsion={crit_sec.kt_torsion:.2f})"
            )
        except Exception as e:
            return SolverResult(
                model_name=model.name,
                timestamp=timestamp_str,
                success=False,
                error_message=f"Stress Solver Error: {str(e)}",
                calculation_steps=calc_steps,
            )

        # 5. Deflection & Slope Integration
        try:
            defl_data = DeflectionSolver.solve_deflection(model, internal_dist, material)
            calc_steps.append(
                f"Max shaft deflection: {defl_data['max_deflection_mm']:.3f} mm at x={defl_data['max_deflection_x']:.3f}m"
            )
        except Exception as e:
            return SolverResult(
                model_name=model.name,
                timestamp=timestamp_str,
                success=False,
                error_message=f"Deflection Solver Error: {str(e)}",
                calculation_steps=calc_steps,
            )

        # 6. Fatigue Life & Endurance Evaluation
        try:
            fatigue_data = FatigueSolver.evaluate_fatigue(crit_sec, material, model)
            crit_sec.fatigue_safety_factor = fatigue_data["nf_goodman"]
            crit_sec.predicted_cycles = fatigue_data["predicted_cycles"]
            calc_steps.append(
                f"Endurance limit Se={fatigue_data['endurance_limit_mpa']:.2f} MPa. "
                f"Goodman SF_f={fatigue_data['nf_goodman']:.2f}. Life: {fatigue_data['life_description']}"
            )
        except Exception as e:
            return SolverResult(
                model_name=model.name,
                timestamp=timestamp_str,
                success=False,
                error_message=f"Fatigue Solver Error: {str(e)}",
                calculation_steps=calc_steps,
            )

        # 7. Mass Calculation
        total_mass = 0.0
        for seg in model.segments:
            vol = seg.area * seg.length
            total_mass += vol * material.density_kg_m3
        calc_steps.append(f"Total calculated component mass: {total_mass:.3f} kg")

        # 8. Constraint Evaluation
        c = model.constraints
        yield_passed = crit_sec.yield_safety_factor >= c.min_yield_safety_factor
        fatigue_passed = crit_sec.fatigue_safety_factor >= c.min_fatigue_safety_factor
        deflection_passed = defl_data["max_deflection_mm"] <= c.max_deflection_mm
        slope_passed = defl_data["max_slope_rad"] <= c.max_slope_rad
        all_passed = bool(yield_passed and fatigue_passed and deflection_passed and slope_passed)

        calc_steps.append(
            f"Constraint Summary: Yield ({crit_sec.yield_safety_factor:.2f} >= {c.min_yield_safety_factor})={yield_passed}; "
            f"Fatigue ({crit_sec.fatigue_safety_factor:.2f} >= {c.min_fatigue_safety_factor})={fatigue_passed}; "
            f"Deflection ({defl_data['max_deflection_mm']:.3f} <= {c.max_deflection_mm})={deflection_passed}."
        )

        # 9. Standard Machine Components: Bearings & Keyways
        bearings_selected: list[dict[str, Any]] = []
        try:
            from components.bearings import BearingCatalog

            rpm = model.speed_rpm if (model.speed_rpm and model.speed_rpm > 0) else 1500.0
            for r in reactions:
                d_at_sup, _, _ = StressSolver.get_diameter_and_segment_at(model, r.position)
                b_res = BearingCatalog.select_bearing(d_at_sup, r.reaction_force_n, rpm)
                bearings_selected.append(b_res.model_dump())
                calc_steps.append(
                    f"Selected {b_res.bearing.designation} (C={b_res.bearing.dynamic_load_c_kn} kN) at x={r.position * 1000:.0f} mm: "
                    f"L10h = {b_res.l10h_hours:,.0f} hours ({b_res.status})"
                )
        except Exception as e:
            calc_steps.append(f"Bearing catalog notice: {str(e)}")

        keyway_analysis: dict[str, Any] | None = None
        try:
            from components.keys import KeyEngine

            nominal_torque = model.calculate_nominal_torque()
            kw_seg = next((s for s in model.segments if s.keyway), None)
            if kw_seg and kw_seg.keyway and nominal_torque > 0:
                k_res = KeyEngine.verify_key(
                    kw_seg.outer_diameter, nominal_torque, key_length_m=kw_seg.keyway.length
                )
                keyway_analysis = k_res.model_dump()
                calc_steps.append(
                    f"Verified {k_res.standard}: Shear SF = {k_res.shear_safety_factor:.2f}, "
                    f"Crushing SF = {k_res.crushing_safety_factor:.2f} ({'PASS' if k_res.passed else 'FAIL'})"
                )
            elif nominal_torque > 0 and model.segments:
                mid_seg = model.segments[len(model.segments) // 2]
                k_res = KeyEngine.verify_key(mid_seg.outer_diameter, nominal_torque)
                keyway_analysis = k_res.model_dump()
        except Exception as e:
            calc_steps.append(f"Keyway verification notice: {str(e)}")

        # 10. Parametric OpenSCAD Code
        try:
            scad_script = OpenSCADGenerator.generate_scad(model, crit_sec.x, highlight_stress=True)
        except Exception as e:
            scad_script = f"// OpenSCAD Generation Error: {str(e)}"

        return SolverResult(
            model_name=model.name,
            timestamp=timestamp_str,
            success=True,
            reactions=reactions,
            applied_torque_nm=model.calculate_nominal_torque(),
            x_stations=internal_dist["x"],
            shear_force=internal_dist["shear_force"],
            bending_moment=internal_dist["bending_moment"],
            torque_distribution=internal_dist["torque"],
            slope_rad=defl_data["slope_rad"],
            deflection_mm=defl_data["deflection_mm"],
            von_mises_stress_mpa=stress_data["effective_von_mises_mpa"],
            diameters_mm=stress_data["diameters_mm"],
            max_bending_moment_nm=internal_dist["max_bending_moment"],
            max_bending_moment_x=internal_dist["max_bending_moment_x"],
            max_shear_force_n=internal_dist["max_shear_force"],
            max_deflection_mm=defl_data["max_deflection_mm"],
            max_deflection_x=defl_data["max_deflection_x"],
            max_slope_rad=defl_data["max_slope_rad"],
            max_von_mises_mpa=stress_data["max_von_mises_mpa"],
            max_von_mises_x=stress_data["max_von_mises_x"],
            critical_section=crit_sec,
            material_name=material.name,
            yield_strength_mpa=material.yield_strength_mpa,
            ultimate_strength_mpa=material.ultimate_strength_mpa,
            endurance_limit_mpa=fatigue_data["endurance_limit_mpa"],
            total_mass_kg=round(total_mass, 3),
            min_yield_safety_factor=round(crit_sec.yield_safety_factor, 2),
            min_fatigue_safety_factor=round(crit_sec.fatigue_safety_factor, 2),
            fatigue_life_cycles=fatigue_data["predicted_cycles"],
            is_infinite_life=fatigue_data["is_infinite_life"],
            yield_passed=yield_passed,
            fatigue_passed=fatigue_passed,
            deflection_passed=deflection_passed,
            slope_passed=slope_passed,
            all_constraints_passed=all_passed,
            bearings_selected=bearings_selected,
            keyway_analysis=keyway_analysis,
            openscad_code=scad_script,
            calculation_steps=calc_steps,
        )
