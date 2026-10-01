"""
Deterministic Physics Solver for Motor Mounting Brackets & Plates
Evaluates root bending stress, bolt shear, bearing/tearout stress, and Von Mises yield criteria.
Authority: Physics verifies.
"""

import math

from pydantic import BaseModel, Field

from core.bracket_model import BracketModel


class BracketSolverResult(BaseModel):
    """Complete stress and verification summary for a mounting bracket."""

    bracket_name: str
    material_name: str
    plate_mass_kg: float

    # Forces & Moments
    motor_weight_n: float
    overturning_moment_nm: float
    root_bending_stress_mpa: float
    plate_shear_stress_mpa: float
    max_von_mises_mpa: float

    # Bolt Fastener Diagnostics
    motor_bolt_shear_stress_mpa: float
    hole_bearing_stress_mpa: float
    bolt_safety_factor: float
    plate_yield_safety_factor: float

    passed: bool
    calculation_log: list[str] = Field(default_factory=list)


class BracketPhysicsSolver:
    """Calculates deterministic structural stresses and fastener safety factors on mounting brackets."""

    @staticmethod
    def solve(model: BracketModel) -> BracketSolverResult:
        g = model.geometry
        l = model.loads
        m = model.material
        log: list[str] = []

        log.append(f"Solving structural verification for '{model.name}' ({m.name}).")

        # 1. Mass & Applied Gravity Force
        f_grav_n = l.motor_mass_kg * 9.80665
        vol_base_m3 = (
            (g.base_length_mm / 1000.0) * (g.base_width_mm / 1000.0) * (g.thickness_mm / 1000.0)
        )
        vol_upright_m3 = (
            (g.upright_height_mm / 1000.0) * (g.base_width_mm / 1000.0) * (g.thickness_mm / 1000.0)
        )
        total_vol_m3 = vol_base_m3 + vol_upright_m3
        bracket_mass_kg = total_vol_m3 * m.density_kg_m3

        log.append(
            f"Motor weight = {f_grav_n:.1f} N. Bracket tare mass = {bracket_mass_kg:.2f} kg."
        )

        # 2. Overturning Moment at Bracket Root / Bend
        arm_m = l.cantilever_arm_mm / 1000.0
        h_m = (g.upright_height_mm * 0.6) / 1000.0
        m_gravity_nm = f_grav_n * arm_m
        m_thrust_nm = l.axial_thrust_n * h_m
        m_torque_nm = l.motor_torque_nm
        m_root_total_nm = m_gravity_nm + m_thrust_nm + m_torque_nm

        log.append(
            f"Root overturning moment M = {m_root_total_nm:.2f} N·m (Cantilever: {m_gravity_nm:.1f} N·m, Torque: {m_torque_nm:.1f} N·m)."
        )

        # 3. Flange / Root Bending Stress
        # Section modulus Z = W * t^2 / 6
        w_m = g.base_width_mm / 1000.0
        t_m = g.thickness_mm / 1000.0
        z_mod_m3 = (w_m * (t_m**2)) / 6.0

        # Gusset reinforcement factor
        gusset_factor = 1.8 if g.has_gussets else 1.0
        sigma_bend_pa = m_root_total_nm / (z_mod_m3 * gusset_factor)
        sigma_bend_mpa = sigma_bend_pa / 1e6

        # Direct transverse shear
        area_shear_m2 = w_m * t_m
        tau_shear_pa = f_grav_n / max(area_shear_m2, 1e-9)
        tau_shear_mpa = tau_shear_pa / 1e6

        # Combined Von Mises stress at bracket root
        # sigma_vm = sqrt(sigma_b^2 + 3 * tau^2)
        sigma_vm_mpa = math.sqrt(sigma_bend_mpa**2 + 3.0 * (tau_shear_mpa**2))

        # 4. Motor Mounting Bolt Analysis
        pat = g.motor_bolt_pattern
        n_bolts = max(1, pat.num_holes)
        r_bcd_m = (
            (pat.bolt_circle_diameter_mm / 2.0) / 1000.0
            if pat.bolt_circle_diameter_mm > 0
            else 0.035
        )

        # Shear force per bolt from motor gravity + torque reaction
        f_shear_grav_per_bolt = f_grav_n / float(n_bolts)
        f_shear_torque_per_bolt = l.motor_torque_nm / max(float(n_bolts) * r_bcd_m, 1e-6)
        f_bolt_total_shear_n = math.sqrt(f_shear_grav_per_bolt**2 + f_shear_torque_per_bolt**2)

        d_bolt_m = pat.hole_diameter_mm / 1000.0
        area_bolt_m2 = math.pi * (d_bolt_m**2) / 4.0
        tau_bolt_pa = f_bolt_total_shear_n / max(area_bolt_m2, 1e-9)
        tau_bolt_mpa = tau_bolt_pa / 1e6

        # Hole Bearing / Tearout Stress on Plate: sigma_brg = F / (d * t)
        area_brg_m2 = d_bolt_m * t_m
        sigma_brg_pa = f_bolt_total_shear_n / max(area_brg_m2, 1e-9)
        sigma_brg_mpa = sigma_brg_pa / 1e6

        # 5. Safety Factors
        # Grade 8.8 structural bolt proof shear ~ 300 MPa
        bolt_allowable_shear_mpa = 300.0
        sf_bolt = bolt_allowable_shear_mpa / max(tau_bolt_mpa, 0.01)
        sf_plate = m.yield_strength_mpa / max(sigma_vm_mpa, 0.01)

        passed = (sf_plate >= 1.5) and (sf_bolt >= 2.0)

        log.append(
            f"Plate Von Mises = {sigma_vm_mpa:.1f} MPa (Yield SF: {sf_plate:.2f}). Bolt Shear = {tau_bolt_mpa:.1f} MPa (Bolt SF: {sf_bolt:.2f})."
        )
        log.append(f"Verification Verdict: {'PASS' if passed else 'FAIL'}.")

        return BracketSolverResult(
            bracket_name=model.name,
            material_name=m.name,
            plate_mass_kg=bracket_mass_kg,
            motor_weight_n=f_grav_n,
            overturning_moment_nm=m_root_total_nm,
            root_bending_stress_mpa=sigma_bend_mpa,
            plate_shear_stress_mpa=tau_shear_mpa,
            max_von_mises_mpa=sigma_vm_mpa,
            motor_bolt_shear_stress_mpa=tau_bolt_mpa,
            hole_bearing_stress_mpa=sigma_brg_mpa,
            bolt_safety_factor=sf_bolt,
            plate_yield_safety_factor=sf_plate,
            passed=passed,
            calculation_log=log,
        )
