"""
General Column Buckling Engine (Euler & Johnson Formulations)
Applicable to any structural column, leg, strut, truss member, or compressive frame element.
Authority: Physics verifies.
"""

import math

from pydantic import BaseModel


class BucklingResult(BaseModel):
    slenderness_ratio: float
    transition_slenderness_cc: float
    is_slender_euler: bool
    critical_buckling_load_n: float
    applied_load_n: float
    buckling_safety_factor: float
    passed: bool
    formula_used: str
    calculation_notes: str


class ColumnBuckling:
    """
    Deterministic column buckling calculator supporting both Euler's formula
    (for slender columns) and Johnson's parabolic formula (for intermediate columns).
    """

    @staticmethod
    def calculate(
        elastic_modulus_pa: float,
        yield_strength_pa: float,
        area_m2: float,
        moment_of_inertia_m4: float,
        length_m: float,
        applied_load_n: float,
        k_factor: float = 1.0,  # 1.0 for pinned-pinned, 0.7 for fixed-pinned, 2.0 for cantilever
        min_safety_factor: float = 2.0,
    ) -> BucklingResult:
        """
        Calculates column stability:
        1. Effective length: L_eff = K * L
        2. Radius of gyration: r = sqrt(I / A)
        3. Slenderness ratio: lambda = L_eff / r
        4. Column constant (transition): Cc = sqrt(2 * pi^2 * E / Sy)
        5. If lambda >= Cc -> Euler formula: P_cr = pi^2 * E * I / (L_eff^2)
           If lambda < Cc  -> Johnson parabolic formula: P_cr = A * [Sy - (Sy * lambda / (2*pi))^2 / E]
        6. Buckling safety factor: SF = P_cr / applied_load
        """
        if area_m2 <= 0 or moment_of_inertia_m4 <= 0 or length_m <= 0:
            raise ValueError(
                "Cross-sectional area, moment of inertia, and length must be positive."
            )

        l_eff = k_factor * length_m
        r = math.sqrt(moment_of_inertia_m4 / area_m2)
        slenderness = l_eff / max(r, 1e-9)

        # Transition slenderness Cc
        cc = math.sqrt((2.0 * (math.pi**2) * elastic_modulus_pa) / max(yield_strength_pa, 1e6))

        p_applied = max(abs(applied_load_n), 1e-3)

        if slenderness >= cc:
            # Euler Slender Column
            p_cr = ((math.pi**2) * elastic_modulus_pa * moment_of_inertia_m4) / (l_eff**2)
            formula = "Euler (Long / Slender)"
            notes = f"Slenderness ({slenderness:.1f}) >= Cc ({cc:.1f}). Column fails by elastic instability."
            is_euler = True
        else:
            # Johnson Parabolic Intermediate Column
            bracket = (
                yield_strength_pa
                - ((yield_strength_pa * slenderness / (2.0 * math.pi)) ** 2) / elastic_modulus_pa
            )
            bracket = max(bracket, 0.0)
            p_cr = area_m2 * bracket
            formula = "Johnson (Intermediate Parabolic)"
            notes = f"Slenderness ({slenderness:.1f}) < Cc ({cc:.1f}). Column fails by inelastic buckling."
            is_euler = False

        sf = p_cr / p_applied
        passed = bool(sf >= min_safety_factor)

        return BucklingResult(
            slenderness_ratio=slenderness,
            transition_slenderness_cc=cc,
            is_slender_euler=is_euler,
            critical_buckling_load_n=p_cr,
            applied_load_n=p_applied,
            buckling_safety_factor=sf,
            passed=passed,
            formula_used=formula,
            calculation_notes=notes,
        )
