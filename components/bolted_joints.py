"""
MDIE Standard Bolted Joint Specification & Catalog
Covers ISO Metric Threaded Fasteners per ISO 898-1 / VDI 2230 / Shigley.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class BoltGeometrySpec(BaseModel):
    designation: str
    nominal_diameter_mm: float
    pitch_mm: float
    tensile_stress_area_mm2: float


# Standard ISO metric coarse pitch thread catalog
METRIC_BOLT_CATALOG: dict[str, BoltGeometrySpec] = {
    "M6": BoltGeometrySpec(
        designation="M6", nominal_diameter_mm=6.0, pitch_mm=1.0, tensile_stress_area_mm2=20.1
    ),
    "M8": BoltGeometrySpec(
        designation="M8", nominal_diameter_mm=8.0, pitch_mm=1.25, tensile_stress_area_mm2=36.6
    ),
    "M10": BoltGeometrySpec(
        designation="M10", nominal_diameter_mm=10.0, pitch_mm=1.5, tensile_stress_area_mm2=58.0
    ),
    "M12": BoltGeometrySpec(
        designation="M12", nominal_diameter_mm=12.0, pitch_mm=1.75, tensile_stress_area_mm2=84.3
    ),
    "M14": BoltGeometrySpec(
        designation="M14", nominal_diameter_mm=14.0, pitch_mm=2.0, tensile_stress_area_mm2=115.0
    ),
    "M16": BoltGeometrySpec(
        designation="M16", nominal_diameter_mm=16.0, pitch_mm=2.0, tensile_stress_area_mm2=157.0
    ),
    "M20": BoltGeometrySpec(
        designation="M20", nominal_diameter_mm=20.0, pitch_mm=2.5, tensile_stress_area_mm2=245.0
    ),
    "M24": BoltGeometrySpec(
        designation="M24", nominal_diameter_mm=24.0, pitch_mm=3.0, tensile_stress_area_mm2=353.0
    ),
    "M30": BoltGeometrySpec(
        designation="M30", nominal_diameter_mm=30.0, pitch_mm=3.5, tensile_stress_area_mm2=561.0
    ),
}

# ISO 898-1 Property Classes (Proof strength Sp, Yield Sy, Ultimate Sut in MPa)
PROPERTY_CLASS_DATA = {
    "8.8": {
        "proof_strength_mpa": 600.0,
        "yield_strength_mpa": 640.0,
        "ultimate_strength_mpa": 800.0,
        "endurance_limit_mpa": 129.0,
    },
    "10.9": {
        "proof_strength_mpa": 830.0,
        "yield_strength_mpa": 940.0,
        "ultimate_strength_mpa": 1040.0,
        "endurance_limit_mpa": 162.0,
    },
    "12.9": {
        "proof_strength_mpa": 970.0,
        "yield_strength_mpa": 1100.0,
        "ultimate_strength_mpa": 1220.0,
        "endurance_limit_mpa": 190.0,
    },
}


class BoltedJointSpecification(BaseModel):
    name: str = "Structural_Flange_Joint"
    bolt_designation: str = Field(
        default="M12", description="Standard metric bolt (e.g. M8, M10, M12, M16, M20)"
    )
    property_class: str = Field(
        default="8.8", description="Bolt property class: '8.8', '10.9', or '12.9'"
    )
    clamped_length_mm: float = Field(
        default=50.0, gt=0, description="Total clamped grip length l in mm"
    )
    clamped_material: str = Field(
        default="Steel", description="'Steel', 'Cast Iron', or 'Aluminum'"
    )
    applied_min_load_n: float = Field(
        default=0.0, ge=0, description="Minimum external cyclic tension load per bolt in N"
    )
    applied_max_load_n: float = Field(
        default=15000.0, gt=0, description="Maximum external tension load per bolt in N"
    )
    torque_coefficient_k: float = Field(
        default=0.20, gt=0, description="Torque coefficient K (0.15 lubricated, 0.20 standard)"
    )
    preload_fraction: float = Field(
        default=0.75,
        ge=0.5,
        le=0.95,
        description="Preload as fraction of proof load (0.75 reusable, 0.90 permanent)",
    )


class BoltedJointResult(BaseModel):
    spec: BoltedJointSpecification
    bolt_diameter_mm: float
    tensile_stress_area_mm2: float
    proof_strength_mpa: float
    yield_strength_mpa: float
    ultimate_strength_mpa: float
    tightening_preload_fi_n: float
    recommended_torque_nm: float
    bolt_stiffness_kb_n_mm: float
    member_stiffness_km_n_mm: float
    joint_constant_c: float
    max_total_bolt_load_n: float
    min_residual_clamp_force_n: float
    separation_safety_factor: float
    proof_load_safety_factor: float
    yield_safety_factor: float
    fatigue_safety_factor: float
    all_safety_criteria_passed: bool
    verdict: str
    recommendations: list[str] = []
