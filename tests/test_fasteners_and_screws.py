"""
Test Suite: Bolted Joints (VDI 2230) & Power Screws (ASME B1.5)
"""

import pytest
from components.bolted_joints import BoltedJointSpecification
from physics.bolted_joints import BoltedJointSolver
from components.power_screws import PowerScrewSpecification
from physics.power_screws import PowerScrewSolver


def test_bolted_joint_vdi2230():
    spec = BoltedJointSpecification(
        name="Test_M12_Joint",
        bolt_designation="M12",
        property_class="8.8",
        clamped_length_mm=40.0,
        applied_max_load_n=12000.0
    )

    res = BoltedJointSolver.solve(spec)

    assert res.bolt_diameter_mm == 12.0
    assert res.tightening_preload_fi_n > 0
    assert res.recommended_torque_nm > 0
    assert 0 < res.joint_constant_c < 1.0
    assert res.separation_safety_factor > 0
    assert res.proof_load_safety_factor > 0


def test_power_screw_asme():
    spec = PowerScrewSpecification(
        nominal_diameter_d_mm=24.0,
        pitch_p_mm=5.0,
        num_starts=1,
        axial_load_n=6000.0,
        thread_type="acme"
    )

    res = PowerScrewSolver.solve(spec)

    assert res.mean_diameter_dm_mm == 21.5
    assert res.total_torque_raise_nm > res.torque_collar_nm
    assert res.is_self_locking is True
    assert 0 < res.efficiency_pct < 100.0
    assert res.bearing_pressure_mpa > 0
