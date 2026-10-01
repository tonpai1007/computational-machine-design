"""
MDIE Deterministic Bolted Joint Physics Engine
Calculates bolt stiffness, member cone stiffness (Shigley frustum), joint constant C,
tightening preload & torque, joint separation safety, proof load safety, and Goodman fatigue.
Standards: VDI 2230 / Shigley's Mechanical Engineering Design.
"""

import math

from components.bolted_joints import (
    METRIC_BOLT_CATALOG,
    PROPERTY_CLASS_DATA,
    BoltedJointResult,
    BoltedJointSpecification,
)


class BoltedJointSolver:
    @classmethod
    def solve(cls, spec: BoltedJointSpecification) -> BoltedJointResult:
        """
        Solve full mechanical equilibrium and safety margins for a preloaded bolted joint.
        """
        # Resolve bolt geometry
        desig = spec.bolt_designation.upper().strip()
        if desig not in METRIC_BOLT_CATALOG:
            # Fallback to M12 if not recognized
            desig = "M12"
        bolt_geo = METRIC_BOLT_CATALOG[desig]

        d = bolt_geo.nominal_diameter_mm
        at = bolt_geo.tensile_stress_area_mm2
        ad = (math.pi * (d**2)) / 4.0

        # Property class strengths
        pclass = spec.property_class.strip()
        if pclass not in PROPERTY_CLASS_DATA:
            pclass = "8.8"
        pdata = PROPERTY_CLASS_DATA[pclass]
        sp = pdata["proof_strength_mpa"]
        sy = pdata["yield_strength_mpa"]
        sut = pdata["ultimate_strength_mpa"]
        se = pdata["endurance_limit_mpa"]

        # Modulus
        eb = 207000.0  # Steel bolt E = 207 GPa
        l_grip = spec.clamped_length_mm

        # Member modulus
        mat_lower = spec.clamped_material.lower()
        if "al" in mat_lower:
            em = 71000.0  # Aluminum 71 GPa
        elif "cast" in mat_lower or "iron" in mat_lower:
            em = 100000.0  # Cast Iron 100 GPa
        else:
            em = 207000.0  # Steel 207 GPa

        # Bolt stiffness kb = Ad * At * Eb / (Ad * lt + At * ld)
        # Approximate threaded length in grip lt ~ 0.5 * l_grip
        lt = 0.5 * l_grip
        ld = 0.5 * l_grip
        denom_kb = (ad * lt) + (at * ld)
        kb = (ad * at * eb) / denom_kb if denom_kb > 0 else (at * eb) / l_grip

        # Member stiffness km using Shigley / Fritsche frustum approximation
        # km = 0.5774 * pi * Em * d / (2 * ln(5 * (0.5774 * l + 0.5 * d) / (0.5774 * l + 2.5 * d)))
        term_num = 5.0 * (0.5774 * l_grip + 0.5 * d)
        term_den = 0.5774 * l_grip + 2.5 * d
        if term_den > 0 and (term_num / term_den) > 1.0:
            ln_term = math.log(term_num / term_den)
            km = (0.5774 * math.pi * em * d) / (2.0 * ln_term)
        else:
            # Fallback simple cylinder approximation
            km = (ad * 3.0 * em) / l_grip

        # Joint constant C
        c_joint = kb / (kb + km) if (kb + km) > 0 else 0.2

        # Tightening Preload Fi = preload_fraction * At * Sp (N)
        fi = spec.preload_fraction * at * sp

        # Recommended tightening torque T = K * Fi * d [N*m]
        # (d in mm -> /1000 to convert to N*m)
        t_tighten_nm = (spec.torque_coefficient_k * fi * d) / 1000.0

        # Load distribution under external load P
        p_max = spec.applied_max_load_n
        p_min = spec.applied_min_load_n

        # Total load on bolt Fb = Fi + C * P
        fb_max = fi + c_joint * p_max

        # Clamping force on member Fm = Fi - (1 - C) * P
        fm_min = fi - (1.0 - c_joint) * p_max

        # Safety factors
        # 1. Joint Separation Safety Factor (must be > 1.0, recommended >= 1.5)
        # Separation occurs when Fm = 0 => P_sep = Fi / (1 - C)
        sf_sep = fi / ((1.0 - c_joint) * p_max) if ((1.0 - c_joint) * p_max) > 0 else 999.0

        # 2. Proof Load Safety Factor np = (Sp * At) / Fb_max
        proof_load = sp * at
        sf_proof = proof_load / fb_max if fb_max > 0 else 999.0

        # 3. Yield Safety Factor ny = (Sy * At) / Fb_max
        yield_load = sy * at
        sf_yield = yield_load / fb_max if fb_max > 0 else 999.0

        # 4. Goodman Fatigue Safety Factor
        # Alternating bolt stress sigma_a = C * (P_max - P_min) / (2 * At)
        sigma_a = (c_joint * (p_max - p_min)) / (2.0 * at)
        # Mean bolt stress sigma_m = Fi/At + C * (P_max + P_min) / (2 * At)
        sigma_m = (fi / at) + (c_joint * (p_max + p_min)) / (2.0 * at)

        # Modified Goodman fatigue limit
        denom_fatigue = (sigma_a / se) + (sigma_m / sut)
        sf_fatigue = 1.0 / denom_fatigue if denom_fatigue > 0 else 999.0

        # Compliance verdict
        passed = (sf_sep >= 1.2) and (sf_proof >= 1.15) and (sf_fatigue >= 1.3)

        recs = []
        if sf_sep < 1.2:
            recs.append(
                f"Joint separation safety factor ({sf_sep:.2f}) is low. Joint will leak or gap under {p_max / 1000:.1f} kN. Increase bolt size or preload."
            )
        if sf_proof < 1.15:
            recs.append(
                f"Proof load safety factor ({sf_proof:.2f}) is below 1.15. Risk of permanent bolt elongation. Use Grade 10.9 or larger diameter."
            )
        if sf_fatigue < 1.3:
            recs.append(
                f"Fatigue safety factor ({sf_fatigue:.2f}) is below 1.3 for cyclic load. Increase clamped member stiffness or use Grade 10.9."
            )
        if not recs:
            recs.append(
                "All bolted joint clamping, separation, proof load, and fatigue criteria are safely satisfied."
            )

        return BoltedJointResult(
            spec=spec,
            bolt_diameter_mm=d,
            tensile_stress_area_mm2=at,
            proof_strength_mpa=sp,
            yield_strength_mpa=sy,
            ultimate_strength_mpa=sut,
            tightening_preload_fi_n=round(fi, 1),
            recommended_torque_nm=round(t_tighten_nm, 1),
            bolt_stiffness_kb_n_mm=round(kb, 1),
            member_stiffness_km_n_mm=round(km, 1),
            joint_constant_c=round(c_joint, 3),
            max_total_bolt_load_n=round(fb_max, 1),
            min_residual_clamp_force_n=round(fm_min, 1),
            separation_safety_factor=round(sf_sep, 2),
            proof_load_safety_factor=round(sf_proof, 2),
            yield_safety_factor=round(sf_yield, 2),
            fatigue_safety_factor=round(sf_fatigue, 2),
            all_safety_criteria_passed=passed,
            verdict="PASS" if passed else "FAIL - Review clamping forces",
            recommendations=recs,
        )
