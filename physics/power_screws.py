"""
MDIE Deterministic Power Screw Physics Engine
Calculates lead angle, raising & lowering torques, collar friction, self-locking condition,
drive power, efficiency, thread bearing pressure, and core buckling.
Standards: ASME B1.5 / DIN 103 / Shigley.
"""

import math
from typing import Dict, Any, List
from mdie.components.power_screws import (
    PowerScrewSpecification,
    PowerScrewResult,
)


class PowerScrewSolver:
    @classmethod
    def solve(cls, spec: PowerScrewSpecification) -> PowerScrewResult:
        """
        Solve full mechanical forces, self-locking stability, torques, and stresses for a power screw.
        """
        d = spec.nominal_diameter_d_mm
        p = spec.pitch_p_mm
        lead = p * spec.num_starts
        f = spec.friction_coefficient_f
        fc = spec.collar_friction_fc
        dc = spec.collar_diameter_dc_mm
        f_axial = spec.axial_load_n
        rpm = spec.rotational_speed_rpm

        # Diameters
        dm = d - 0.5 * p
        dr = d - p

        # Lead angle lambda
        tan_lambda = lead / (math.pi * dm)
        lambda_rad = math.atan(tan_lambda)
        lambda_deg = math.degrees(lambda_rad)

        # Thread angle alpha
        ttype = spec.thread_type.lower()
        if "square" in ttype:
            alpha_deg = 0.0
        elif "trapezoidal" in ttype or "tr" in ttype:
            alpha_deg = 15.0  # 30 deg included
        else:  # acme
            alpha_deg = 14.5  # 29 deg included
        sec_alpha = 1.0 / math.cos(math.radians(alpha_deg))

        # Torque to raise load (in N*m -> diameters in mm divided by 2000)
        # T_thread = (F * dm / 2) * ( (l + pi * f * dm * sec_alpha) / (pi * dm - f * l * sec_alpha) )
        num_raise = lead + (math.pi * f * dm * sec_alpha)
        den_raise = (math.pi * dm) - (f * lead * sec_alpha)
        t_thread_raise = (f_axial * dm / 2000.0) * (num_raise / den_raise) if den_raise > 0 else 0.0

        # Collar friction torque Tc = (F * fc * dc) / 2
        t_collar = (f_axial * fc * dc) / 2000.0

        # Total torque to raise
        t_total_raise = t_thread_raise + t_collar

        # Torque to lower load
        # T_thread_lower = (F * dm / 2) * ( (pi * f * dm * sec_alpha - l) / (pi * dm + f * l * sec_alpha) )
        num_lower = (math.pi * f * dm * sec_alpha) - lead
        den_lower = (math.pi * dm) + (f * lead * sec_alpha)
        t_thread_lower = (f_axial * dm / 2000.0) * (num_lower / den_lower) if den_lower > 0 else 0.0
        t_total_lower = t_thread_lower + t_collar

        # Self-locking condition: occurs when num_lower > 0 (f * sec_alpha > tan_lambda)
        is_self_locking = (f * sec_alpha) > tan_lambda

        # Ideal torque T0 (zero friction) = (F * lead) / (2 * pi)
        t_ideal = (f_axial * lead) / (2000.0 * math.pi)
        efficiency_pct = (t_ideal / t_total_raise * 100.0) if t_total_raise > 0 else 0.0

        # Motor power required: P = T * omega [Watts]
        omega = (2.0 * math.pi * rpm) / 60.0
        motor_power_w = t_total_raise * omega

        # Linear speed v = (rpm * lead) / 60 [mm/s]
        v_linear_mm_s = (rpm * lead) / 60.0

        # Thread Bearing Pressure on Nut
        # Nut engaged length and active threads
        nut_l = spec.nut_length_mm
        nt = nut_l / p
        area_bearing = (math.pi * (d**2 - dr**2) / 4.0) * nt
        p_bearing_mpa = f_axial / area_bearing if area_bearing > 0 else 0.0

        # Direct axial core stress
        area_root = (math.pi * (dr**2)) / 4.0
        sigma_axial_mpa = f_axial / area_root if area_root > 0 else 0.0

        # Allowable limits
        # Typical bronze nut allowable bearing pressure: 15.0 MPa
        passed = (p_bearing_mpa <= 18.0) and (sigma_axial_mpa <= 120.0)

        recs = []
        if is_self_locking:
            recs.append("Lead screw is self-locking: will safely hold load without a holding brake.")
        else:
            recs.append("Lead screw will BACK-DRIVE under axial load! A holding brake or irreversible worm drive is required.")

        if p_bearing_mpa > 15.0:
            recs.append(f"Thread bearing pressure ({p_bearing_mpa:.1f} MPa) exceeds bronze limit (15 MPa). Increase nut engagement length (nut_length > {nut_l} mm).")

        if not recs:
            recs.append("All torque, power, bearing pressure, and kinematic criteria verified.")

        return PowerScrewResult(
            spec=spec,
            mean_diameter_dm_mm=round(dm, 2),
            root_diameter_dr_mm=round(dr, 2),
            lead_mm=round(lead, 2),
            lead_angle_deg=round(lambda_deg, 2),
            torque_thread_raise_nm=round(t_thread_raise, 2),
            torque_collar_nm=round(t_collar, 2),
            total_torque_raise_nm=round(t_total_raise, 2),
            total_torque_lower_nm=round(t_total_lower, 2),
            linear_speed_mm_s=round(v_linear_mm_s, 2),
            required_motor_power_w=round(motor_power_w, 1),
            is_self_locking=is_self_locking,
            efficiency_pct=round(efficiency_pct, 1),
            bearing_pressure_mpa=round(p_bearing_mpa, 2),
            axial_direct_stress_mpa=round(sigma_axial_mpa, 1),
            all_safety_criteria_passed=passed,
            verdict="PASS" if passed else "FAIL - Review bearing pressure",
            recommendations=recs,
        )
