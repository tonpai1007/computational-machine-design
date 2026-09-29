"""
MDIE Standard Power Screw Specification & Models
Covers Acme, Square, and ISO Trapezoidal Lead Screws per ASME B1.5 / DIN 103 / Shigley.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class PowerScrewSpecification(BaseModel):
    name: str = "Linear_Actuator_Lead_Screw"
    thread_type: str = Field(default="acme", description="'acme', 'square', or 'trapezoidal'")
    nominal_diameter_d_mm: float = Field(default=24.0, gt=0, description="Major nominal outer diameter d in mm")
    pitch_p_mm: float = Field(default=5.0, gt=0, description="Thread pitch p in mm")
    num_starts: int = Field(default=1, ge=1, description="Number of thread starts (1 for single, 2 for double, etc.)")
    axial_load_n: float = Field(default=8000.0, gt=0, description="Axial working load F in Newtons")
    friction_coefficient_f: float = Field(default=0.15, gt=0, description="Thread friction coefficient f (e.g. 0.15 steel on bronze)")
    collar_diameter_dc_mm: float = Field(default=35.0, ge=0, description="Mean thrust collar diameter dc in mm")
    collar_friction_fc: float = Field(default=0.10, ge=0, description="Collar friction coefficient fc (0 if thrust bearing used)")
    rotational_speed_rpm: float = Field(default=60.0, gt=0, description="Screw rotational speed in RPM")
    nut_length_mm: float = Field(default=35.0, gt=0, description="Engaged length of bronze nut in mm")


class PowerScrewResult(BaseModel):
    spec: PowerScrewSpecification
    mean_diameter_dm_mm: float
    root_diameter_dr_mm: float
    lead_mm: float
    lead_angle_deg: float
    torque_thread_raise_nm: float
    torque_collar_nm: float
    total_torque_raise_nm: float
    total_torque_lower_nm: float
    linear_speed_mm_s: float
    required_motor_power_w: float
    is_self_locking: bool
    efficiency_pct: float
    bearing_pressure_mpa: float
    axial_direct_stress_mpa: float
    all_safety_criteria_passed: bool
    verdict: str
    recommendations: List[str] = []
