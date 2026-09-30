"""
General Multi-Body Frame & Structural Assembly Data Model
Supports any 3D spatial machine frame, furniture assembly, chassis, stand, or truss.
"""

import math
from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel, Field

class TubeProfile(BaseModel):
    """Structural tube or solid section for columns, beams, rails, and frame members."""
    profile_type: str = Field(default="round_tube", description="'round_tube', 'round_solid', 'square_tube', 'square_solid'")
    outer_dimension_mm: float = Field(default=28.0, description="Outer diameter or square width in mm")
    wall_thickness_mm: float = Field(default=2.0, description="Wall thickness in mm (0 for solid)")

    @property
    def outer_dim_m(self) -> float:
        return self.outer_dimension_mm / 1000.0

    @property
    def wall_thick_m(self) -> float:
        return self.wall_thickness_mm / 1000.0

    @property
    def area_m2(self) -> float:
        d_o = self.outer_dim_m
        t = self.wall_thick_m
        if self.profile_type == "round_solid":
            return math.pi * (d_o ** 2) / 4.0
        elif self.profile_type == "round_tube":
            d_i = max(0.0, d_o - 2.0 * t)
            return math.pi * (d_o ** 2 - d_i ** 2) / 4.0
        elif self.profile_type == "square_solid":
            return d_o ** 2
        elif self.profile_type == "square_tube":
            d_i = max(0.0, d_o - 2.0 * t)
            return (d_o ** 2) - (d_i ** 2)
        return math.pi * (d_o ** 2) / 4.0

    @property
    def moment_of_inertia_m4(self) -> float:
        d_o = self.outer_dim_m
        t = self.wall_thick_m
        if self.profile_type == "round_solid":
            return math.pi * (d_o ** 4) / 64.0
        elif self.profile_type == "round_tube":
            d_i = max(0.0, d_o - 2.0 * t)
            return math.pi * (d_o ** 4 - d_i ** 4) / 64.0
        elif self.profile_type == "square_solid":
            return (d_o ** 4) / 12.0
        elif self.profile_type == "square_tube":
            d_i = max(0.0, d_o - 2.0 * t)
            return (d_o ** 4 - d_i ** 4) / 12.0
        return math.pi * (d_o ** 4) / 64.0

    @property
    def section_modulus_m3(self) -> float:
        c = self.outer_dim_m / 2.0
        return self.moment_of_inertia_m4 / max(c, 1e-6)

    @property
    def radius_of_gyration_m(self) -> float:
        return math.sqrt(self.moment_of_inertia_m4 / max(self.area_m2, 1e-9))


class StructuralMaterial(BaseModel):
    """Material specifications for structural frames and assemblies."""
    id: str = "STEEL_1018"
    name: str = "AISI 1018 Steel"
    yield_strength_mpa: float = 370.0
    ultimate_strength_mpa: float = 440.0
    elastic_modulus_gpa: float = 205.0
    poissons_ratio: float = 0.29
    density_kg_m3: float = 7870.0
    allowable_bending_stress_mpa: float = 220.0
    allowable_shear_stress_mpa: float = 120.0
    cost_per_kg_usd: float = 2.50


# Standard Structural Materials Catalog
STRUCTURAL_MATERIALS: Dict[str, StructuralMaterial] = {
    "STEEL_1018": StructuralMaterial(
        id="STEEL_1018",
        name="AISI 1018 Steel Tubing",
        yield_strength_mpa=370.0,
        ultimate_strength_mpa=440.0,
        elastic_modulus_gpa=205.0,
        poissons_ratio=0.29,
        density_kg_m3=7870.0,
        cost_per_kg_usd=2.50
    ),
    "STAINLESS_304": StructuralMaterial(
        id="STAINLESS_304",
        name="AISI 304 Stainless Steel",
        yield_strength_mpa=290.0,
        ultimate_strength_mpa=620.0,
        elastic_modulus_gpa=193.0,
        poissons_ratio=0.29,
        density_kg_m3=8000.0,
        cost_per_kg_usd=6.50
    ),
    "AL_6061_T6": StructuralMaterial(
        id="AL_6061_T6",
        name="Aluminum 6061-T6 Structural Tube",
        yield_strength_mpa=276.0,
        ultimate_strength_mpa=310.0,
        elastic_modulus_gpa=68.9,
        poissons_ratio=0.33,
        density_kg_m3=2700.0,
        cost_per_kg_usd=8.00
    ),
    "WHITE_OAK": StructuralMaterial(
        id="WHITE_OAK",
        name="Solid White Oak Timber",
        yield_strength_mpa=55.0,
        ultimate_strength_mpa=85.0,
        elastic_modulus_gpa=12.2,
        poissons_ratio=0.37,
        density_kg_m3=750.0,
        cost_per_kg_usd=4.50
    ),
}


class FrameGeometry(BaseModel):
    """Parametric dimensions for any 4-post or multi-column structural frame/assembly."""
    seat_height_mm: float = Field(default=450.0, description="Height from floor to top of main platform / seat (mm)")
    seat_width_mm: float = Field(default=480.0, description="Platform / seat pan width X (mm)")
    seat_depth_mm: float = Field(default=460.0, description="Platform / seat pan depth Y (mm)")
    seat_thickness_mm: float = Field(default=22.0, description="Top pan thickness (mm)")

    # Upper supports / arms
    armrest_height_above_seat_mm: float = Field(default=210.0, description="Upper arm/rail height above platform (mm)")
    armrest_length_mm: float = Field(default=320.0, description="Length of arm pad along depth (mm)")
    armrest_width_mm: float = Field(default=45.0, description="Width of arm pad (mm)")
    armrest_overhang_front_mm: float = Field(default=60.0, description="Forward cantilever overhang (mm)")

    # Backrest / vertical extension
    backrest_height_above_seat_mm: float = Field(default=420.0, description="Backrest height above platform (mm)")
    backrest_angle_deg: float = Field(default=98.0, description="Recline angle from horizontal (deg)")

    # Topology & Member Configuration
    topology_type: str = Field(default="chair", description="'chair', 'stool', 'table', 'bench'")
    num_legs: int = Field(default=4, description="Number of support legs / columns (e.g. 3, 4, 6)")
    has_arms: bool = Field(default=True, description="Whether armrests/side rails are included")
    has_backrest: bool = Field(default=True, description="Whether a backrest is included")
    has_seat_plate: bool = Field(default=True, description="Whether top platform/seat pan is included")

    # Columns / Legs & Bracing
    leg_splay_angle_deg: float = Field(default=3.5, description="Outward splay angle of columns for tipping stability (deg)")
    stretcher_height_mm: float = Field(default=150.0, description="Height of lower cross bracing stretchers from floor (mm)")
    has_stretchers: bool = Field(default=True, description="Whether lower cross-braces/stretchers are present")

    # Member Profiles
    leg_profile: TubeProfile = Field(default_factory=lambda: TubeProfile(profile_type="round_tube", outer_dimension_mm=28.0, wall_thickness_mm=2.0))
    frame_profile: TubeProfile = Field(default_factory=lambda: TubeProfile(profile_type="square_tube", outer_dimension_mm=25.0, wall_thickness_mm=2.0))
    arm_profile: TubeProfile = Field(default_factory=lambda: TubeProfile(profile_type="round_tube", outer_dimension_mm=22.0, wall_thickness_mm=1.8))
    stretcher_profile: TubeProfile = Field(default_factory=lambda: TubeProfile(profile_type="round_tube", outer_dimension_mm=19.0, wall_thickness_mm=1.5))


class FrameLoads(BaseModel):
    """External applied loads for structural frame assemblies."""
    seat_vertical_load_n: float = Field(default=1300.0, description="Primary vertical downward load (N)")
    seat_load_center_x_mm: float = Field(default=0.0, description="Lateral offset of load center from midpoint (mm)")
    seat_load_center_y_mm: float = Field(default=-25.0, description="Fore/aft offset of load center (mm)")

    left_arm_vertical_n: float = Field(default=450.0, description="Left vertical downward force (N)")
    left_arm_lateral_n: float = Field(default=-150.0, description="Left outward lateral force (N)")
    left_arm_foreaft_n: float = Field(default=0.0, description="Left fore/aft thrust (N)")

    right_arm_vertical_n: float = Field(default=450.0, description="Right vertical downward force (N)")
    right_arm_lateral_n: float = Field(default=150.0, description="Right outward lateral force (N)")
    right_arm_foreaft_n: float = Field(default=0.0, description="Right fore/aft thrust (N)")

    backrest_force_n: float = Field(default=300.0, description="Horizontal thrust on backrest (N)")


class FrameDesignModel(BaseModel):
    """Complete engineering definition of a 3D structural frame assembly."""
    name: str = "Structural Frame Assembly"
    geometry: FrameGeometry = Field(default_factory=FrameGeometry)
    loads: FrameLoads = Field(default_factory=FrameLoads)
    material: StructuralMaterial = Field(default_factory=lambda: STRUCTURAL_MATERIALS["STEEL_1018"])


# Aliases for backwards compatibility
ChairGeometry = FrameGeometry
ChairLoads = FrameLoads
ChairDesignModel = FrameDesignModel
ChairMaterial = StructuralMaterial
CHAIR_MATERIALS = STRUCTURAL_MATERIALS
