"""
MDIE Standard Spring Specification & Analysis Models
Covers Helical Compression and Extension Springs per Shigley & DIN 2089.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SpringSpecification(BaseModel):
    name: str = "Helical_Compression_Spring"
    spring_type: str = Field(default="compression", description="'compression' or 'extension'")
    wire_diameter_d_mm: float = Field(..., gt=0, description="Wire diameter d in mm")
    mean_diameter_d_mm: float | None = Field(default=None, description="Mean coil diameter D in mm")
    outer_diameter_do_mm: float | None = Field(default=None, description="Outer diameter Do in mm")
    active_coils_na: float = Field(default=8.0, gt=0, description="Number of active coils Na")
    free_length_l0_mm: float | None = Field(
        default=None, description="Unloaded free length L0 in mm"
    )
    end_type: str = Field(
        default="squared_and_ground",
        description="'squared_and_ground', 'squared', 'plain', or 'plain_and_ground'",
    )
    min_operating_force_n: float = Field(
        default=50.0, ge=0, description="Minimum operating cyclic load in Newtons"
    )
    max_operating_force_n: float = Field(
        default=250.0, gt=0, description="Maximum operating working load in Newtons"
    )
    material_name: str = Field(default="Music Wire (ASTM A228)", description="Spring wire material")
    shear_modulus_g_mpa: float = Field(
        default=79300.0, gt=0, description="Torsional modulus G in MPa (79.3 GPa for steel)"
    )
    tensile_strength_sut_mpa: float | None = Field(
        default=None, description="Tensile strength Sut (auto-estimated from wire d if None)"
    )


class SpringGeometry(BaseModel):
    wire_diameter_mm: float
    mean_diameter_mm: float
    outer_diameter_mm: float
    inner_diameter_mm: float
    spring_index_c: float
    active_coils: float
    total_coils: float
    pitch_mm: float
    solid_length_ls_mm: float
    free_length_l0_mm: float


class SpringAnalysisResult(BaseModel):
    spec: SpringSpecification
    geometry: SpringGeometry
    spring_rate_k_n_mm: float
    deflection_min_mm: float
    deflection_max_mm: float
    operating_stroke_mm: float
    deflection_to_solid_mm: float
    force_at_solid_n: float
    wahl_factor_kw: float
    shear_stress_min_mpa: float
    shear_stress_max_mpa: float
    shear_stress_solid_mpa: float
    torsional_yield_strength_mpa: float
    solid_yield_safety_factor: float
    fatigue_safety_factor: float
    is_buckling_safe: bool
    all_criteria_passed: bool
    verdict: str
    recommendations: list[str] = []
