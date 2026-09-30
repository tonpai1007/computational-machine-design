"""
MDIE Optimization and Design Exploration Engine
Generates design candidates, performs parametric optimization (e.g. minimum mass / cost),
and evaluates candidate feasibility through the deterministic physics solver.
"""

import copy
import math
from typing import List, Dict, Any, Optional, Tuple
from scipy.optimize import minimize_scalar
from core.models import EngineeringModel, ShaftSegment, SolverResult, EngineeringConstraints
from materials.database import MaterialDatabase, Material
from physics.solver import PhysicsSolver

# Standard metric shaft diameters in millimeters (ISO 286 / DIN standard transmission shafting)
STANDARD_SHAFT_DIAMETERS_MM = [
    12, 14, 15, 16, 17, 18, 19, 20, 22, 24, 25, 28, 30, 32, 35, 38, 40, 42, 45, 48, 50,
    55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 110, 120
]

class DesignCandidate:
    def __init__(
        self,
        name: str,
        model: EngineeringModel,
        result: SolverResult,
        material: Material,
        mass_kg: float,
        cost_metric: float,
        description: str = ""
    ):
        self.name = name
        self.model = model
        self.result = result
        self.material = material
        self.mass_kg = mass_kg
        self.cost_metric = cost_metric
        self.description = description

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "material_name": self.material.name,
            "material_id": self.material.id,
            "diameter_mm": [s.outer_diameter * 1000.0 for s in self.model.segments],
            "mass_kg": round(self.mass_kg, 3),
            "cost_metric": round(self.cost_metric, 2),
            "max_von_mises_mpa": round(self.result.max_von_mises_mpa, 2),
            "max_deflection_mm": round(self.result.max_deflection_mm, 4),
            "min_yield_sf": round(self.result.min_yield_safety_factor, 2),
            "min_fatigue_sf": round(self.result.min_fatigue_safety_factor, 2),
            "is_infinite_life": self.result.is_infinite_life,
            "all_constraints_passed": self.result.all_constraints_passed,
            "description": self.description,
        }

class DesignOptimizer:
    @staticmethod
    def explore_candidates(
        base_model: EngineeringModel,
        candidate_materials: Optional[List[str]] = None,
        scale_factors: Optional[List[float]] = None
    ) -> List[DesignCandidate]:
        """
        Generate multiple engineering candidate designs by varying materials and diameters.
        Evaluates each candidate through the deterministic physics solver.
        """
        if candidate_materials is None:
            candidate_materials = ["AISI_1018_CD", "AISI_1045_CD", "AISI_4140_QT", "AL_7075_T6"]
        if scale_factors is None:
            scale_factors = [0.85, 1.0, 1.15, 1.30]

        candidates: List[DesignCandidate] = []
        c_count = 1

        for mat_id in candidate_materials:
            try:
                mat = MaterialDatabase.get(mat_id)
            except KeyError:
                continue

            for scale in scale_factors:
                m_cand = copy.deepcopy(base_model)
                m_cand.name = f"Candidate {chr(64 + c_count)}"
                m_cand.material_id = mat_id
                
                # Scale segment diameters
                for seg in m_cand.segments:
                    # Round to nearest integer mm for realistic manufacturing
                    d_mm = round(seg.outer_diameter * 1000.0 * scale)
                    seg.outer_diameter = max(10.0, d_mm) / 1000.0
                    if seg.inner_diameter > 0:
                        di_mm = round(seg.inner_diameter * 1000.0 * scale)
                        seg.inner_diameter = min(seg.outer_diameter * 0.8, di_mm / 1000.0)

                # Solve through physics engine
                res = PhysicsSolver.solve(m_cand)
                cost = res.total_mass_kg * mat.cost_index_per_kg
                desc = (
                    f"Material: {mat.name}, Diameter scaled {scale*100:.0f}%. "
                    f"Status: {'FEASIBLE' if res.all_constraints_passed else 'NON-COMPLIANT'}"
                )

                candidates.append(DesignCandidate(
                    name=m_cand.name,
                    model=m_cand,
                    result=res,
                    material=mat,
                    mass_kg=res.total_mass_kg,
                    cost_metric=cost,
                    description=desc
                ))
                c_count += 1

        # Sort candidates: feasible first, then by mass ascending
        candidates.sort(key=lambda c: (not c.result.all_constraints_passed, c.mass_kg))
        return candidates

    @staticmethod
    def optimize_diameter_for_minimum_mass(
        base_model: EngineeringModel,
        target_sf_yield: float = 2.0,
        target_sf_fatigue: float = 1.5,
        max_defl_mm: float = 1.0
    ) -> Tuple[Optional[DesignCandidate], List[str]]:
        """
        Finds the minimum standardized diameter that satisfies all yield, fatigue, and deflection constraints.
        """
        logs = []
        logs.append(f"Starting minimum mass diameter optimization for '{base_model.name}'.")
        
        mat = MaterialDatabase.get(base_model.material_id)
        best_candidate: Optional[DesignCandidate] = None

        # Search across standard diameters
        for d_mm in STANDARD_SHAFT_DIAMETERS_MM:
            d_m = d_mm / 1000.0
            test_model = copy.deepcopy(base_model)
            for seg in test_model.segments:
                seg.outer_diameter = d_m
            
            test_model.constraints.min_yield_safety_factor = target_sf_yield
            test_model.constraints.min_fatigue_safety_factor = target_sf_fatigue
            test_model.constraints.max_deflection_mm = max_defl_mm

            res = PhysicsSolver.solve(test_model)
            if res.all_constraints_passed:
                cost = res.total_mass_kg * mat.cost_index_per_kg
                best_candidate = DesignCandidate(
                    name=f"Optimal Standard Design (d={d_mm} mm)",
                    model=test_model,
                    result=res,
                    material=mat,
                    mass_kg=res.total_mass_kg,
                    cost_metric=cost,
                    description=f"Optimal standardized diameter: {d_mm} mm. Minimum mass: {res.total_mass_kg:.3f} kg."
                )
                logs.append(
                    f"Optimal solution found: d={d_mm} mm (Mass={res.total_mass_kg:.3f} kg, "
                    f"SF_y={res.min_yield_safety_factor:.2f}, SF_f={res.min_fatigue_safety_factor:.2f}, "
                    f"Defl={res.max_deflection_mm:.3f} mm)"
                )
                break

        if not best_candidate:
            logs.append("No standard diameter up to 120 mm satisfied all constraints. Review loads or material selection.")

        return best_candidate, logs
