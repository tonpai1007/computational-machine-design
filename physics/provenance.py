"""
Provenance manifest for frame designs.

Every engineering number that leaves the solver can be traced back to the
field it came from, the formula used, and the inputs. Reports, drawing sheets
and CAD all read the solver rather than re-deriving values, so this manifest
is the machine-checkable record of that chain:

    FrameDesignModel (inputs)
        -> FramePhysicsSolver.solve()  (physics/frame_physics.py)
        -> FrameSolverResult           (values + this manifest)
        -> CAD / drafting / reporting  (readers)

The traceability test in ``tests/test_provenance.py`` asserts each quantity
below is present in the generated artifacts. That is what stops a hand-typed
stale value from surviving a geometry change.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from core.frame_model import (
    ARM_PAD_THICKNESS_MM,
    FrameDesignModel,
    resolve_armrest_shared,
)
from physics.fatigue import MarinFactors
from physics.frame_physics import FramePhysicsSolver, FrameSolverResult


class GoverningQuantity(BaseModel):
    """One engineering conclusion, with where it came from."""

    key: str
    label: str
    value: float
    unit: str
    formula: str
    source: str  # dotted path into FrameSolverResult
    inputs: dict[str, Any] = Field(default_factory=dict)

    def formatted(self, dp: int = 3) -> str:
        return f"{self.value:.{dp}f}"


def _marin_endurance(model: FrameDesignModel, d_eff_mm: float) -> float:
    """Marin-corrected endurance limit, via the single physics implementation."""
    m = model.material
    ka = MarinFactors.surface_factor(m.ultimate_strength_mpa, "machined")
    kb = MarinFactors.size_factor(d_eff_mm / 1000.0)
    kc = MarinFactors.load_factor("bending")
    ke = MarinFactors.reliability_factor(0.90)
    return ka * kb * kc * 1.0 * ke * 1.0 * (0.5 * m.ultimate_strength_mpa)


def build_manifest(
    model: FrameDesignModel | None = None,
    result: FrameSolverResult | None = None,
) -> list[GoverningQuantity]:
    """Assemble the governing quantities for a frame design."""
    model = model or FrameDesignModel()
    if result is None:
        result = FramePhysicsSolver.solve(model)

    g = model.geometry
    m = model.material
    ag = resolve_armrest_shared(
        g,
        side=-1.0,
        arm_tube_r=g.arm_profile.outer_dimension_mm / 2.0,
        pad_thickness_mm=ARM_PAD_THICKNESS_MM,
    )

    out: list[GoverningQuantity] = [
        GoverningQuantity(
            key="arm.post_span",
            label="Arm post spacing (front to rear)",
            value=ag.post_span_mm,
            unit="mm",
            formula="front_post_y - rear_post_y",
            source="ArmrestGeometry.post_span_mm",
            inputs={
                "front_post_y_mm": ag.front_post_y_mm,
                "rear_post_y_mm": ag.rear_post_y_mm,
            },
        ),
        GoverningQuantity(
            key="arm.overhang_front",
            label="Arm pad forward cantilever",
            value=ag.cantilever_front_mm,
            unit="mm",
            formula="pad_front_y - front_post_y",
            source="ArmrestGeometry.cantilever_front_mm",
        ),
        GoverningQuantity(
            key="arm.total_downward_load",
            label="Total downward load",
            value=result.total_downward_load_n,
            unit="N",
            formula="self weight + applied loads",
            source="FrameSolverResult.total_downward",
        ),
    ]

    # Legs: the governing one is enough to pin the verdict.
    if result.floor_reactions:
        leg = min(result.floor_reactions, key=lambda c: c.buckling_safety_factor)
        out += [
            GoverningQuantity(
                key="leg.min_buckling_sf",
                label=f"Leg buckling safety factor (worst: {leg.leg_id})",
                value=leg.buckling_safety_factor,
                unit="-",
                formula="P_cr / P",
                source=f"floor_reactions.{leg.leg_id}.buckling_safety_factor",
                inputs={
                    "critical_buckling_load_n": leg.critical_buckling_load_n,
                    "axial_reaction_n": leg.axial_reaction_n,
                    "slenderness_ratio": leg.slenderness_ratio,
                },
            ),
            GoverningQuantity(
                key="leg.min_yield_sf",
                label=f"Leg yield safety factor (worst: {leg.leg_id})",
                value=leg.yield_safety_factor,
                unit="-",
                formula="S_y / sigma_combined",
                source=f"floor_reactions.{leg.leg_id}.yield_safety_factor",
                inputs={"combined_stress_mpa": leg.combined_stress_mpa},
            ),
        ]

    if result.seat_frame:
        out += [
            GoverningQuantity(
                key="rail.bending_stress",
                label="Seat-frame rail bending stress",
                value=result.seat_frame.rail_bending_stress_mpa,
                unit="MPa",
                formula="M / Z",
                source="seat_frame.rail_bending_stress",
            ),
            GoverningQuantity(
                key="rail.deflection",
                label="Seat-frame rail deflection",
                value=result.seat_frame.rail_deflection_mm,
                unit="mm",
                formula="5 w L^4 / (384 E I)",
                source="seat_frame.rail_deflection",
            ),
        ]

    for arm in result.armrests:
        out.append(
            GoverningQuantity(
                key=f"arm.{arm.arm_id}.combined_stress",
                label=f"Arm post combined stress ({arm.arm_id})",
                value=arm.strut_combined_stress_mpa,
                unit="MPa",
                formula="sigma_axial + sigma_bending",
                source=f"armrests.{arm.arm_id}.strut_combined_stress_mpa",
                inputs={
                    "axial_stress_mpa": arm.strut_axial_stress_mpa,
                    "bending_stress_mpa": arm.strut_bending_stress_mpa,
                },
            )
        )
        out.append(
            GoverningQuantity(
                key=f"arm.{arm.arm_id}.base_moment",
                label=f"Arm post base moment ({arm.arm_id})",
                value=arm.strut_base_moment_nm,
                unit="N.m",
                formula="hypot(Flat*h, Ffa*h, M_cant)",
                source=f"armrests.{arm.arm_id}.strut_base_moment_nm",
                inputs={"overhang_moment_nm": arm.overhang_moment_nm},
            )
        )

    for brk in result.arm_brackets:
        out.append(
            GoverningQuantity(
                key=f"bracket.{brk.arm_id}.combined_stress",
                label=f"Arm bracket combined stress ({brk.arm_id})",
                value=brk.combined_stress_mpa,
                unit="MPa",
                formula="F_post/A + (M_base/2)/Z",
                source=f"arm_brackets.{brk.arm_id}.combined_stress_mpa",
                inputs={
                    "post_axial_n": brk.post_axial_n,
                    "section_area_mm2": brk.section_area_mm2,
                    "section_modulus_mm3": brk.section_modulus_mm3,
                },
            )
        )
        out.append(
            GoverningQuantity(
                key=f"bracket.{brk.arm_id}.safety_factor",
                label=f"Arm bracket safety factor ({brk.arm_id})",
                value=brk.bracket_safety_factor,
                unit="-",
                formula="S_y / sigma_combined",
                source=f"arm_brackets.{brk.arm_id}.bracket_safety_factor",
            )
        )

    # Governing member drives the endurance check.
    gov = max(result.arm_brackets, key=lambda b: b.combined_stress_mpa, default=None)
    if gov is not None:
        out.append(
            GoverningQuantity(
                key="fatigue.endurance_limit",
                label="Marin-corrected endurance limit (bracket)",
                value=_marin_endurance(model, ag.bracket_len_mm),
                unit="MPa",
                formula="ka*kb*kc*kd*ke*kf*0.5*Sut",
                source="physics.fatigue.MarinFactors",
                inputs={"d_effective_mm": ag.bracket_len_mm, "S_ut_mpa": m.ultimate_strength_mpa},
            )
        )

    return out


def manifest_dict(
    model: FrameDesignModel | None = None,
    result: FrameSolverResult | None = None,
) -> dict[str, Any]:
    """Manifest as a JSON-serialisable dict, including the verdict."""
    model = model or FrameDesignModel()
    if result is None:
        result = FramePhysicsSolver.solve(model)
    return {
        "design": model.name,
        "material": model.material.name,
        "all_safety_criteria_passed": result.all_safety_criteria_passed,
        "min_safety_factors": {
            "leg_buckling": result.min_leg_buckling_sf,
            "leg_yield": result.min_leg_yield_sf,
            "arm_post": result.min_arm_sf,
            "arm_bracket": result.min_arm_bracket_sf,
        },
        "quantities": [q.model_dump() for q in build_manifest(model, result)],
    }


def write_manifest(outdir: str | Path, model: FrameDesignModel | None = None) -> Path:
    """Write ``provenance.json`` next to the generated artifacts."""
    import json

    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "provenance.json"
    path.write_text(
        json.dumps(manifest_dict(model), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return path
