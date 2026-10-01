"""
MDIE Structured Engineering Data Models
Defines the machine model, boundary conditions, loads, geometry, and solver output representations.
"""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, Field


class Support(BaseModel):
    """Support or bearing location along component length."""

    name: str = "Support"
    support_type: str = Field(
        default="pinned", description="Type of support: 'pinned', 'roller', 'fixed', 'bearing'"
    )
    position: float = Field(..., description="Position along length in meters (m)")
    allowable_slope_rad: float | None = Field(
        default=0.005,
        description="Maximum allowable angular misalignment (rad), typical for deep groove ball bearings: ~0.001 - 0.005 rad",
    )


class PointLoad(BaseModel):
    """Transverse or radial point load."""

    name: str = "PointLoad"
    position: float = Field(..., description="Position along length in meters (m)")
    magnitude: float = Field(
        ..., description="Force magnitude in Newtons (N), positive downward/transverse"
    )
    direction_deg: float = Field(
        default=90.0, description="Angle of load in degrees (90 = vertical downward)"
    )
    load_type: str = Field(default="static", description="'static', 'alternating', 'repeated'")


class DistributedLoad(BaseModel):
    """Continuous distributed load (e.g. self-weight, linear gear mesh)."""

    name: str = "DistributedLoad"
    start_pos: float = Field(..., description="Start position in meters (m)")
    end_pos: float = Field(..., description="End position in meters (m)")
    w_start: float = Field(..., description="Load intensity at start in N/m")
    w_end: float | None = Field(
        None, description="Load intensity at end in N/m (defaults to w_start for uniform)"
    )

    def get_w_end(self) -> float:
        return self.w_end if self.w_end is not None else self.w_start


class TorqueLoad(BaseModel):
    """Applied torque or power transfer point."""

    name: str = "Torque"
    position: float = Field(..., description="Position along shaft in meters (m)")
    magnitude: float = Field(
        ..., description="Torque in N*m. Positive = driving (input), negative = driven (output)"
    )
    is_alternating: bool = Field(default=False, description="Whether torque reverses or alternates")


class KeywaySpec(BaseModel):
    """Standard shaft keyway specification."""

    position: float = Field(..., description="Axial start position in meters (m)")
    length: float = Field(..., description="Keyway length in meters (m)")
    width: float = Field(..., description="Key width in meters (m)")
    depth: float = Field(..., description="Keyway cut depth into shaft in meters (m)")
    fillet_radius: float = Field(default=0.0005, description="Root fillet radius in meters (m)")
    standard: str = Field(default="DIN 6885", description="Standard e.g. DIN 6885 / ANSI")


class ShaftSegment(BaseModel):
    """Cylindrical or tubular segment of a stepped shaft or beam."""

    start_pos: float = Field(..., description="Start axial coordinate in meters (m)")
    end_pos: float = Field(..., description="End axial coordinate in meters (m)")
    outer_diameter: float = Field(..., description="Outer diameter in meters (m)")
    inner_diameter: float = Field(
        default=0.0, description="Inner bore diameter in meters (m), 0 for solid"
    )
    fillet_radius: float = Field(
        default=0.002, description="Transition fillet radius to next shoulder in meters (m)"
    )
    feature_type: str = Field(
        default="smooth",
        description="'smooth', 'bearing_seat', 'gear_mount', 'pulley_seat', 'threaded'",
    )
    surface_finish: str = Field(
        default="machined",
        description="'ground', 'machined', 'cold_drawn', 'hot_rolled', 'as_forged'",
    )
    keyway: KeywaySpec | None = None

    @property
    def length(self) -> float:
        return self.end_pos - self.start_pos

    @property
    def area(self) -> float:
        """Cross-sectional area A = pi/4 * (do^2 - di^2)."""
        return (math.pi / 4.0) * (self.outer_diameter**2 - self.inner_diameter**2)

    @property
    def second_moment_of_area(self) -> float:
        """Area moment of inertia I = pi/64 * (do^4 - di^4)."""
        return (math.pi / 64.0) * (self.outer_diameter**4 - self.inner_diameter**4)

    @property
    def polar_moment_of_inertia(self) -> float:
        """Polar moment of inertia J = pi/32 * (do^4 - di^4)."""
        return (math.pi / 32.0) * (self.outer_diameter**4 - self.inner_diameter**4)

    @property
    def section_modulus(self) -> float:
        """Elastic section modulus Z = I / (do/2)."""
        c = self.outer_diameter / 2.0
        return self.second_moment_of_area / c if c > 0 else 0.0

    @property
    def torsional_section_modulus(self) -> float:
        """Torsional section modulus Zt = J / (do/2)."""
        c = self.outer_diameter / 2.0
        return self.polar_moment_of_inertia / c if c > 0 else 0.0


class EngineeringConstraints(BaseModel):
    """Target performance constraints and safety criteria."""

    min_yield_safety_factor: float = Field(
        default=2.0, description="Minimum allowable SF against static yield"
    )
    min_fatigue_safety_factor: float = Field(
        default=1.5, description="Minimum allowable SF against fatigue endurance"
    )
    max_deflection_mm: float = Field(
        default=1.0, description="Maximum allowable deflection along span in mm"
    )
    max_slope_rad: float = Field(
        default=0.0015, description="Maximum allowable slope at bearings in radians"
    )
    target_life_cycles: float = Field(
        default=1e7, description="Required fatigue operational cycles (e.g. 10M)"
    )
    max_mass_kg: float | None = Field(None, description="Maximum allowable total mass in kg")


class EngineeringAssumption(BaseModel):
    """Explicit record of an engineering assumption made by user or AI."""

    parameter: str
    value: Any
    unit: str
    source: str = Field(
        ..., description="'user_explicit', 'ai_inference', 'standard_default', 'catalog'"
    )
    status: str = Field(
        ..., description="'CONFIRMED', 'ASSUMED', 'REQUIRES_CONFIRMATION', 'MISSING'"
    )
    notes: str | None = None


class EngineeringModel(BaseModel):
    """Complete machine engineering model."""

    name: str = "Shaft Assembly"
    component_type: str = Field(
        default="shaft", description="'shaft', 'cantilever_beam', 'simply_supported_beam'"
    )
    total_length: float = Field(..., description="Total length in meters (m)")
    power_watts: float | None = Field(None, description="Input transmitted power in Watts (W)")
    speed_rpm: float | None = Field(None, description="Rotational speed in RPM")
    torque_nm: float | None = Field(
        None, description="Explicit transmitted torque in N*m if power/speed not given"
    )
    material_id: str = Field(
        default="AISI_1045_CD", description="Material identifier from materials DB"
    )
    segments: list[ShaftSegment] = Field(default_factory=list)
    supports: list[Support] = Field(default_factory=list)
    point_loads: list[PointLoad] = Field(default_factory=list)
    distributed_loads: list[DistributedLoad] = Field(default_factory=list)
    torques: list[TorqueLoad] = Field(default_factory=list)
    constraints: EngineeringConstraints = Field(
        default_factory=lambda: EngineeringConstraints(max_mass_kg=None)
    )
    assumptions: list[EngineeringAssumption] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def calculate_nominal_torque(self) -> float:
        """Determine nominal torque from power and speed, or direct torque."""
        if self.torque_nm is not None and self.torque_nm > 0:
            return self.torque_nm
        if self.power_watts is not None and self.speed_rpm is not None and self.speed_rpm > 0:
            omega = self.speed_rpm * (2.0 * math.pi / 60.0)
            return self.power_watts / omega
        return 0.0


class SectionStress(BaseModel):
    """Stress state at a specific axial station."""

    x: float
    outer_diameter: float
    bending_moment: float
    bending_stress: float
    torque: float
    torsional_stress: float
    axial_force: float = 0.0
    axial_stress: float = 0.0
    von_mises_stress: float
    principal_stress_1: float
    principal_stress_2: float
    kt_bending: float = 1.0
    kt_torsion: float = 1.0
    effective_von_mises: float
    yield_safety_factor: float
    fatigue_safety_factor: float
    predicted_cycles: float


class SupportReaction(BaseModel):
    """Calculated reaction force at a support."""

    support_name: str
    position: float
    reaction_force_n: float
    reaction_moment_nm: float = 0.0


class SolverResult(BaseModel):
    """Complete physics engine deterministic calculation output."""

    model_name: str
    timestamp: str
    success: bool
    error_message: str | None = None

    # Equilibrium & Reactions
    reactions: list[SupportReaction] = Field(default_factory=list)
    applied_torque_nm: float = 0.0

    # Spatial discretized curves (x in m)
    x_stations: list[float] = Field(default_factory=list)
    shear_force: list[float] = Field(default_factory=list)  # N
    bending_moment: list[float] = Field(default_factory=list)  # N*m
    torque_distribution: list[float] = Field(default_factory=list)  # N*m
    slope_rad: list[float] = Field(default_factory=list)  # rad
    deflection_mm: list[float] = Field(default_factory=list)  # mm
    von_mises_stress_mpa: list[float] = Field(default_factory=list)  # MPa
    diameters_mm: list[float] = Field(default_factory=list)  # mm

    # Critical Section & Peak Values
    max_bending_moment_nm: float = 0.0
    max_bending_moment_x: float = 0.0
    max_shear_force_n: float = 0.0
    max_deflection_mm: float = 0.0
    max_deflection_x: float = 0.0
    max_slope_rad: float = 0.0
    max_von_mises_mpa: float = 0.0
    max_von_mises_x: float = 0.0

    # Critical Section Analysis
    critical_section: SectionStress | None = None

    # Material Verification
    material_name: str = ""
    yield_strength_mpa: float = 0.0
    ultimate_strength_mpa: float = 0.0
    endurance_limit_mpa: float = 0.0
    total_mass_kg: float = 0.0

    # Safety Factors
    min_yield_safety_factor: float = 0.0
    min_fatigue_safety_factor: float = 0.0
    fatigue_life_cycles: float = 1e9
    is_infinite_life: bool = False

    # Compliance against constraints
    yield_passed: bool = False
    fatigue_passed: bool = False
    deflection_passed: bool = False
    slope_passed: bool = False
    all_constraints_passed: bool = False

    # Standard Machine Components Integration
    bearings_selected: list[dict[str, Any]] = Field(default_factory=list)
    keyway_analysis: dict[str, Any] | None = None

    # OpenSCAD Script
    openscad_code: str = ""

    # Solver trace / equations log
    calculation_steps: list[str] = Field(default_factory=list)
