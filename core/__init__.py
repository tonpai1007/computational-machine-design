"""
MDIE Core Package
"""

from core.models import (
    DistributedLoad,
    EngineeringAssumption,
    EngineeringConstraints,
    EngineeringModel,
    KeywaySpec,
    PointLoad,
    SectionStress,
    ShaftSegment,
    SolverResult,
    Support,
    SupportReaction,
    TorqueLoad,
)
from core.units import Units
from core.vectors import Vector3D

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
