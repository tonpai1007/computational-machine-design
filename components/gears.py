"""
MDIE Standard Gear Specification & Geometry Engine
Covers Spur and Helical gears per AGMA 2001-D04 and ISO 6336.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class GearPairSpecification(BaseModel):
    name: str = "Spur_Gear_Pair"
    gear_type: str = Field(default="spur", description="'spur' or 'helical'")
    power_kw: float = Field(..., gt=0, description="Transmitted power in kilowatts")
    pinion_speed_rpm: float = Field(..., gt=0, description="Pinion rotational speed in RPM")
    pinion_teeth: int = Field(default=20, ge=12, description="Number of teeth on pinion (z1)")
    gear_teeth: int = Field(default=60, ge=12, description="Number of teeth on driven gear (z2)")
    normal_module_mm: float = Field(default=3.0, gt=0, description="Normal module mn in mm")
    pressure_angle_deg: float = Field(
        default=20.0, description="Standard pressure angle (normally 20 deg)"
    )
    helix_angle_deg: float = Field(
        default=0.0, ge=0.0, le=45.0, description="Helix angle beta in degrees (0 for spur)"
    )
    face_width_mm: float | None = Field(
        default=None, description="Face width b in mm (auto-sized if None)"
    )
    pinion_bore_mm: float = Field(
        default=25.0, gt=0, description="Pinion shaft bore diameter in mm"
    )
    gear_bore_mm: float = Field(default=40.0, gt=0, description="Gear shaft bore diameter in mm")
    material_id: str = Field(default="AISI_4140_QT", description="Gear material ID")
    quality_grade: int = Field(
        default=7, ge=5, le=11, description="AGMA quality grade (typically 6-8)"
    )
    service_factor: float = Field(default=1.25, ge=1.0, description="Application service factor Ko")


class GearGeometry(BaseModel):
    normal_module_mm: float
    transverse_module_mm: float
    pitch_diameter_pinion_mm: float
    pitch_diameter_gear_mm: float
    center_distance_mm: float
    addendum_mm: float
    dedendum_mm: float
    outer_diameter_pinion_mm: float
    outer_diameter_gear_mm: float
    root_diameter_pinion_mm: float
    root_diameter_gear_mm: float
    base_diameter_pinion_mm: float
    base_diameter_gear_mm: float
    face_width_mm: float
    circular_pitch_mm: float
    gear_ratio: float


class GearStressResult(BaseModel):
    transmitted_torque_pinion_nm: float
    transmitted_torque_gear_nm: float
    pitch_line_velocity_m_s: float
    tangential_force_wt_n: float
    radial_force_wr_n: float
    axial_thrust_wa_n: float
    normal_resultant_force_wn_n: float
    bending_stress_pinion_mpa: float
    bending_stress_gear_mpa: float
    bending_safety_factor_pinion: float
    bending_safety_factor_gear: float
    contact_pitting_stress_mpa: float
    contact_safety_factor: float
    all_safety_criteria_passed: bool
    verdict: str
    recommendations: list[str] = []


class GearPairResult(BaseModel):
    spec: GearPairSpecification
    geometry: GearGeometry
    stress: GearStressResult
    material_name: str
    yield_strength_mpa: float
    ultimate_strength_mpa: float
    allowable_bending_mpa: float
    allowable_contact_mpa: float
