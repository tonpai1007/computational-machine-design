"""Golden worked-example tests for the specialized deterministic solvers.

Each expected value below is computed by hand from the governing closed-form
equation (cited per block) and is independent of the solver implementation, so
these tests catch a silent change in the physics rather than merely restating
the code.
"""

import math

import pytest

from components.bolted_joints import BoltedJointSpecification
from components.gears import GearPairSpecification
from components.power_screws import PowerScrewSpecification
from components.springs import SpringSpecification
from physics.bolted_joints import BoltedJointSolver
from physics.gears import GearSolver
from physics.power_screws import PowerScrewSolver
from physics.springs import SpringSolver


def test_spur_gear_kinematics_golden():
    """20T/60T, mn=3, 10 kW @ 1500 rpm.

    d = z*m ; omega = 2*pi*n/60 ; T = P/omega ; v = pi*d*n/(60*1000) ;
    Wt = P/v ; Wr = Wt*tan(alpha) ; Wn = sqrt(Wt^2 + Wr^2).
    """
    spec = GearPairSpecification(
        gear_type="spur", power_kw=10.0, pinion_speed_rpm=1500.0,
        pinion_teeth=20, gear_teeth=60, normal_module_mm=3.0,
    )
    res = GearSolver.solve(spec)

    omega = 2.0 * math.pi * 1500.0 / 60.0     # 157.08 rad/s
    expected_t1 = 10000.0 / omega             # 63.66 N*m
    v = math.pi * 60.0 * 1500.0 / 60000.0     # 4.712 m/s
    expected_wt = 10000.0 / v                 # 2122.1 N
    expected_wr = expected_wt * math.tan(math.radians(20.0))

    assert res.geometry.pitch_diameter_pinion_mm == pytest.approx(60.0)
    assert res.geometry.pitch_diameter_gear_mm == pytest.approx(180.0)
    assert res.geometry.center_distance_mm == pytest.approx(120.0)
    assert res.geometry.gear_ratio == pytest.approx(3.0)
    assert res.stress.transmitted_torque_pinion_nm == pytest.approx(expected_t1, abs=0.05)
    assert res.stress.transmitted_torque_gear_nm == pytest.approx(3.0 * expected_t1, abs=0.1)
    assert res.stress.pitch_line_velocity_m_s == pytest.approx(v, abs=0.01)
    assert res.stress.tangential_force_wt_n == pytest.approx(expected_wt, rel=1e-3)
    assert res.stress.radial_force_wr_n == pytest.approx(expected_wr, rel=1e-3)
    assert res.stress.axial_thrust_wa_n == pytest.approx(0.0, abs=1e-6)
    assert res.stress.normal_resultant_force_wn_n == pytest.approx(
        math.hypot(expected_wt, expected_wr), rel=1e-3)


def test_helical_gear_transverse_geometry_golden():
    """24T helical, mn=4, beta=20 deg: mt = mn/cos(beta), d1 = z*mt."""
    spec = GearPairSpecification(
        gear_type="helical", power_kw=25.0, pinion_speed_rpm=1800.0,
        pinion_teeth=24, gear_teeth=72, normal_module_mm=4.0, helix_angle_deg=20.0,
    )
    res = GearSolver.solve(spec)

    mt = 4.0 / math.cos(math.radians(20.0))    # 4.2567 mm
    assert res.geometry.transverse_module_mm == pytest.approx(mt, abs=0.001)
    assert res.geometry.pitch_diameter_pinion_mm == pytest.approx(24 * mt, abs=0.02)
    assert res.stress.axial_thrust_wa_n > 0.0


def test_helical_spring_rate_and_stress_golden():
    """d=3, D=24 (C=8), Na=8, G=79300 MPa, Fmax=200 N.

    k = G*d^4 / (8*D^3*Na) ; Kw = (4C-1)/(4C-4) + 0.615/C ;
    tau = Kw * 8*F*D / (pi*d^3).
    """
    spec = SpringSpecification(
        wire_diameter_d_mm=3.0, mean_diameter_d_mm=24.0, active_coils_na=8.0,
        min_operating_force_n=40.0, max_operating_force_n=200.0,
        shear_modulus_g_mpa=79300.0,
    )
    res = SpringSolver.solve(spec)

    d, D, na, g = 3.0, 24.0, 8.0, 79300.0
    k = (g * d ** 4) / (8.0 * D ** 3 * na)                 # 7.260 N/mm
    c = D / d
    kw = ((4 * c - 1) / (4 * c - 4)) + (0.615 / c)         # 1.184
    tau_max = kw * (8.0 * 200.0 * D) / (math.pi * d ** 3)  # 536.0 MPa

    assert res.geometry.spring_index_c == pytest.approx(8.0)
    assert res.spring_rate_k_n_mm == pytest.approx(k, abs=0.01)
    assert res.wahl_factor_kw == pytest.approx(kw, abs=0.001)
    assert res.deflection_max_mm == pytest.approx(200.0 / k, abs=0.05)
    assert res.shear_stress_max_mpa == pytest.approx(tau_max, abs=1.0)


def test_bolted_joint_preload_and_margins_golden():
    """M12 class 8.8, grip 40 mm, Pmax=12 kN, 75% preload, K=0.20.

    Fi = 0.75*At*Sp ; T = K*Fi*d/1000 ; C = kb/(kb+km) via Shigley frustum.
    """
    spec = BoltedJointSpecification(
        bolt_designation="M12", property_class="8.8", clamped_length_mm=40.0,
        applied_max_load_n=12000.0, preload_fraction=0.75, torque_coefficient_k=0.20,
    )
    res = BoltedJointSolver.solve(spec)

    at, sp = 84.3, 600.0
    fi = 0.75 * at * sp                        # 37935 N
    torque = 0.20 * fi * 12.0 / 1000.0         # 91.044 N*m

    assert res.tensile_stress_area_mm2 == pytest.approx(at)
    assert res.tightening_preload_fi_n == pytest.approx(fi, abs=1.0)
    assert res.recommended_torque_nm == pytest.approx(torque, abs=0.1)
    # Joint constant and resulting margins from the independent stiffness calc.
    assert res.joint_constant_c == pytest.approx(0.183, abs=0.01)
    assert res.separation_safety_factor == pytest.approx(3.87, abs=0.05)
    assert res.proof_load_safety_factor == pytest.approx(1.26, abs=0.02)
    assert res.yield_safety_factor == pytest.approx(1.34, abs=0.02)
    assert res.fatigue_safety_factor == pytest.approx(1.47, abs=0.03)
    assert res.all_safety_criteria_passed is True


def test_power_screw_torque_and_efficiency_golden():
    """Acme d=24, p=5, single start, F=6 kN, f=0.15, collar fc=0.10/dc=35.

    dm = d - p/2 ; tan(lambda) = lead/(pi*dm) ; Tcollar = F*fc*dc/2 ;
    eff = Tideal/Traise, Tideal = F*lead/(2*pi).
    """
    spec = PowerScrewSpecification(
        nominal_diameter_d_mm=24.0, pitch_p_mm=5.0, num_starts=1,
        axial_load_n=6000.0, thread_type="acme",
    )
    res = PowerScrewSolver.solve(spec)

    dm = 24.0 - 0.5 * 5.0                      # 21.5 mm
    assert res.mean_diameter_dm_mm == pytest.approx(21.5)
    assert res.root_diameter_dr_mm == pytest.approx(19.0)
    assert res.lead_mm == pytest.approx(5.0)
    assert res.lead_angle_deg == pytest.approx(
        math.degrees(math.atan(5.0 / (math.pi * dm))), abs=0.02)
    assert res.torque_collar_nm == pytest.approx(6000.0 * 0.10 * 35.0 / 2000.0, abs=0.05)
    assert res.total_torque_raise_nm == pytest.approx(25.44, abs=0.1)
    assert res.efficiency_pct == pytest.approx(18.8, abs=0.4)
    assert res.linear_speed_mm_s == pytest.approx(5.0, abs=0.01)
    assert res.is_self_locking is True
    assert res.bearing_pressure_mpa == pytest.approx(5.08, abs=0.05)
    assert res.axial_direct_stress_mpa == pytest.approx(21.2, abs=0.2)
