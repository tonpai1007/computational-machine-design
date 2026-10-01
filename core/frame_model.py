"""
General Multi-Body Frame & Structural Assembly Data Model
Supports any 3D spatial machine frame, furniture assembly, chassis, stand, or truss.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, Field

# Arm pad is a fixed-thickness capping plate, not a structural member. It is
# defined here so CAD and physics agree on it without physics importing from cad.
ARM_PAD_THICKNESS_MM = 18.0


class TubeProfile(BaseModel):
    """Structural tube or solid section for columns, beams, rails, and frame members."""

    profile_type: str = Field(
        default="round_tube",
        description="'round_tube', 'round_solid', 'square_tube', 'square_solid'",
    )
    outer_dimension_mm: float = Field(
        default=28.0, description="Outer diameter or square width in mm"
    )
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
            return math.pi * (d_o**2) / 4.0
        elif self.profile_type == "round_tube":
            d_i = max(0.0, d_o - 2.0 * t)
            return math.pi * (d_o**2 - d_i**2) / 4.0
        elif self.profile_type == "square_solid":
            return d_o**2
        elif self.profile_type == "square_tube":
            d_i = max(0.0, d_o - 2.0 * t)
            return (d_o**2) - (d_i**2)
        return math.pi * (d_o**2) / 4.0

    @property
    def moment_of_inertia_m4(self) -> float:
        d_o = self.outer_dim_m
        t = self.wall_thick_m
        if self.profile_type == "round_solid":
            return math.pi * (d_o**4) / 64.0
        elif self.profile_type == "round_tube":
            d_i = max(0.0, d_o - 2.0 * t)
            return math.pi * (d_o**4 - d_i**4) / 64.0
        elif self.profile_type == "square_solid":
            return (d_o**4) / 12.0
        elif self.profile_type == "square_tube":
            d_i = max(0.0, d_o - 2.0 * t)
            return (d_o**4 - d_i**4) / 12.0
        return math.pi * (d_o**4) / 64.0

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
STRUCTURAL_MATERIALS: dict[str, StructuralMaterial] = {
    "STEEL_1018": StructuralMaterial(
        id="STEEL_1018",
        name="AISI 1018 Steel Tubing",
        yield_strength_mpa=370.0,
        ultimate_strength_mpa=440.0,
        elastic_modulus_gpa=205.0,
        poissons_ratio=0.29,
        density_kg_m3=7870.0,
        cost_per_kg_usd=2.50,
    ),
    "STAINLESS_304": StructuralMaterial(
        id="STAINLESS_304",
        name="AISI 304 Stainless Steel",
        yield_strength_mpa=290.0,
        ultimate_strength_mpa=620.0,
        elastic_modulus_gpa=193.0,
        poissons_ratio=0.29,
        density_kg_m3=8000.0,
        cost_per_kg_usd=6.50,
    ),
    "AL_6061_T6": StructuralMaterial(
        id="AL_6061_T6",
        name="Aluminum 6061-T6 Structural Tube",
        yield_strength_mpa=276.0,
        ultimate_strength_mpa=310.0,
        elastic_modulus_gpa=68.9,
        poissons_ratio=0.33,
        density_kg_m3=2700.0,
        cost_per_kg_usd=8.00,
    ),
    "WHITE_OAK": StructuralMaterial(
        id="WHITE_OAK",
        name="Solid White Oak Timber",
        yield_strength_mpa=55.0,
        ultimate_strength_mpa=85.0,
        elastic_modulus_gpa=12.2,
        poissons_ratio=0.37,
        density_kg_m3=750.0,
        cost_per_kg_usd=4.50,
    ),
}


class FrameGeometry(BaseModel):
    """Parametric dimensions for any 4-post or multi-column structural frame/assembly."""

    seat_height_mm: float = Field(
        default=450.0, description="Height from floor to top of main platform / seat (mm)"
    )
    seat_width_mm: float = Field(default=480.0, description="Platform / seat pan width X (mm)")
    seat_depth_mm: float = Field(default=460.0, description="Platform / seat pan depth Y (mm)")
    seat_thickness_mm: float = Field(default=22.0, description="Top pan thickness (mm)")

    # Upper supports / arms
    armrest_height_above_seat_mm: float = Field(
        default=210.0, description="Upper arm/rail height above platform (mm)"
    )
    armrest_length_mm: float = Field(
        default=320.0, description="Length of arm pad along depth (mm)"
    )
    armrest_width_mm: float = Field(default=45.0, description="Width of arm pad (mm)")
    # Forward cantilever overhang: pad leading edge measured forward from the front
    # post axis. This is the SOURCE OF TRUTH -- armrest_pad_position() derives the
    # pad centre from it, so CAD and the frame solver can never disagree.
    #
    # Keeping the pad where it sits and moving the post forward (rather than
    # shortening the pad) holds the armrest length at the ergonomic 320 mm while
    # cutting the cantilever that drove the post base moment.
    armrest_overhang_front_mm: float = Field(
        default=60.0, description="Forward cantilever overhang past front post axis (mm)"
    )
    armrest_front_post_y_mm: float = Field(
        default=110.0, description="Front post fore/aft position from seat datum (mm)"
    )
    armrest_rear_post_y_over_depth: float = Field(
        default=-1.0 / 3.0, description="Rear post position as a fraction of seat depth (mm/mm)"
    )
    armrest_has_diagonal_brace: bool = Field(
        default=True, description="Whether a diagonal brace triangulates the two posts"
    )
    armrest_bracket_thickness_mm: float = Field(
        default=12.0, description="Arm mounting bracket plate thickness (mm)"
    )
    armrest_bracket_height_mm: float = Field(
        default=11.0, description="Arm mounting bracket plate height (mm)"
    )

    # Backrest / vertical extension
    backrest_height_above_seat_mm: float = Field(
        default=420.0, description="Backrest height above platform (mm)"
    )
    backrest_angle_deg: float = Field(
        default=98.0, description="Recline angle from horizontal (deg)"
    )

    # Topology & Member Configuration
    topology_type: str = Field(default="chair", description="'chair', 'stool', 'table', 'bench'")
    num_legs: int = Field(default=4, description="Number of support legs / columns (e.g. 3, 4, 6)")
    has_arms: bool = Field(default=True, description="Whether armrests/side rails are included")
    has_backrest: bool = Field(default=True, description="Whether a backrest is included")
    has_seat_plate: bool = Field(
        default=True, description="Whether top platform/seat pan is included"
    )

    # Columns / Legs & Bracing
    leg_splay_angle_deg: float = Field(
        default=3.5, description="Outward splay angle of columns for tipping stability (deg)"
    )
    stretcher_height_mm: float = Field(
        default=150.0, description="Height of lower cross bracing stretchers from floor (mm)"
    )
    has_stretchers: bool = Field(
        default=True, description="Whether lower cross-braces/stretchers are present"
    )

    # Member Profiles
    leg_profile: TubeProfile = Field(
        default_factory=lambda: TubeProfile(
            profile_type="round_tube", outer_dimension_mm=28.0, wall_thickness_mm=2.0
        )
    )
    frame_profile: TubeProfile = Field(
        default_factory=lambda: TubeProfile(
            profile_type="square_tube", outer_dimension_mm=25.0, wall_thickness_mm=2.0
        )
    )
    arm_profile: TubeProfile = Field(
        default_factory=lambda: TubeProfile(
            profile_type="round_tube", outer_dimension_mm=22.0, wall_thickness_mm=1.8
        )
    )
    stretcher_profile: TubeProfile = Field(
        default_factory=lambda: TubeProfile(
            profile_type="round_tube", outer_dimension_mm=19.0, wall_thickness_mm=1.5
        )
    )


class FrameLoads(BaseModel):
    """External applied loads for structural frame assemblies."""

    seat_vertical_load_n: float = Field(
        default=1300.0, description="Primary vertical downward load (N)"
    )
    seat_load_center_x_mm: float = Field(
        default=0.0, description="Lateral offset of load center from midpoint (mm)"
    )
    seat_load_center_y_mm: float = Field(
        default=-25.0, description="Fore/aft offset of load center (mm)"
    )

    left_arm_vertical_n: float = Field(
        default=450.0, description="Left vertical downward force (N)"
    )
    left_arm_lateral_n: float = Field(default=-150.0, description="Left outward lateral force (N)")
    left_arm_foreaft_n: float = Field(default=0.0, description="Left fore/aft thrust (N)")
    left_arm_load_y_mm: float = Field(
        default=0.0, description="Fore/aft position of the left arm load on the pad (mm)"
    )

    right_arm_vertical_n: float = Field(
        default=450.0, description="Right vertical downward force (N)"
    )
    right_arm_lateral_n: float = Field(default=150.0, description="Right outward lateral force (N)")
    right_arm_foreaft_n: float = Field(default=0.0, description="Right fore/aft thrust (N)")
    right_arm_load_y_mm: float = Field(
        default=0.0, description="Fore/aft position of the right arm load on the pad (mm)"
    )

    backrest_force_n: float = Field(default=300.0, description="Horizontal thrust on backrest (N)")


class FrameDesignModel(BaseModel):
    """Complete engineering definition of a 3D structural frame assembly."""

    name: str = "Structural Frame Assembly"
    geometry: FrameGeometry = Field(default_factory=FrameGeometry)
    loads: FrameLoads = Field(default_factory=FrameLoads)
    material: StructuralMaterial = Field(default_factory=lambda: STRUCTURAL_MATERIALS["STEEL_1018"])


class ArmrestGeometry(BaseModel):
    """
    Fully-resolved armrest sub-assembly layout, in mm.

    Every downstream consumer (CAD primitives, OpenSCAD, STL, the frame solver
    and the drawings) must read positions from here rather than re-deriving them
    from the raw ``FrameGeometry`` fields, so the drawn part and the analysed
    part cannot drift apart.
    """

    post_x_mm: float = Field(description="Signed X of the post axis (negative = left arm)")
    bracket_len_mm: float = Field(description="Span from seat-rail outer face to post axis")
    bracket_x_mm: float = Field(description="Signed X of the bracket centroid")
    bracket_thick_mm: float = Field(description="Bracket plate thickness")
    bracket_height_mm: float = Field(description="Bracket plate height")

    front_post_y_mm: float = Field(description="Y of the front post axis")
    rear_post_y_mm: float = Field(description="Y of the rear post axis")
    post_span_mm: float = Field(description="Front-to-rear post spacing")
    post_radius_mm: float = Field(description="Post tube outer radius")
    post_base_z_mm: float = Field(description="Z of the post foot, at the seat top face")
    post_top_z_mm: float = Field(description="Z of the post head, at the pad underside")

    pad_center_y_mm: float = Field(description="Y of the pad centroid")
    pad_front_y_mm: float = Field(description="Y of the pad leading edge")
    pad_rear_y_mm: float = Field(description="Y of the pad trailing edge")
    pad_width_mm: float = Field(description="Pad width across X")
    pad_length_mm: float = Field(description="Pad length along Y")
    pad_thickness_mm: float = Field(description="Pad thickness")
    pad_center_z_mm: float = Field(description="Z of the pad centroid")
    pad_top_z_mm: float = Field(description="Z of the pad top face")
    pad_underside_z_mm: float = Field(
        description="Z of the pad underside, where it lands on the posts"
    )

    # The cantilever that actually exists in the geometry, derived rather than
    # assumed. This is what the solver must use for the post base moment.
    cantilever_front_mm: float = Field(
        description="Pad leading edge forward of the front post axis"
    )
    cantilever_rear_mm: float = Field(description="Pad trailing edge aft of the rear post axis")

    diagonal_brace: bool = Field(description="Whether the posts are triangulated")

    def post_reaction_fractions(self, load_y_mm: float) -> tuple[float, float]:
        """
        Lever-rule share of a load at ``load_y_mm`` carried by (front, rear).

        Returns fractions summing to 1.0. Clamped so a load beyond either post
        cannot produce a negative (hold-down) reaction from a simple bearing
        seat.
        """
        span = self.post_span_mm
        if span <= 1e-9:
            return 0.5, 0.5
        front = (load_y_mm - self.rear_post_y_mm) / span
        front = min(1.0, max(0.0, front))
        return front, 1.0 - front


def resolve_armrest(
    geom: FrameGeometry,
    side: float = -1.0,
    arm_tube_r: float = 11.0,
    pad_thickness_mm: float = 18.0,
) -> ArmrestGeometry:
    """
    Resolve the armrest layout for one side from the raw design parameters.

    The pad is positioned *from* ``armrest_overhang_front_mm``, not the reverse,
    which is what makes the drawn overhang and the analysed overhang identical.
    """
    w, d, h = geom.seat_width_mm, geom.seat_depth_mm, geom.seat_height_mm

    post_x = side * (w / 2.0 + 25.0)
    bracket_len = abs(post_x) - w / 2.0
    bracket_x = side * (w / 2.0 + bracket_len / 2.0)

    front_y = geom.armrest_front_post_y_mm
    rear_y = geom.armrest_rear_post_y_over_depth * d
    span = front_y - rear_y

    pad_front = front_y + geom.armrest_overhang_front_mm
    pad_center = pad_front - geom.armrest_length_mm / 2.0

    return ArmrestGeometry(
        post_x_mm=post_x,
        bracket_len_mm=bracket_len,
        bracket_x_mm=bracket_x,
        bracket_thick_mm=geom.armrest_bracket_thickness_mm,
        bracket_height_mm=geom.armrest_bracket_height_mm,
        front_post_y_mm=front_y,
        rear_post_y_mm=rear_y,
        post_span_mm=span,
        post_radius_mm=arm_tube_r,
        post_base_z_mm=h,
        post_top_z_mm=h + geom.armrest_height_above_seat_mm,
        pad_center_y_mm=pad_center,
        pad_front_y_mm=pad_front,
        pad_rear_y_mm=pad_center - geom.armrest_length_mm / 2.0,
        pad_width_mm=geom.armrest_width_mm,
        pad_length_mm=geom.armrest_length_mm,
        pad_thickness_mm=pad_thickness_mm,
        pad_center_z_mm=h + geom.armrest_height_above_seat_mm + pad_thickness_mm / 2.0,
        pad_top_z_mm=h + geom.armrest_height_above_seat_mm + pad_thickness_mm,
        pad_underside_z_mm=h + geom.armrest_height_above_seat_mm,
        cantilever_front_mm=pad_front - front_y,
        cantilever_rear_mm=pad_center - geom.armrest_length_mm / 2.0 - rear_y,
        diagonal_brace=geom.armrest_has_diagonal_brace,
    )


# Aliases for backwards compatibility
ChairGeometry = FrameGeometry
ChairLoads = FrameLoads
ChairDesignModel = FrameDesignModel
ChairMaterial = StructuralMaterial
CHAIR_MATERIALS = STRUCTURAL_MATERIALS
