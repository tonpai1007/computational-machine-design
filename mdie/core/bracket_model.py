"""
MDIE Motor Mounting Bracket & Plate Data Model
Supports L-brackets, flat faceplates, and foot-mounting brackets with bolt hole patterns.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from mdie.core.frame_model import StructuralMaterial, STRUCTURAL_MATERIALS


class BoltHolePattern(BaseModel):
    """Specification of bolt mounting patterns on a plate or flange."""
    num_holes: int = Field(default=4, description="Number of mounting bolt holes")
    hole_diameter_mm: float = Field(default=8.5, description="Hole diameter in mm (e.g. 8.5 mm for M8 clearance)")
    pattern_type: str = Field(default="circle", description="'circle' (BCD) or 'rectangular'")
    bolt_circle_diameter_mm: float = Field(default=75.0, description="Bolt Circle Diameter (BCD) in mm")
    spacing_x_mm: float = Field(default=60.0, description="Center-to-center spacing along X in mm")
    spacing_y_mm: float = Field(default=60.0, description="Center-to-center spacing along Y in mm")


class BracketGeometry(BaseModel):
    """Parametric dimensions for mounting brackets and plates."""
    bracket_type: str = Field(default="L_bracket", description="'L_bracket', 'flat_plate', 'U_bracket'")
    base_length_mm: float = Field(default=120.0, description="Base foot length along X (mm)")
    base_width_mm: float = Field(default=100.0, description="Base foot width along Y (mm)")
    thickness_mm: float = Field(default=6.0, description="Plate material thickness (mm)")
    upright_height_mm: float = Field(default=110.0, description="Vertical mounting flange height (mm)")
    motor_pilot_diameter_mm: float = Field(default=40.0, description="Central clearance bore for motor boss / shaft (mm)")
    bend_radius_mm: float = Field(default=6.0, description="Inside bend radius for sheet metal / forged angle (mm)")
    has_gussets: bool = Field(default=True, description="Whether reinforcing triangular gussets are attached")
    gusset_thickness_mm: float = Field(default=4.0, description="Thickness of triangular stiffener ribs (mm)")

    # Bolt patterns
    motor_bolt_pattern: BoltHolePattern = Field(default_factory=lambda: BoltHolePattern(num_holes=4, hole_diameter_mm=8.5, bolt_circle_diameter_mm=75.0))
    base_bolt_pattern: BoltHolePattern = Field(default_factory=lambda: BoltHolePattern(num_holes=4, hole_diameter_mm=9.0, pattern_type="rectangular", spacing_x_mm=85.0, spacing_y_mm=70.0))


class BracketLoads(BaseModel):
    """Mechanical operating loads applied to the bracket."""
    motor_mass_kg: float = Field(default=8.0, description="Supported motor mass (kg)")
    motor_torque_nm: float = Field(default=20.0, description="Motor dynamic reaction torque (N*m)")
    cantilever_arm_mm: float = Field(default=55.0, description="Distance from mounting flange to motor Center of Gravity (mm)")
    axial_thrust_n: float = Field(default=250.0, description="Axial push/pull thrust load (N)")


class BracketModel(BaseModel):
    """Complete engineering definition of a mounting bracket."""
    name: str = "Motor Mounting Bracket"
    geometry: BracketGeometry = Field(default_factory=BracketGeometry)
    loads: BracketLoads = Field(default_factory=BracketLoads)
    material: StructuralMaterial = Field(default_factory=lambda: STRUCTURAL_MATERIALS["STEEL_1018"])
