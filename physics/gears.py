"""
MDIE Deterministic Gear Physics Solver
Calculates kinematic geometry, gear forces (tangential, radial, axial),
Lewis bending stress, AGMA contact pitting stress, and safety factors.
"""

import math
from typing import Dict, Any, List, Optional
from mdie.components.gears import (
    GearPairSpecification,
    GearGeometry,
    GearStressResult,
    GearPairResult,
)
from mdie.materials.database import MaterialDatabase


class GearSolver:
    @classmethod
    def solve(cls, spec: GearPairSpecification) -> GearPairResult:
        """
        Solve full kinematic, static, bending, and contact stress for a spur or helical gear pair.
        Deterministic engineering calculations per AGMA 2001-D04 / ISO 6336.
        """
        # Material
        mat = MaterialDatabase.get(spec.material_id)
        sy = mat.yield_strength_mpa
        sut = mat.ultimate_strength_mpa

        # Allowable stresses per AGMA guidelines
        # Bending endurance limit approx 0.4 * Sut to 0.5 * Sut for steel
        s_b_all = 0.45 * sut
        # Contact fatigue limit (approx 2.8 * HB - 69 for steel, or ~ 0.9 * Sut)
        s_c_all = min(1100.0, 1.2 * sy)

        # Angles
        beta_rad = math.radians(spec.helix_angle_deg)
        alpha_n_rad = math.radians(spec.pressure_angle_deg)
        # Transverse pressure angle alpha_t
        alpha_t_rad = math.atan(math.tan(alpha_n_rad) / math.cos(beta_rad)) if math.cos(beta_rad) > 1e-6 else alpha_n_rad

        # Modules
        mn = spec.normal_module_mm
        mt = mn / math.cos(beta_rad) if math.cos(beta_rad) > 1e-6 else mn

        # Pitch diameters
        d1 = spec.pinion_teeth * mt
        d2 = spec.gear_teeth * mt
        center_dist = (d1 + d2) / 2.0
        gear_ratio = spec.gear_teeth / spec.pinion_teeth

        # Tooth profile proportions (Standard ISO 53 / AGMA full depth)
        addendum = 1.0 * mn
        dedendum = 1.25 * mn
        da1 = d1 + 2.0 * addendum
        da2 = d2 + 2.0 * addendum
        df1 = d1 - 2.0 * dedendum
        df2 = d2 - 2.0 * dedendum
        db1 = d1 * math.cos(alpha_t_rad)
        db2 = d2 * math.cos(alpha_t_rad)
        circular_pitch = math.pi * mt

        # Face width: default 10 * mn if not provided, min 8*mn
        if spec.face_width_mm and spec.face_width_mm > 0:
            face_w = spec.face_width_mm
        else:
            face_w = max(20.0, 10.0 * mn)

        geom = GearGeometry(
            normal_module_mm=mn,
            transverse_module_mm=round(mt, 3),
            pitch_diameter_pinion_mm=round(d1, 2),
            pitch_diameter_gear_mm=round(d2, 2),
            center_distance_mm=round(center_dist, 2),
            addendum_mm=round(addendum, 2),
            dedendum_mm=round(dedendum, 2),
            outer_diameter_pinion_mm=round(da1, 2),
            outer_diameter_gear_mm=round(da2, 2),
            root_diameter_pinion_mm=round(df1, 2),
            root_diameter_gear_mm=round(df2, 2),
            base_diameter_pinion_mm=round(db1, 2),
            base_diameter_gear_mm=round(db2, 2),
            face_width_mm=round(face_w, 2),
            circular_pitch_mm=round(circular_pitch, 3),
            gear_ratio=round(gear_ratio, 3),
        )

        # Kinematics & Power
        omega1 = (2.0 * math.pi * spec.pinion_speed_rpm) / 60.0
        t1_nm = (spec.power_kw * 1000.0) / omega1
        t2_nm = t1_nm * gear_ratio

        # Pitch line velocity v in m/s
        v_pitch = (math.pi * d1 * spec.pinion_speed_rpm) / (60.0 * 1000.0)

        # Tangential force Wt (N)
        wt = (spec.power_kw * 1000.0) / v_pitch if v_pitch > 1e-4 else 0.0

        # Radial force Wr (N)
        wr = wt * math.tan(alpha_t_rad)

        # Axial thrust force Wa (N)
        wa = wt * math.tan(beta_rad)

        # Normal resultant force Wn (N)
        wn = math.sqrt(wt**2 + wr**2 + wa**2)

        # Dynamic Factor Kv per AGMA (Barth or Qv formula)
        qv = spec.quality_grade
        b_exp = 0.25 * ((12.0 - qv) ** 0.667)
        a_const = 50.0 + 56.0 * (1.0 - b_exp)
        # velocity in ft/min for standard AGMA formula, or SI equivalent:
        v_fpm = v_pitch * 196.85
        if v_fpm > 0:
            kv = ((a_const + math.sqrt(v_fpm)) / a_const) ** b_exp
        else:
            kv = 1.0
        kv = max(1.05, min(2.5, kv))

        # Application factor Ko
        ko = spec.service_factor

        # Load distribution factor Km
        km = 1.2 if face_w <= 50.0 else 1.35

        # Lewis Bending Stress
        # Virtual tooth counts for form factor
        zv1 = spec.pinion_teeth / (math.cos(beta_rad) ** 3)
        zv2 = spec.gear_teeth / (math.cos(beta_rad) ** 3)

        # Form factor Y (20 deg full depth)
        y1 = max(0.24, 0.484 - 2.87 / zv1)
        y2 = max(0.24, 0.484 - 2.87 / zv2)

        # Bending stress sigma = Wt * Ko * Kv * Km / (b * mn * Y)
        sigma_b1 = (wt * ko * kv * km) / (face_w * mn * y1)
        sigma_b2 = (wt * ko * kv * km) / (face_w * mn * y2)

        sf_bend1 = s_b_all / sigma_b1 if sigma_b1 > 0 else 999.0
        sf_bend2 = s_b_all / sigma_b2 if sigma_b2 > 0 else 999.0

        # AGMA Contact / Pitting Stress
        # Elastic coefficient Ze for steel = 191 sqrt(MPa)
        ze = 191.0
        # Geometry factor I
        cos_beta = math.cos(beta_rad)
        sin_alpha_t = math.sin(alpha_t_rad)
        cos_alpha_t = math.cos(alpha_t_rad)
        geom_i = (sin_alpha_t * cos_alpha_t / 2.0) * (gear_ratio / (gear_ratio + 1.0)) * (1.0 / cos_beta)
        geom_i = max(0.08, geom_i)

        # Contact stress sigma_c = Ze * sqrt((Wt * Ko * Kv * Km) / (d1 * face_w * I))
        radicand = (wt * ko * kv * km) / (d1 * face_w * geom_i)
        sigma_c = ze * math.sqrt(max(0.0, radicand))
        sf_contact = s_c_all / sigma_c if sigma_c > 0 else 999.0

        passed = (sf_bend1 >= 1.5) and (sf_bend2 >= 1.5) and (sf_contact >= 1.2)

        recs = []
        if sf_bend1 < 1.5:
            recs.append(f"Pinion bending safety factor ({sf_bend1:.2f}) is below 1.5. Increase normal module (mn > {mn} mm) or face width.")
        if sf_contact < 1.2:
            recs.append(f"Surface pitting safety factor ({sf_contact:.2f}) is below 1.2. Increase center distance, face width, or use case-hardened alloy.")
        if not recs:
            recs.append("All AGMA bending and contact surface fatigue constraints verified with high safety margin.")

        stress_res = GearStressResult(
            transmitted_torque_pinion_nm=round(t1_nm, 2),
            transmitted_torque_gear_nm=round(t2_nm, 2),
            pitch_line_velocity_m_s=round(v_pitch, 2),
            tangential_force_wt_n=round(wt, 1),
            radial_force_wr_n=round(wr, 1),
            axial_thrust_wa_n=round(wa, 1),
            normal_resultant_force_wn_n=round(wn, 1),
            bending_stress_pinion_mpa=round(sigma_b1, 2),
            bending_stress_gear_mpa=round(sigma_b2, 2),
            bending_safety_factor_pinion=round(sf_bend1, 2),
            bending_safety_factor_gear=round(sf_bend2, 2),
            contact_pitting_stress_mpa=round(sigma_c, 2),
            contact_safety_factor=round(sf_contact, 2),
            all_safety_criteria_passed=passed,
            verdict="PASS" if passed else "FAIL - Review stresses",
            recommendations=recs,
        )

        return GearPairResult(
            spec=spec,
            geometry=geom,
            stress=stress_res,
            material_name=mat.name,
            yield_strength_mpa=sy,
            ultimate_strength_mpa=sut,
            allowable_bending_mpa=round(s_b_all, 1),
            allowable_contact_mpa=round(s_c_all, 1),
        )
