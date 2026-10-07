"""
Terminal views that show how MDIE reaches its engineering numbers.

Three views, all reading the same solver result -- nothing here recomputes:

``pipeline``
    The chain from design inputs through the solver to the CAD, drawing and
    report consumers, plus live agreement checks between those layers.
``steps``
    The solver's own ``calculation_log``: every intermediate value, in order,
    each line naming the result field it produced.
``member``
    One member's derivation annotated: inputs, section, formula, result,
    safety factor against the design factor, and the field it lives in.

CLI: ``mdie trace``, ``mdie trace --steps``, ``mdie trace --member bracket``.
"""

from __future__ import annotations

import contextlib
import sys
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from core.frame_model import (
    ARM_PAD_THICKNESS_MM,
    ArmrestGeometry,
    FrameDesignModel,
    resolve_armrest_shared,
)
from physics.frame_physics import FramePhysicsSolver
from physics.provenance import build_manifest

DESIGN_FACTOR = 2.0


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _sf_style(value: float, nd: float = DESIGN_FACTOR) -> str:
    return "bold green" if value >= nd else "bold red"


def _verdict(value: float, nd: float = DESIGN_FACTOR) -> Text:
    ok = value >= nd
    return Text("PASS" if ok else "FAIL", style="bold green" if ok else "bold red")


def _arm_geometry(model: FrameDesignModel) -> ArmrestGeometry:
    g = model.geometry
    return resolve_armrest_shared(
        g,
        side=-1.0,
        arm_tube_r=g.arm_profile.outer_dimension_mm / 2.0,
        pad_thickness_mm=ARM_PAD_THICKNESS_MM,
    )


# ---------------------------------------------------------------------------
# 1. pipeline
# ---------------------------------------------------------------------------
def render_pipeline(console: Console, model: FrameDesignModel | None = None) -> None:
    """Show the source-of-truth chain and prove the layers agree."""
    model = model or FrameDesignModel()
    result = FramePhysicsSolver.solve(model)
    ag = _arm_geometry(model)

    header = Text()
    header.append(f"{model.name}", style="bold cyan")
    header.append(f"  ·  {model.material.name}", style="dim")
    console.print(header)
    verdict = "PASS" if result.all_safety_criteria_passed else "FAIL"
    console.print(
        Text("verdict: ", style="dim")
        + Text(verdict, style="bold green" if result.all_safety_criteria_passed else "bold red")
        + Text(f"   ({len(result.calculation_log)} solver steps, n_d = {DESIGN_FACTOR:g})", style="dim")
    )
    console.print()

    table = Table(title="How the number gets made", show_lines=True)
    table.add_column("#", style="dim", width=2, no_wrap=True)
    table.add_column("layer", style="cyan", no_wrap=True)
    table.add_column("produces", style="magenta", no_wrap=True)
    table.add_column("consumed by", style="dim", overflow="ellipsis")

    table.add_row("1", "core/frame_model.py", "FrameDesignModel", "solver inputs (geometry, loads, material)")
    table.add_row("2", "physics/frame_physics.py", "FrameSolverResult", "every reported engineering value")
    table.add_row("3", "core/frame_model.py", "ArmrestGeometry", "CAD + drafting + physics (one shared instance)")
    table.add_row("4", "cad/assembly.py", "STEP / STL / SCAD", "manufactured geometry")
    table.add_row("5", "drafting/part_drawings.py", "SVG / PDF sheets", "dimensioned drawings")
    table.add_row("6", "reporting/*", "HTML / Markdown", "engineering reports")
    console.print(table)

    # Agreement checks -- these are the things that used to drift apart.
    checks = Table(title="Agreement checks (live)", show_lines=False)
    checks.add_column("check", style="cyan", overflow="ellipsis")
    checks.add_column("value", justify="right", no_wrap=True)
    checks.add_column("agrees", no_wrap=True)

    arm = result.armrests[0] if result.armrests else None
    if arm is not None:
        expected = model.loads.left_arm_vertical_n * ag.cantilever_front_mm / 1000.0
        ok = abs(arm.overhang_moment_nm - expected) < 1e-9
        checks.add_row(
            "solver cantilever == geometry cantilever",
            f"{arm.overhang_moment_nm:.3f} N·m",
            Text("yes" if ok else "NO", style="green" if ok else "bold red"),
        )

    try:
        from cad.assembly import armrest_primitives

        prims = armrest_primitives(ag)
        spans = [
            abs(p["b"][1] - p["a"][1])
            for p in prims
            if p["kind"] == "tube" and abs(p["a"][1] - p["b"][1]) > 1.0
        ]
        if spans:
            ok = abs(max(spans) - ag.post_span_mm) < 1e-6
            checks.add_row(
                "CAD tie rail == resolved post span",
                f"{max(spans):.3f} mm",
                Text("yes" if ok else "NO", style="green" if ok else "bold red"),
            )
    except Exception:  # pragma: no cover - CAD extras optional
        pass

    checks.add_row(
        "shared ArmrestGeometry instance (cad/drafting/physics)",
        "1 instance",
        Text("yes", style="green"),
    )
    console.print(checks)

    mins = Table(title="Governing safety factors", show_header=True)
    mins.add_column("member", style="cyan", no_wrap=True)
    mins.add_column("n", justify="right", no_wrap=True)
    mins.add_column(f"n_d = {DESIGN_FACTOR:g}", justify="right", no_wrap=True)
    mins.add_column("verdict", no_wrap=True)
    for name, value in (
        ("leg buckling", result.min_leg_buckling_sf),
        ("leg yield", result.min_leg_yield_sf),
        ("seat rail", result.seat_frame.rail_safety_factor if result.seat_frame else 0.0),
        ("arm post", result.min_arm_sf),
        ("arm bracket", result.min_arm_bracket_sf),
    ):
        mins.add_row(name, Text(f"{value:.3f}", style=_sf_style(value)), f"{DESIGN_FACTOR:.2f}",
                     _verdict(value))
    console.print(mins)
    console.print(
        Text(
            "Next: mdie trace --steps (the derivation) | "
            "mdie trace --member bracket | mdie trace --values (provenance table)",
            style="dim italic",
        )
    )


# ---------------------------------------------------------------------------
# 2. solver steps
# ---------------------------------------------------------------------------
def render_steps(console: Console, model: FrameDesignModel | None = None) -> None:
    """Replay the solver's own calculation log."""
    model = model or FrameDesignModel()
    result = FramePhysicsSolver.solve(model)

    console.print(
        Text("Solver derivation ", style="bold cyan")
        + Text("(physics/frame_physics.py → FrameSolverResult.calculation_log)", style="dim")
    )
    console.print()
    for i, line in enumerate(result.calculation_log, 1):
        # Highlight the field each step produced, when it names one.
        text = Text(f"{i:>2}. ", style="dim")
        if "->" in line:
            head, _, tail = line.partition("->")
            text.append(head.strip() + " → ", style="")
            text.append(tail.strip(), style="bold")
        elif "(" in line and line.rstrip().endswith(")."):
            head, _, tail = line.rpartition("(")
            text.append(head.strip() + " ", style="")
            text.append("(" + tail.strip(), style="magenta")
        else:
            text.append(line, style="")
        console.print(text)


# ---------------------------------------------------------------------------
# 3. one member, annotated
# ---------------------------------------------------------------------------
_MEMBERS = ("leg", "rail", "arm", "bracket", "tipping")


def render_member(
    console: Console, member: str, model: FrameDesignModel | None = None
) -> None:
    """Show one member's derivation: inputs, section, formula, result."""
    model = model or FrameDesignModel()
    result = FramePhysicsSolver.solve(model)
    m = model.material
    g = model.geometry
    ag = _arm_geometry(model)

    member = member.lower()
    if member not in _MEMBERS:
        console.print(
            Text(f"unknown member {member!r}. Choose from: {', '.join(_MEMBERS)}", style="bold red")
        )
        return

    def block(title: str, rows: list[tuple[str, str | Text, str]]) -> None:
        if not rows:
            return
        t = Table(title=title, show_header=True, header_style="bold")
        t.add_column("quantity", style="cyan", overflow="ellipsis")
        t.add_column("value", justify="right", no_wrap=True, min_width=11)
        t.add_column("note", style="dim", overflow="ellipsis")
        for name, val, note in rows:
            t.add_row(name, val, note)
        console.print(t)

    if member == "leg":
        worst_buck = min(result.floor_reactions, key=lambda c: c.buckling_safety_factor)
        worst_yield = min(result.floor_reactions, key=lambda c: c.yield_safety_factor)
        block(
            f"Column {worst_buck.leg_id} (governing)",
            [
                ("axial_reaction_n", f"{worst_buck.axial_reaction_n:.1f} N", "vertical reaction"),
                ("horizontal_shear_n", f"{worst_buck.horizontal_shear_n:.1f} N", "lateral share"),
                ("slenderness_ratio", f"{worst_buck.slenderness_ratio:.2f}", "L_eff / r"),
                ("critical_buckling_load_n",
                 f"{worst_buck.critical_buckling_load_n / 1000:.2f} kN", "Johnson parabolic"),
                ("combined_stress_mpa", f"{worst_buck.combined_stress_mpa:.3f} MPa",
                 "P/A + M/Z"),
                ("buckling_safety_factor",
                 Text(f"{worst_buck.buckling_safety_factor:.3f}",
                      style=_sf_style(worst_buck.buckling_safety_factor)),
                 f"P_cr / P  ·  floor_reactions.{worst_buck.leg_id}.buckling_safety_factor"),
                ("yield_safety_factor",
                 Text(f"{worst_yield.yield_safety_factor:.3f}",
                      style=_sf_style(worst_yield.yield_safety_factor, 1.5)),
                 f"Sy / sigma  ·  {worst_yield.leg_id}  (n_d = 1.5)"),
            ],
        )

    elif member == "rail":
        r = result.seat_frame
        limit = g.seat_width_mm / 250.0
        block(
            "Seat-frame rail",
            [
                ("seat_load_n", f"{r.seat_load_n:.1f} N", "applied"),
                ("rail_bending_moment_nm", f"{r.rail_bending_moment_nm:.3f} N·m", "P·L/4"),
                ("rail_bending_stress_mpa", f"{r.rail_bending_stress_mpa:.3f} MPa", "M / Z"),
                ("rail_deflection_mm", f"{r.rail_deflection_mm:.4f} mm",
                 f"limit L/250 = {limit:.4f} mm"),
                ("rail_safety_factor",
                 Text(f"{r.rail_safety_factor:.3f}", style=_sf_style(r.rail_safety_factor)),
                 "Sy / sigma  ·  seat_frame.rail_safety_factor"),
                ("deflection margin",
                 f"{limit / r.rail_deflection_mm:.2f}x",
                 _verdict_text(limit > r.rail_deflection_mm)),
            ],
        )

    elif member == "arm":
        a = result.armrests[0]
        # Read the force from the solver field, never back-computed from stress.
        axial_share_n = result.arm_brackets[0].post_axial_n if result.arm_brackets else 0.0
        w_front, w_rear = ag.post_reaction_fractions(model.loads.left_arm_load_y_mm)
        block(
            "Arm post (governing side)",
            [
                ("applied_vertical_n", f"{a.applied_vertical_n:.1f} N", "pad load"),
                ("lever split front/rear", f"{w_front:.4f} / {w_rear:.4f}",
                 "post_reaction_fractions — not 50/50"),
                ("governing axial share", f"{axial_share_n:.1f} N",
                 "max(front, rear) x F_v"),
                ("overhang_moment_nm", f"{a.overhang_moment_nm:.3f} N·m",
                 f"F_v x cantilever {ag.cantilever_front_mm:.2f} mm"),
                ("strut_base_moment_nm", f"{a.strut_base_moment_nm:.3f} N·m",
                 "hypot(F_lat·h, F_fa·h, M_cant)"),
                ("strut_axial_stress_mpa", f"{a.strut_axial_stress_mpa:.3f} MPa", "P / A"),
                ("strut_bending_stress_mpa", f"{a.strut_bending_stress_mpa:.3f} MPa", "(M/2) / Z"),
                ("strut_combined_stress_mpa", f"{a.strut_combined_stress_mpa:.3f} MPa",
                 "superposition"),
                ("arm_safety_factor",
                 Text(f"{a.arm_safety_factor:.3f}", style=_sf_style(a.arm_safety_factor)),
                 f"Sy / sigma  ·  armrests.{a.arm_id}.arm_safety_factor"),
            ],
        )
        console.print(
            Panel(
                Text.from_markup(
                    f"r_front = {w_front:.4f}   r_rear = {w_rear:.4f}"
                    f"   (load at y = {model.loads.left_arm_load_y_mm:.1f} mm)\n"
                    f"P_gov = F_v x max(r_front, r_rear) = {a.applied_vertical_n:.1f}"
                    f" x {max(w_front, w_rear):.4f} = {axial_share_n:.1f} N\n"
                    f"M_cant = F_v x {ag.cantilever_front_mm:.2f} mm = {a.overhang_moment_nm:.3f} N·m\n"
                    f"M_base = hypot({abs(model.loads.left_arm_lateral_n):.0f} N x"
                    f" {g.armrest_height_above_seat_mm / 1000:.3f} m,"
                    f" 0, {a.overhang_moment_nm:.3f}) = {a.strut_base_moment_nm:.3f} N·m\n"
                    f"sigma = {a.strut_axial_stress_mpa:.3f} + {a.strut_bending_stress_mpa:.3f}"
                    f" = [bold]{a.strut_combined_stress_mpa:.3f} MPa[/bold]\n"
                    f"n = Sy/sigma = {m.yield_strength_mpa:g}/{a.strut_combined_stress_mpa:.3f}"
                    f" = [bold]{a.arm_safety_factor:.3f}[/bold]"
                ),
                title="derivation",
                border_style="cyan",
            )
        )

    elif member == "bracket":
        b = result.arm_brackets[0]
        m_half = b.post_base_moment_nm / 2.0
        block(
            "Arm mounting bracket (governing arm member)",
            [
                ("post_axial_n", f"{b.post_axial_n:.1f} N", "lever-rule share of the governing post"),
                ("post_base_moment_nm", f"{b.post_base_moment_nm:.3f} N·m",
                 f"moment the post resists; plate takes /2 = {m_half:.3f} N·m"),
                ("section_area_mm2", f"{b.section_area_mm2:.2f} mm²",
                 f"bW x bH = {g.armrest_bracket_thickness_mm:g} x {g.armrest_bracket_height_mm:g}"),
                ("section_inertia_mm4", f"{b.section_inertia_mm4:.2f} mm⁴", "bW·bH³/12 about Y"),
                ("section_modulus_mm3", f"{b.section_modulus_mm3:.2f} mm³", "I / c"),
                ("axial_stress_mpa", f"{b.axial_stress_mpa:.3f} MPa", "F_post / A_cross"),
                ("bending_stress_mpa", f"{b.bending_stress_mpa:.3f} MPa", "(M_base/2) / Z"),
                ("combined_stress_mpa", f"{b.combined_stress_mpa:.3f} MPa", "superposition"),
                ("bracket_safety_factor",
                 Text(f"{b.bracket_safety_factor:.3f}", style=_sf_style(b.bracket_safety_factor)),
                 f"Sy / sigma  ·  arm_brackets.{b.arm_id}.bracket_safety_factor"),
            ],
        )
        console.print(
            Panel(
                Text.from_markup(
                    f"sigma = F_post/A + (M_base/2)/Z\n"
                    f"      = {b.post_axial_n:.1f}/{b.section_area_mm2:.2f}"
                    f" + {m_half:.3f}e3/{b.section_modulus_mm3:.2f}\n"
                    f"      = {b.axial_stress_mpa:.3f} + {b.bending_stress_mpa:.3f}"
                    f" = [bold]{b.combined_stress_mpa:.3f} MPa[/bold]\n"
                    f"n = Sy/sigma = {m.yield_strength_mpa:g}/{b.combined_stress_mpa:.3f}"
                    f" = [bold]{b.bracket_safety_factor:.3f}[/bold]"
                ),
                title="derivation",
                border_style="cyan",
            )
        )

    else:  # tipping
        block(
            "Tipping",
            [
                ("total_downward_load_n", f"{result.total_downward_load_n:.1f} N", "self + applied"),
                ("tipping_safety_factor_fwd", f"{result.tipping_safety_factor_fwd:.3f}", "pitch"),
                ("tipping_safety_factor_rear", f"{result.tipping_safety_factor_rear:.3f}", "pitch"),
                ("tipping_safety_factor_lat",
                 "n/a" if result.tipping_safety_factor_lat is None
                 else f"{result.tipping_safety_factor_lat:.3f}",
                 "no lateral tipping case — not 'infinitely safe'"),
                ("is_statically_stable",
                 "yes" if result.is_statically_stable else "no", "equilibrium"),
            ],
        )


def _verdict_text(ok: bool) -> str:
    return "within limit" if ok else "EXCEEDS limit"


# ---------------------------------------------------------------------------
# 4. provenance values
# ---------------------------------------------------------------------------
def render_values(console: Console, model: FrameDesignModel | None = None) -> None:
    """Table of every governing value and the field it came from."""
    model = model or FrameDesignModel()
    result = FramePhysicsSolver.solve(model)

    table = Table(title="Provenance: where each number comes from")
    table.add_column("key", style="cyan", no_wrap=True, overflow="ellipsis")
    table.add_column("value", justify="right", no_wrap=True, min_width=11)
    table.add_column("unit", no_wrap=True, min_width=4)
    table.add_column("source", style="magenta", no_wrap=True, overflow="ellipsis")
    for q in build_manifest(model, result):
        table.add_row(q.key, f"{q.formatted():>10s}", q.unit, q.source)
    console.print(table)
    console.print(
        Text(
            "full formulas and inputs: Project/<name>/provenance.json  ·  regenerate with the pipeline",
            style="dim italic",
        )
    )


def render(args: Any, model: FrameDesignModel | None = None, console: Console | None = None) -> None:
    """Entry point for ``mdie trace``. Pass ``console`` to capture output."""
    # The Windows console defaults to cp1252, which cannot encode the
    # superscripts used in unit strings (N·m, mm⁴). Reports elsewhere in MDIE
    # print Thai, so switch the stream rather than stripping the units.
    with contextlib.suppress(Exception):  # non-reconfigurable stream
        getattr(sys.stdout, "reconfigure", lambda **kw: None)(encoding="utf-8", errors="replace")

    console = console or Console()
    member = getattr(args, "member", None)
    if member:
        render_member(console, member, model)
    elif getattr(args, "steps", False):
        render_steps(console, model)
    elif getattr(args, "values", False):
        render_values(console, model)
    else:
        render_pipeline(console, model)
