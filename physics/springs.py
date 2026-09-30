"""
MDIE Deterministic Helical Spring Physics Engine
Calculates spring rate, Wahl shear stress, solid height, fatigue endurance, and column buckling.
Standards: Shigley's Mechanical Engineering Design / DIN 2089.
"""

import math
from typing import Dict, Any, List, Optional
from components.springs import (
    SpringSpecification,
    SpringGeometry,
    SpringAnalysisResult,
)


class SpringSolver:
    @classmethod
    def solve(cls, spec: SpringSpecification) -> SpringAnalysisResult:
        """
        Solve full mechanical and fatigue characteristics of a helical spring.
        Deterministic engineering calculations per DIN 2089 & Shigley.
        """
        d = spec.wire_diameter_d_mm
        
        # Diameter determination
        if spec.mean_diameter_d_mm and spec.mean_diameter_d_mm > 0:
            mean_d = spec.mean_diameter_d_mm
            outer_d = mean_d + d
        elif spec.outer_diameter_do_mm and spec.outer_diameter_do_mm > 0:
            outer_d = spec.outer_diameter_do_mm
            mean_d = outer_d - d
        else:
            # Default spring index C = 8
            mean_d = 8.0 * d
            outer_d = mean_d + d

        inner_d = mean_d - d
        spring_index_c = mean_d / d

        # End conditions and coil counts
        na = spec.active_coils_na
        end_type = spec.end_type.lower()
        if "squared_and_ground" in end_type or "squared and ground" in end_type:
            total_coils = na + 2.0
            ls = d * total_coils
        elif "squared" in end_type:
            total_coils = na + 2.0
            ls = d * (total_coils + 1.0)
        elif "plain_and_ground" in end_type or "plain and ground" in end_type:
            total_coils = na + 1.0
            ls = d * total_coils
        else:  # plain
            total_coils = na
            ls = d * (total_coils + 1.0)

        # Spring Rate k = (G * d^4) / (8 * D^3 * Na) [N/mm]
        g = spec.shear_modulus_g_mpa
        k = (g * (d ** 4)) / (8.0 * (mean_d ** 3) * na)

        # Operating deflections
        f_min = spec.min_operating_force_n
        f_max = spec.max_operating_force_n
        delta_min = f_min / k if k > 0 else 0.0
        delta_max = f_max / k if k > 0 else 0.0
        stroke = delta_max - delta_min

        # Free length determination
        if spec.free_length_l0_mm and spec.free_length_l0_mm > 0:
            l0 = spec.free_length_l0_mm
        else:
            # Generous clearance to solid (at least 20% clash allowance beyond max stroke)
            l0 = ls + delta_max * 1.25

        delta_solid = max(0.0, l0 - ls)
        f_solid = k * delta_solid

        # Pitch
        pitch = (l0 - 2.0 * d) / na if na > 0 else d

        geom = SpringGeometry(
            wire_diameter_mm=round(d, 2),
            mean_diameter_mm=round(mean_d, 2),
            outer_diameter_mm=round(outer_d, 2),
            inner_diameter_mm=round(inner_d, 2),
            spring_index_c=round(spring_index_c, 2),
            active_coils=round(na, 1),
            total_coils=round(total_coils, 1),
            pitch_mm=round(pitch, 2),
            solid_length_ls_mm=round(ls, 2),
            free_length_l0_mm=round(l0, 2),
        )

        # Wahl curvature correction factor Kw
        # Kw = (4C - 1) / (4C - 4) + 0.615 / C
        kw = ((4.0 * spring_index_c - 1.0) / (4.0 * spring_index_c - 4.0)) + (0.615 / spring_index_c)

        # Torsional shear stresses: tau = Kw * (8 * F * D) / (pi * d^3)
        def calc_tau(force: float) -> float:
            return kw * (8.0 * force * mean_d) / (math.pi * (d ** 3))

        tau_min = calc_tau(f_min)
        tau_max = calc_tau(f_max)
        tau_solid = calc_tau(f_solid)

        # Material Strengths (ASTM A228 Music wire empirical relation if not specified)
        if spec.tensile_strength_sut_mpa:
            sut = spec.tensile_strength_sut_mpa
        else:
            # Sut = A / d^m (A = 2211, m = 0.145)
            sut = 2211.0 / (d ** 0.145)

        # Torsional yield strength Ssy approx 0.45 * Sut (unpreset) or 0.65 * Sut (preset)
        ssy = 0.45 * sut
        # Torsional ultimate strength Ssu approx 0.67 * Sut
        ssu = 0.67 * sut

        # Solid yield safety factor
        sf_solid = ssy / tau_solid if tau_solid > 0 else 999.0

        # Fatigue Analysis (Zimmerli unpeened endurance limit in shear: Ssa = 241 MPa, Ssm = 379 MPa)
        tau_a = (tau_max - tau_min) / 2.0
        tau_m = (tau_max + tau_min) / 2.0
        # Gerber / Goodman torsional fatigue limit: Sse ~ 310 MPa
        sse = 310.0
        denom_fatigue = (tau_a / sse) + (tau_m / ssu)
        sf_fatigue = 1.0 / denom_fatigue if denom_fatigue > 0 else 999.0

        # Buckling Check (Euler column analogy for helical springs)
        # For ends resting on flat parallel ground plates, stable without guide if L0 / D < 4.0
        slenderness = l0 / mean_d
        is_buckling_safe = slenderness <= 4.0 or (delta_max / l0) < 0.35

        # Recommendations & Pass/Fail
        recs = []
        if spring_index_c < 4.0:
            recs.append(f"Spring index C={spring_index_c:.1f} is too tight (C < 4). Difficult to coil and high residual stresses.")
        elif spring_index_c > 12.0:
            recs.append(f"Spring index C={spring_index_c:.1f} is large (C > 12). Wire is prone to tangling and buckling.")

        if sf_solid < 1.15:
            recs.append(f"Solid yield safety factor ({sf_solid:.2f}) is below 1.15. Risk of permanent set when fully compressed.")

        if sf_fatigue < 1.25:
            recs.append(f"Fatigue safety factor ({sf_fatigue:.2f}) is below 1.25 for cyclic duty. Consider shot peening or larger wire diameter.")

        if not is_buckling_safe:
            recs.append(f"Slenderness ratio L0/D={slenderness:.1f} exceeds 4.0. Recommend internal guide rod or external sleeve to prevent lateral buckling.")

        if not recs:
            recs.append("All spring rate, solid clash, fatigue, and lateral buckling criteria satisfied.")

        passed = (sf_solid >= 1.15) and (sf_fatigue >= 1.25) and is_buckling_safe

        return SpringAnalysisResult(
            spec=spec,
            geometry=geom,
            spring_rate_k_n_mm=round(k, 3),
            deflection_min_mm=round(delta_min, 2),
            deflection_max_mm=round(delta_max, 2),
            operating_stroke_mm=round(stroke, 2),
            deflection_to_solid_mm=round(delta_solid, 2),
            force_at_solid_n=round(f_solid, 1),
            wahl_factor_kw=round(kw, 3),
            shear_stress_min_mpa=round(tau_min, 1),
            shear_stress_max_mpa=round(tau_max, 1),
            shear_stress_solid_mpa=round(tau_solid, 1),
            torsional_yield_strength_mpa=round(ssy, 1),
            solid_yield_safety_factor=round(sf_solid, 2),
            fatigue_safety_factor=round(sf_fatigue, 2),
            is_buckling_safe=is_buckling_safe,
            all_criteria_passed=passed,
            verdict="PASS" if passed else "FAIL - Review spring stresses",
            recommendations=recs,
        )
