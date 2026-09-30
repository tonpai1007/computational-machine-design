"""
General Spatial Frame Physics Solver
Deterministic static equilibrium, floor reactions, tipping stability,
Euler and Johnson column buckling, and member combined stresses.
Authority: Physics verifies.
"""

import math
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from core.frame_model import FrameDesignModel, FrameLoads, FrameGeometry, StructuralMaterial
from physics.buckling import ColumnBuckling

class ColumnAnalysisResult(BaseModel):
    leg_id: str                      # 'FL' (Front-Left), 'FR', 'RR', 'RL'
    leg_name: str
    floor_x_mm: float
    floor_y_mm: float
    axial_reaction_n: float          # Vertical reaction force Rz
    horizontal_shear_n: float        # Lateral shear force Rh
    total_reaction_n: float          # Combined reaction vector
    compressive_stress_mpa: float    # P / A
    bending_moment_nm: float         # Bending from lateral loads + eccentricity
    bending_stress_mpa: float        # M / Z
    combined_stress_mpa: float       # P/A + M/Z
    slenderness_ratio: float         # lambda = L_eff / r
    critical_buckling_load_n: float  # P_cr (Euler or Johnson)
    buckling_safety_factor: float    # P_cr / P
    yield_safety_factor: float       # Sy / sigma_combined
    buckling_passed: bool
    yield_passed: bool


class UpperStrutAnalysisResult(BaseModel):
    arm_id: str                      # 'left', 'right'
    applied_vertical_n: float
    applied_lateral_n: float
    applied_foreaft_n: float
    overhang_moment_nm: float
    strut_base_moment_nm: float
    strut_axial_stress_mpa: float
    strut_bending_stress_mpa: float
    strut_combined_stress_mpa: float
    arm_safety_factor: float
    passed: bool


class FrameRailAnalysisResult(BaseModel):
    seat_load_n: float
    rail_bending_moment_nm: float
    rail_bending_stress_mpa: float
    rail_deflection_mm: float
    rail_safety_factor: float
    passed: bool


class FrameSolverResult(BaseModel):
    chair_name: str
    material_name: str
    total_chair_weight_n: float
    total_applied_vertical_n: float
    total_downward_load_n: float

    # Reactions & Stability
    floor_reactions: List[ColumnAnalysisResult]
    tipping_safety_factor_fwd: float
    tipping_safety_factor_rear: float
    tipping_safety_factor_lat: float
    is_statically_stable: bool

    # Upper members / Struts
    armrests: List[UpperStrutAnalysisResult]

    # Frame rails
    seat_frame: FrameRailAnalysisResult

    # Margins
    min_leg_buckling_sf: float
    min_leg_yield_sf: float
    min_arm_sf: float
    seat_deflection_mm: float
    all_safety_criteria_passed: bool

    # Trace
    calculation_log: List[str] = Field(default_factory=list)


class FramePhysicsSolver:
    """Deterministic engineering physics solver for spatial frame and column assemblies."""

    @staticmethod
    def solve(model: FrameDesignModel) -> FrameSolverResult:
        geom = model.geometry
        loads = model.loads
        mat = model.material
        calc_log: List[str] = []

        calc_log.append(f"Starting deterministic structural verification for '{model.name}'.")
        calc_log.append(f"Material: {mat.name} (Sy = {mat.yield_strength_mpa:.1f} MPa, E = {mat.elastic_modulus_gpa:.1f} GPa).")

        n_legs = max(3, geom.num_legs)

        # 1. Structural Self-Weight Estimation
        leg_len_m = math.sqrt((geom.seat_height_mm/1000.0)**2 + (geom.seat_height_mm/1000.0 * math.tan(math.radians(geom.leg_splay_angle_deg)))**2)
        v_legs = float(n_legs) * geom.leg_profile.area_m2 * leg_len_m

        frame_len_m = 2.0 * (geom.seat_width_mm + geom.seat_depth_mm) / 1000.0
        v_frame = geom.frame_profile.area_m2 * frame_len_m

        v_arms = 0.0
        if geom.has_arms:
            v_arms = 2.0 * geom.arm_profile.area_m2 * (geom.armrest_height_above_seat_mm / 1000.0 + geom.armrest_length_mm / 1000.0)

        v_stretchers = 0.0
        if geom.has_stretchers:
            v_stretchers = 2.0 * (geom.seat_width_mm + geom.seat_depth_mm) / 1000.0 * geom.stretcher_profile.area_m2

        v_seat_pan = (geom.seat_width_mm/1000.0) * (geom.seat_depth_mm/1000.0) * (geom.seat_thickness_mm/1000.0) if geom.has_seat_plate else 0.0
        m_pan = v_seat_pan * 700.0

        total_metal_vol = v_legs + v_frame + v_arms + v_stretchers
        metal_mass = total_metal_vol * mat.density_kg_m3
        total_chair_mass_kg = metal_mass + m_pan
        total_chair_weight_n = total_chair_mass_kg * 9.80665

        calc_log.append(f"Calculated structural self-mass = {total_chair_mass_kg:.2f} kg ({total_chair_weight_n:.1f} N) with {n_legs} support columns.")

        # 2. Footprint Geometry on Floor
        splay_rad = math.radians(geom.leg_splay_angle_deg)
        h_m = geom.seat_height_mm / 1000.0
        delta_splay = h_m * math.tan(splay_rad)

        w_seat_m = geom.seat_width_mm / 1000.0
        d_seat_m = geom.seat_depth_mm / 1000.0

        w_floor_m = w_seat_m + 2.0 * delta_splay
        d_floor_m = d_seat_m + 2.0 * delta_splay

        if n_legs == 3:
            r_floor_m = (min(w_seat_m, d_seat_m) / 2.0) + delta_splay
            angles = [math.pi / 2.0, 7.0 * math.pi / 6.0, 11.0 * math.pi / 6.0]
            leg_coords = {
                f"Leg_{i+1}": (r_floor_m * math.cos(ang), r_floor_m * math.sin(ang), f"Column {i+1}")
                for i, ang in enumerate(angles)
            }
        else:
            leg_coords = {
                "FL": (-w_floor_m / 2.0, +d_floor_m / 2.0, "Front-Left Column"),
                "FR": (+w_floor_m / 2.0, +d_floor_m / 2.0, "Front-Right Column"),
                "RR": (+w_floor_m / 2.0, -d_floor_m / 2.0, "Rear-Right Column"),
                "RL": (-w_floor_m / 2.0, -d_floor_m / 2.0, "Rear-Left Column"),
            }

        # 3. External Applied Loads Compilation
        x_seat = (loads.seat_load_center_x_mm) / 1000.0
        y_seat = (loads.seat_load_center_y_mm) / 1000.0
        z_seat = h_m
        f_seat_z = loads.seat_vertical_load_n

        f_arm_l_z = loads.left_arm_vertical_n if geom.has_arms else 0.0
        f_arm_l_x = loads.left_arm_lateral_n if geom.has_arms else 0.0
        f_arm_l_y = loads.left_arm_foreaft_n if geom.has_arms else 0.0

        f_arm_r_z = loads.right_arm_vertical_n if geom.has_arms else 0.0
        f_arm_r_x = loads.right_arm_lateral_n if geom.has_arms else 0.0
        f_arm_r_y = loads.right_arm_foreaft_n if geom.has_arms else 0.0

        x_arm_l = -(w_seat_m / 2.0 + 0.035)
        y_arm_l = 0.0
        z_arm = h_m + (geom.armrest_height_above_seat_mm / 1000.0)

        x_arm_r = +(w_seat_m / 2.0 + 0.035)
        y_arm_r = 0.0

        total_applied_vert_n = f_seat_z + f_arm_l_z + f_arm_r_z
        total_vert_down_n = total_applied_vert_n + total_chair_weight_n

        mx_seat = f_seat_z * y_seat
        my_seat = -f_seat_z * x_seat

        mx_arm_l = f_arm_l_z * y_arm_l - f_arm_l_y * z_arm
        my_arm_l = -f_arm_l_z * x_arm_l + f_arm_l_x * z_arm

        mx_arm_r = f_arm_r_z * y_arm_r - f_arm_r_y * z_arm
        my_arm_r = -f_arm_r_z * x_arm_r + f_arm_r_x * z_arm

        mx_back = 0.0
        if geom.has_backrest and loads.backrest_force_n > 0:
            z_back = h_m + (geom.backrest_height_above_seat_mm * 0.6 / 1000.0)
            mx_back = loads.backrest_force_n * z_back

        mx_total = mx_seat + mx_arm_l + mx_arm_r + mx_back
        my_total = my_seat + my_arm_l + my_arm_r

        calc_log.append(
            f"Global Equilibrium: Total Fz = {total_vert_down_n:.1f} N, "
            f"Overturning Moments: Mx (pitch) = {mx_total:.2f} N·m, My (roll) = {my_total:.2f} N·m."
        )

        # 4. Vertical Floor Contact Reaction per Column
        sum_y2 = sum(c[1]**2 for c in leg_coords.values())
        sum_x2 = sum(c[0]**2 for c in leg_coords.values())

        fx_net = f_arm_l_x + f_arm_r_x
        fy_net = f_arm_l_y + f_arm_r_y
        shear_per_leg = math.sqrt(fx_net**2 + fy_net**2) / float(n_legs)

        leg_results: List[ColumnAnalysisResult] = []
        is_stable = True
        min_reaction = 1e9

        k_factor = 0.85 if geom.has_stretchers else 1.2
        unbraced_len_m = ((geom.seat_height_mm - geom.stretcher_height_mm) / 1000.0) if geom.has_stretchers else h_m

        prof = geom.leg_profile
        e_pa = mat.elastic_modulus_gpa * 1e9
        sy_pa = mat.yield_strength_mpa * 1e6

        # Deterministic Buckling Calculation via general engine
        buck_res = ColumnBuckling.calculate(
            elastic_modulus_pa=e_pa,
            yield_strength_pa=sy_pa,
            area_m2=prof.area_m2,
            moment_of_inertia_m4=prof.moment_of_inertia_m4,
            length_m=unbraced_len_m,
            applied_load_n=total_vert_down_n / float(n_legs),
            k_factor=k_factor
        )
        p_cr = buck_res.critical_buckling_load_n

        calc_log.append(f"Column Slenderness λ = {buck_res.slenderness_ratio:.1f} (Threshold λc = {buck_res.transition_slenderness_cc:.1f}) -> {buck_res.formula_used} P_cr = {p_cr/1000.0:.2f} kN per column.")

        for lid, (lx, ly, lname) in leg_coords.items():
            rz_i = (total_vert_down_n / float(n_legs)) + (mx_total * ly / max(sum_y2, 1e-6)) - (my_total * lx / max(sum_x2, 1e-6))
            if rz_i < min_reaction:
                min_reaction = rz_i

            if rz_i <= 0:
                is_stable = False

            sigma_comp_pa = max(0.0, rz_i) / max(prof.area_m2, 1e-9)
            sigma_comp_mpa = sigma_comp_pa / 1e6

            m_leg_nm = shear_per_leg * unbraced_len_m + max(0.0, rz_i) * (delta_splay * 0.25)
            sigma_bend_pa = m_leg_nm / max(prof.section_modulus_m3, 1e-9)
            sigma_bend_mpa = sigma_bend_pa / 1e6

            sigma_combined_mpa = sigma_comp_mpa + sigma_bend_mpa

            sf_buckling = p_cr / max(rz_i, 1.0)
            sf_yield = mat.yield_strength_mpa / max(sigma_combined_mpa, 0.01)

            leg_results.append(ColumnAnalysisResult(
                leg_id=lid,
                leg_name=lname,
                floor_x_mm=lx * 1000.0,
                floor_y_mm=ly * 1000.0,
                axial_reaction_n=rz_i,
                horizontal_shear_n=shear_per_leg,
                total_reaction_n=math.sqrt(rz_i**2 + shear_per_leg**2),
                compressive_stress_mpa=sigma_comp_mpa,
                bending_moment_nm=m_leg_nm,
                bending_stress_mpa=sigma_bend_mpa,
                combined_stress_mpa=sigma_combined_mpa,
                slenderness_ratio=buck_res.slenderness_ratio,
                critical_buckling_load_n=p_cr,
                buckling_safety_factor=sf_buckling,
                yield_safety_factor=sf_yield,
                buckling_passed=(sf_buckling >= 2.0),
                yield_passed=(sf_yield >= 1.5)
            ))

        # 5. Upper Struts Analysis
        arm_results: List[UpperStrutAnalysisResult] = []
        if geom.has_arms:
            arm_prof = geom.arm_profile
            arm_h_m = geom.armrest_height_above_seat_mm / 1000.0
            arm_overhang_m = geom.armrest_overhang_front_mm / 1000.0

            for arm_id, f_v, f_lat, f_fa in [
                ("left", loads.left_arm_vertical_n, abs(loads.left_arm_lateral_n), abs(loads.left_arm_foreaft_n)),
                ("right", loads.right_arm_vertical_n, abs(loads.right_arm_lateral_n), abs(loads.right_arm_foreaft_n))
            ]:
                m_cantilever = f_v * arm_overhang_m
                m_strut_base = math.sqrt((f_lat * arm_h_m)**2 + (f_fa * arm_h_m)**2 + m_cantilever**2)

                sigma_axial = (f_v / 2.0) / max(arm_prof.area_m2, 1e-9) / 1e6
                sigma_bend = (m_strut_base / 2.0) / max(arm_prof.section_modulus_m3, 1e-9) / 1e6
                sigma_tot = sigma_axial + sigma_bend

                sf_arm = mat.yield_strength_mpa / max(sigma_tot, 0.01)
                arm_results.append(UpperStrutAnalysisResult(
                    arm_id=arm_id,
                    applied_vertical_n=f_v,
                    applied_lateral_n=f_lat,
                    applied_foreaft_n=f_fa,
                    overhang_moment_nm=m_cantilever,
                    strut_base_moment_nm=m_strut_base,
                    strut_axial_stress_mpa=sigma_axial,
                    strut_bending_stress_mpa=sigma_bend,
                    strut_combined_stress_mpa=sigma_tot,
                    arm_safety_factor=sf_arm,
                    passed=(sf_arm >= 2.0)
                ))

        # 6. Main Frame Rails & Deck Deflection
        frame_prof = geom.frame_profile
        span_m = geom.seat_width_mm / 1000.0
        p_rail = (loads.seat_vertical_load_n / 2.0)
        m_rail_max = (p_rail * span_m) / 4.0
        sigma_rail_bend = (m_rail_max / max(frame_prof.section_modulus_m3, 1e-9)) / 1e6

        # Deflection: delta = (P * L^3) / (48 * E * I)
        delta_m = (p_rail * (span_m ** 3)) / (48.0 * (mat.elastic_modulus_gpa * 1e9) * max(frame_prof.moment_of_inertia_m4, 1e-12))
        delta_mm = delta_m * 1000.0

        sf_rail = mat.yield_strength_mpa / max(sigma_rail_bend, 0.01)
        rail_result = FrameRailAnalysisResult(
            seat_load_n=loads.seat_vertical_load_n,
            rail_bending_moment_nm=m_rail_max,
            rail_bending_stress_mpa=sigma_rail_bend,
            rail_deflection_mm=delta_mm,
            rail_safety_factor=sf_rail,
            passed=(sf_rail >= 2.0 and delta_mm < (geom.seat_width_mm / 250.0))
        )

        # 7. Tipping Safety Margins
        lever_fwd = (d_floor_m / 2.0)
        lever_rear = (d_floor_m / 2.0)
        lever_lat = (w_floor_m / 2.0)

        restoring_moment_pitch = total_vert_down_n * min(lever_fwd, lever_rear)
        restoring_moment_roll = total_vert_down_n * lever_lat

        sf_tip_fwd = restoring_moment_pitch / max(abs(mx_total), 1.0)
        sf_tip_rear = restoring_moment_pitch / max(abs(mx_total), 1.0)
        # When my_total is ~0 (balanced lateral loads), there is no net overturning moment
        sf_tip_lat = restoring_moment_roll / abs(my_total) if abs(my_total) > 1.0 else 1e6

        min_leg_buck = min(l.buckling_safety_factor for l in leg_results)
        min_leg_yld = min(l.yield_safety_factor for l in leg_results)
        min_arm_sf = min((a.arm_safety_factor for a in arm_results), default=99.0)

        all_passed = (
            is_stable and
            all(l.buckling_passed and l.yield_passed for l in leg_results) and
            all(a.passed for a in arm_results) and
            rail_result.passed and
            min(sf_tip_fwd, sf_tip_rear, sf_tip_lat) >= 1.5
        )

        return FrameSolverResult(
            chair_name=model.name,
            material_name=mat.name,
            total_chair_weight_n=total_chair_weight_n,
            total_applied_vertical_n=total_applied_vert_n,
            total_downward_load_n=total_vert_down_n,
            floor_reactions=leg_results,
            tipping_safety_factor_fwd=sf_tip_fwd,
            tipping_safety_factor_rear=sf_tip_rear,
            tipping_safety_factor_lat=sf_tip_lat,
            is_statically_stable=is_stable,
            armrests=arm_results,
            seat_frame=rail_result,
            min_leg_buckling_sf=min_leg_buck,
            min_leg_yield_sf=min_leg_yld,
            min_arm_sf=min_arm_sf,
            seat_deflection_mm=delta_mm,
            all_safety_criteria_passed=all_passed,
            calculation_log=calc_log
        )


# Backward compatibility aliases
LegAnalysisResult = ColumnAnalysisResult
ChairSolverResult = FrameSolverResult
ChairPhysicsSolver = FramePhysicsSolver
