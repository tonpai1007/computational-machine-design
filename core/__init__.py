"""
MDIE Core Package
"""
from core.units import Units
from core.vectors import Vector3D
from core.models import (
    Support,
    PointLoad,
    DistributedLoad,
    TorqueLoad,
    KeywaySpec,
    ShaftSegment,
    EngineeringConstraints,
    EngineeringAssumption,
    EngineeringModel,
    SectionStress,
    SupportReaction,
    SolverResult,
)

__all__ = [
    "Units",
    "Vector3D",
    "Support",
    "PointLoad",
    "DistributedLoad",
    "TorqueLoad",
    "KeywaySpec",
    "ShaftSegment",
    "EngineeringConstraints",
    "EngineeringAssumption",
    "EngineeringModel",
    "SectionStress",
    "SupportReaction",
    "SolverResult",
]

__version__ = "0.2.0"
