"""Command line interface.

Usage shapes
------------
``mdie "design a chair with 4 legs"``   free-form design prompt
``mdie chair | bracket | shaft``        canned designs
``mdie convert in.html --to pdf``       file conversion (see :mod:`convert`)
``mdie view chair --freecad``           open a project in a CAD viewer
``mdie drawings --pdf``                 regenerate chair drawing sheets
``mdie report chair --ai``              consolidate an engineering report
``mdie info``                           show detected tools and LLM providers
``mdie trace``                          how every engineering number is produced
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from ai.docgen_workflow import generate_docx_report
from cli.designers import (
    _handle_bracket,
    _handle_chair,
    _handle_generative,
    _handle_shaft,
    _handle_space_frame,
)
from cli.viewers import find_cad_tools, launch_cad_viewer

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

console = Console()

SUBCOMMANDS = {
    "design",
    "chair",
    "bracket",
    "shaft",
    "space_frame",
    "solve",
    "optimize",
    "view",
    "convert",
    "docx",
    "convert-docx",
    "word",
    "drawings",
    "report",
    "consolidate",
    "study",
    "info",
    "slides",
    "help",
    "trace",
    "menu",
    "interactive",
}

CANNED = {
    "chair": ("Design a chair with two arms and four splayed legs", "Project/chair"),
    "bracket": ("motor mounting bracket with 4 bolt holes, 10 kg, steel", "Project/bracket"),
    "shaft": ("Design a stepped transmission shaft 500 mm long, 40 mm diameter", "Project/shaft"),
    "space_frame": ("transmission tower 3D space frame 5 kN load", "Project/space_frame"),
}


def _report_unsupported(meta: dict[str, Any]) -> None:
    """Decline an out-of-scope request and list what MDIE can actually verify.

    MDIE only reports designs it has a deterministic solver for; declining is
    the honest response where synthesising would be a guess.
    """
    domain = meta.get("unsupported_domain", "this domain")
    console.print(
        Panel(
            f"[bold yellow]Unsupported domain:[/bold yellow] {domain}\n\n"
            "MDIE only verifies designs it has a deterministic solver for, so it "
            "declines this request rather than emitting a guess.\n\n"
            "[bold cyan]Supported design families:[/bold cyan]\n"
            '  1. Rotating shafts / power transmission  (e.g. "stepped shaft 500 mm, 10 kW")\n'
            '  2. Frames & furniture                     (e.g. "chair with 4 splayed legs")\n'
            '  3. 3D space frames & trusses              (e.g. "transmission tower, 5 kN")\n'
            '  4. Mounting brackets & flange plates      (e.g. "motor bracket, 4 bolt holes")\n'
            "  5. Power-transmission elements: gears, springs, bolted joints, lead/power screws\n\n"
            "[dim]Rephrase using one of the families above.[/dim]",
            title="[bold red]Out of Scope[/bold red]",
            border_style="yellow",
        )
    )


def process_prompt(prompt: str, output_dir: str | None = None, auto_open: bool = False) -> bool:
    """Classify a plain-English prompt and run the matching design pipeline."""
    prompt = _maybe_read_file_prompt(prompt)
    p_lower = prompt.lower().strip()
    if not p_lower:
        return False

    console.print(f"\n[bold cyan]>> Analyzing Prompt:[/bold cyan] [italic]{prompt}[/italic]")

    from ai.classifier import DomainClassifier
    from ai.parser import extract_from_prompt

    domain, meta = DomainClassifier.classify(prompt)

    # Extract structured parameters from the prompt
    params = extract_from_prompt(prompt)
    if params:
        meta["extracted_params"] = params

    if domain == "bracket":
        console.print(
            f"[bold cyan]>> Classified Domain:[/bold cyan] [bold green]Mounting Bracket & Flange Plate[/bold green] (confidence: {meta.get('confidence', 0.95):.0%})"
        )
        res = _handle_bracket(prompt, p_lower, output_dir, params)
        if res and auto_open:
            launch_cad_viewer(Path(output_dir or "Project/bracket"))
        return res

    if domain == "space_frame":
        console.print(
            f"[bold cyan]>> Classified Domain:[/bold cyan] [bold green]3D Space Frame & Truss[/bold green] (confidence: {meta.get('confidence', 0.95):.0%})"
        )
        res = _handle_space_frame(prompt, p_lower, output_dir, params)
        if res and auto_open:
            launch_cad_viewer(Path(output_dir or "Project/space_frame"))
        return res

    if domain == "frame":
        console.print(
            f"[bold cyan]>> Classified Domain:[/bold cyan] [bold green]Structural Frame & Furniture[/bold green] (confidence: {meta.get('confidence', 0.95):.0%})"
        )
        res = _handle_chair(prompt, p_lower, output_dir, params)
        if res and auto_open:
            launch_cad_viewer(Path(output_dir or "Project/chair"))
        return res

    if domain == "unsupported":
        from ai.generative_agent import GenerativeEngineeringAgent

        if GenerativeEngineeringAgent.is_specialized(prompt):
            console.print(
                "[bold cyan]>> Classified Domain:[/bold cyan] [bold green]Specialized Power-Transmission Element[/bold green]"
            )
            res = _handle_generative(prompt, p_lower, output_dir, params)
            if res and auto_open:
                slug = meta.get("slug", "generative_part")
                launch_cad_viewer(Path(output_dir or f"Project/{slug}"))
            return res
        # Truly out of scope: decline explicitly instead of synthesising a guess.
        _report_unsupported(meta)
        return False

    if (
        any(w in p_lower for w in ["shaft", "spindle", "rotor", "axle", "bearing seat"])
        or (domain == "shaft" and meta.get("confidence", 0.5) > 0.8)
    ) and not any(w in p_lower for w in ["bolt", "fastener", "spring", "gear", "screw"]):
        confidence = meta.get("confidence", 0.50)
        conf_str = f" (confidence: {confidence:.0%})" if confidence < 0.9 else ""
        console.print(
            f"[bold cyan]>> Classified Domain:[/bold cyan] [bold green]Rotating Shaft & Power Transmission[/bold green]{conf_str}"
        )
        res = _handle_shaft(prompt, p_lower, output_dir)
        if res and auto_open:
            launch_cad_viewer(Path(output_dir or "Project/shaft"))
        return res

    console.print(
        "[bold cyan]>> Engaging AI Generative Engineering Agent:[/bold cyan] [bold green]On-the-Fly CAD & Physics Synthesis[/bold green]"
    )
    res = _handle_generative(prompt, p_lower, output_dir)
    if res and auto_open:
        slug = meta.get("slug", "generative_part")
        launch_cad_viewer(Path(output_dir or f"Project/{slug}"))
    return res


def interactive_repl() -> None:
    """Interactive terminal prompt with guided numbered menu and natural language REPL."""
    from cli.interactive import run_interactive_menu

    run_interactive_menu(main, console)


def _show_help() -> None:
    tools = find_cad_tools()
    rows = []
    for name in ["openscad", "freecad"]:
        p = tools.get(name)
        rows.append(
            (
                name.capitalize(),
                f"[green]Installed[/green] ({p})" if p else "[yellow]Not detected[/yellow]",
            )
        )

    from ai.llm_router import LLMRouter

    providers = LLMRouter.get_configured_providers()
    llm = (
        f"[green]{' -> '.join(p.upper() for p in providers)}[/green]"
        if providers
        else "[yellow]none configured (offline heuristic engine)[/yellow]"
    )

    from convert import available_formats

    conv = ", ".join(available_formats())

    console.print(
        Panel(
            "[bold cyan]MDIE - Mechanical Design Intelligence Engine[/bold cyan]\n\n"
            "[bold]Design:[/bold]\n"
            '  mdie "design a chair with 4 splayed legs" [--output-dir DIR] [--open]\n'
            "  mdie chair | bracket                     canned designs\n"
            "  mdie shaft [--d 40 --l 500]               rotating shaft\n\n"
            "[bold]Files:[/bold]\n"
            "  mdie convert <input> --to <fmt> [-o OUT]  convert a file (see formats below)\n"
            "  mdie <spec.docx|md|html|pdf>            read a spec file as a design prompt\n"
            "  mdie drawings [--outdir DIR] [--pdf]      regenerate chair drawing sheets\n"
            "  mdie report <project> [--ai]              consolidate an engineering report\n"
            "  mdie report <project> --check             validate report structure\n"
            "  mdie validate <file> [--profile NAME]     check tables, anchors, sentinels\n"
            "  mdie view <project|file> [--freecad]     open in a CAD viewer\n\n"
            "[bold]Other:[/bold]\n"
            "  mdie info                                 detected tools and providers\n"
            "  mdie trace [--steps|--values|--member NAME]  how the physics numbers are made\n"
            "  mdie [menu]                               interactive numbered wizard menu\n\n"
            f"[bold cyan]Convertible formats:[/bold cyan] {conv}\n\n"
            f"[bold cyan]Local CAD tools:[/bold cyan]\n"
            + "\n".join(f"  * {n}: {s}" for n, s in rows)
            + f"\n\n[bold cyan]LLM cascade:[/bold cyan] {llm}\n"
            "  [dim](GROQ_API_KEY, OPENROUTER_API_KEY, GEMINI_API_KEY, OLLAMA_HOST)[/dim]",
            border_style="cyan",
        )
    )


def _show_info() -> None:
    from ai.llm_router import LLMRouter
    from core import __version__

    table = Table(title=f"MDIE {__version__}", show_header=True, header_style="bold cyan")
    table.add_column("Component")
    table.add_column("Status")

    table.add_row("python", sys.version.split()[0])
    for name in ["openscad", "freecad"]:
        p = find_cad_tools().get(name)
        table.add_row(name, p or "not detected")
    providers = LLMRouter.get_configured_providers()
    table.add_row(
        "llm cascade", " -> ".join(providers) if providers else "offline heuristic engine"
    )

    from convert import available_formats, missing_dependencies

    table.add_row("convert formats", ", ".join(available_formats()))
    missing = missing_dependencies()
    if missing:
        table.add_row("optional deps missing", ", ".join(sorted(missing)))
    console.print(table)


def _resolve_target(name: str) -> Path:
    """Accept a project name, a project folder or a direct file path."""
    target = Path(name)
    if target.exists():
        return target
    for candidate in (
        Path("Project") / name,
        Path(f"{name}.scad"),
        Path("Project") / name / f"{name}.step",
    ):
        if candidate.exists():
            return candidate
    return target


def _cmd_convert(argv: list[str]) -> int:
    import argparse

    from convert import convert_file, describe_formats

    ap = argparse.ArgumentParser(
        prog="mdie convert",
        description="Convert engineering files between documents, CAD solids and drawing sheets.",
    )
    ap.add_argument("input", nargs="?", help="source file")
    ap.add_argument(
        "--to",
        "-t",
        dest="to",
        help="target format (docx, pdf, html, md, stl, step, scad, 3mf, iges, obj, dxf, dxf-parts, png)",
    )
    ap.add_argument("-o", "--output", dest="output", help="output path")
    ap.add_argument("--list-formats", action="store_true", help="show supported conversions")
    ap.add_argument("--ai", action="store_true", help="AI pass on document output (docx/html)")
    ap.add_argument("--dpi", type=int, default=200, help="raster DPI for png output")
    ap.add_argument(
        "--no-dims",
        dest="dimensions",
        action="store_false",
        help="omit auto-dimensions from STEP -> DXF output",
    )
    args = ap.parse_args(argv)

    if args.list_formats:
        console.print(Markdown(describe_formats()))
        return 0

    if not args.input:
        console.print("[bold red]No input file given.[/bold red]")
        console.print("[dim]Usage: mdie convert <input> --to <fmt> [-o OUT][/dim]")
        return 1

    try:
        result = convert_file(
            args.input,
            target_format=args.to,
            output_path=args.output,
            use_ai=args.ai,
            dpi=args.dpi,
            dimensions=args.dimensions,
        )
    except Exception as exc:
        console.print(f"[bold red]Conversion failed:[/bold red] {exc}")
        return 1

    if result.is_dir():
        count = len(list(result.glob("*.dxf")))
        console.print(
            f"[bold green]>> Wrote[/bold green] [bold cyan]{count} DXF files[/bold cyan] to {result}"
        )
        return 0

    size = result.stat().st_size / 1024
    console.print(
        f"[bold green]>> Wrote[/bold green] [bold cyan]{result}[/bold cyan] ({size:.1f} KB)"
    )
    return 0


def _cmd_drawings(argv: list[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="mdie drawings", description="Regenerate the dimensioned chair drawing sheets."
    )
    ap.add_argument("--outdir", default="Project/chair/drawings")
    ap.add_argument("--pdf", action="store_true", help="also emit a combined PDF sheet")
    ap.add_argument("--chrome", help="explicit Chrome/Chromium path for PDF output")
    args = ap.parse_args(argv)

    import subprocess

    cmd = [sys.executable, "-m", "drafting.part_drawings", "--outdir", args.outdir]
    if args.pdf:
        cmd.append("--pdf")
    if args.chrome:
        cmd += ["--chrome", args.chrome]
    return subprocess.call(cmd)


def _cmd_report(argv: list[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="mdie report", description="Consolidate an engineering report via learning-tools."
    )
    ap.add_argument("target", nargs="?", default="chair", help="project name or report path")
    ap.add_argument("--ai", action="store_true", help="enable AI summarisation")
    ap.add_argument(
        "--check",
        action="store_true",
        help="validate the report's structure instead of consolidating it",
    )
    ap.add_argument(
        "--profile",
        choices=["core", "academic", "academic_v2", "reference_closed_form"],
        help="content policy for --check (default: inferred from the file name)",
    )
    args = ap.parse_args(argv)

    target_p = Path(args.target)
    if target_p.exists() and target_p.is_file():
        target_file = target_p
    else:
        candidates = [
            Path("Project") / args.target / "academic_assignment_report.html",
            Path("Project") / args.target / f"{args.target}_report.html",
            Path("Project") / args.target / "report.html",
            Path("Project/chair/academic_assignment_report.html"),
        ]
        target_file = next((c for c in candidates if c.exists()), candidates[-1])

    if not target_file.exists():
        console.print(f"[bold red]Report file not found:[/bold red] {target_file}")
        return 1

    if args.check:
        from reporting.validate import validate_file

        try:
            issues = validate_file(target_file, profile=args.profile)
        except ValueError as exc:
            console.print(f"[bold red]Cannot check:[/bold red] {target_file} ({exc})")
            return 1
        if not issues:
            console.print(f"[bold green]>> Report OK:[/bold green] {target_file}")
            return 0
        for issue in issues:
            style = "bold red" if issue.severity == "error" else "yellow"
            console.print(
                f"[{style}]{issue.severity.upper()}[/{style}] "
                f"[bold]{issue.code}[/bold]: {issue.message}"
            )
        return 1

    from integrations.learning_tools import LearningToolsBridge

    bridge = LearningToolsBridge()

    console.print(f"[bold cyan]>> Consolidating:[/bold cyan] {target_file}")
    console.print(
        f"[dim]Bridge mode: {'REST API (port 5000)' if bridge.is_online() else 'Direct Library Import'}[/dim]"
    )
    res = bridge.consolidate_report(
        report_path=target_file,
        convert_docx=True,
        generate_summaries=True,
        generate_notebooklm=True,
        enable_ai=args.ai,
    )
    console.print(
        f"[bold green]>> Consolidated[/bold green] (chunks: {res.get('chunks_count', 0)})"
    )
    for ftype, fpath in res.get("generated_files", {}).items():
        console.print(f"   - [bold]{ftype.upper()}:[/bold] [cyan]{fpath}[/cyan]")
    return 0


def _cmd_validate(argv: list[str]) -> int:
    """Check rendered reports for structural defects (tables, anchors, sentinels)."""
    import argparse

    from reporting.validate import validate_file

    ap = argparse.ArgumentParser(
        prog="mdie validate",
        description="Check rendered reports for structural defects.",
    )
    ap.add_argument("paths", nargs="+", help="report file(s) to check")
    ap.add_argument(
        "--profile",
        choices=["core", "academic", "academic_v2", "reference_closed_form"],
        help="content policy (default: inferred from the file name)",
    )
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = ap.parse_args(argv)

    failed = False
    for raw in args.paths:
        path = Path(raw)
        if not path.exists():
            console.print(f"[bold red]Missing:[/bold red] {path}")
            failed = True
            continue
        try:
            issues = validate_file(path, profile=args.profile)
        except ValueError as exc:
            console.print(f"[bold red]Cannot check:[/bold red] {path} ({exc})")
            failed = True
            continue
        blocking = [i for i in issues if i.severity == "error" or args.strict]
        if not issues:
            console.print(f"[bold green]OK[/bold green] {path}")
            continue
        console.print(f"[bold yellow]{len(issues)} issue(s)[/bold yellow] {path}")
        for issue in issues:
            style = "bold red" if issue.severity == "error" else "yellow"
            console.print(f"  [{style}]{issue.code}[/{style}]: {issue.message}")
        failed = failed or bool(blocking)
    return 1 if failed else 0


def _cmd_view(argv: list[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="mdie view", description="Open a project in a CAD viewer.")
    ap.add_argument("target", nargs="?", default="chair")
    ap.add_argument("--freecad", "--fc", dest="freecad", action="store_true")
    args = ap.parse_args(argv)

    target = _resolve_target(args.target)
    if not target.exists():
        console.print(f"[bold red]Not found:[/bold red] {target}")
        return 1
    if not launch_cad_viewer(target, tool_type="freecad" if args.freecad else None):
        console.print("[yellow]No CAD viewer available. Install OpenSCAD or FreeCAD.[/yellow]")
        return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="mdie", add_help=False, description="MDIE - plain-language mechanical design."
    )
    ap.add_argument("prompt", nargs="*", help="design prompt (omit to open the interactive prompt)")
    ap.add_argument("-o", "--output-dir", dest="output_dir")
    ap.add_argument("--open", dest="auto_open", action="store_true")
    ap.add_argument("-h", "--help", action="store_true", dest="show_help")
    return ap


def _cmd_trace(argv: list[str]) -> int:
    """Show how MDIE reaches its engineering numbers."""
    import argparse

    from core.frame_model import FrameDesignModel
    from reporting.trace_view import render

    ap = argparse.ArgumentParser(
        prog="mdie trace",
        description="Show the physics source-of-truth chain and how each number is produced.",
    )
    ap.add_argument(
        "--member",
        metavar="NAME",
        help="annotated derivation for one member: leg | rail | arm | bracket | tipping",
    )
    ap.add_argument("--steps", action="store_true", help="replay the solver's calculation log")
    ap.add_argument("--values", action="store_true", help="provenance table of every value")
    args = ap.parse_args(argv)

    render(args, FrameDesignModel())
    return 0


def _load_project_model(target_name: str) -> tuple[Any, Any]:
    """Load or create the appropriate engineering model for a project type.

    Returns a heterogeneous (model, solver) pair: shaft projects use
    ``(EngineeringModel, PhysicsSolver)`` while bracket and chair projects use
    domain-specific model/solver pairs that do not share a common base class.
    Callers should treat the returned model via duck typing (``.name``,
    ``.constraints`` etc.) rather than relying on a static common type.
    """
    from core.bracket_model import BracketGeometry, BracketLoads, BracketModel
    from core.frame_model import STRUCTURAL_MATERIALS, FrameDesignModel, FrameGeometry, FrameLoads
    from core.models import (
        EngineeringConstraints,
        EngineeringModel,
        ShaftSegment,
        Support,
        TorqueLoad,
    )
    from physics.bracket_physics import BracketPhysicsSolver
    from physics.frame_physics import FramePhysicsSolver
    from physics.solver import PhysicsSolver

    geom: Any
    loads: Any
    model: Any
    solver: Any

    if target_name == "shaft":
        model = EngineeringModel(
            name="Stepped Transmission Shaft",
            component_type="shaft",
            total_length=0.5,
            power_watts=10000.0,
            speed_rpm=1500.0,
            material_id="AISI_1045_CD",
            segments=[
                ShaftSegment(start_pos=0.0, end_pos=0.1, outer_diameter=0.040, inner_diameter=0.0, feature_type="bearing_seat"),
                ShaftSegment(start_pos=0.1, end_pos=0.25, outer_diameter=0.030, inner_diameter=0.0, feature_type="smooth"),
                ShaftSegment(start_pos=0.25, end_pos=0.4, outer_diameter=0.050, inner_diameter=0.0, feature_type="gear_mount"),
                ShaftSegment(start_pos=0.4, end_pos=0.5, outer_diameter=0.035, inner_diameter=0.0, feature_type="bearing_seat"),
            ],
            supports=[
                Support(name="Left Bearing", support_type="bearing", position=0.05),
                Support(name="Right Bearing", support_type="bearing", position=0.45),
            ],
            point_loads=[],
            torques=[
                TorqueLoad(name="Input Torque", position=0.15, magnitude=63.66),
                TorqueLoad(name="Output Torque", position=0.35, magnitude=-63.66),
            ],
            constraints=EngineeringConstraints(max_mass_kg=5.0),
        )
        solver = PhysicsSolver()
        return model, solver

    elif target_name == "bracket":
        geom = BracketGeometry()
        loads = BracketLoads()
        material = STRUCTURAL_MATERIALS["STEEL_1018"]
        model = BracketModel(name="Motor Mounting Bracket", geometry=geom, loads=loads, material=material)
        solver = BracketPhysicsSolver()
        return model, solver

    elif target_name == "chair":
        geom = FrameGeometry()
        loads = FrameLoads()
        material = STRUCTURAL_MATERIALS["STEEL_1018"]
        model = FrameDesignModel(name="Structural Frame Assembly", geometry=geom, loads=loads, material=material)
        solver = FramePhysicsSolver()
        return model, solver

    elif target_name == "space_frame":
        from core.frame_model import STRUCTURAL_MATERIALS, FrameDesignModel, FrameGeometry, FrameLoads
        # Space frame uses 3D FEA
        geom = FrameGeometry(topology_type="space_frame")
        loads = FrameLoads()
        material = STRUCTURAL_MATERIALS["STEEL_1018"]
        model = FrameDesignModel(name="3D Space Frame", geometry=geom, loads=loads, material=material)
        # Use frame solver for space frame
        solver = FramePhysicsSolver()
        return model, solver

    else:
        # Default to shaft model
        console.print(f"[yellow]Unknown target '{target_name}', defaulting to shaft model[/yellow]")
        return _load_project_model("shaft")


def _cmd_docx_report(argv: list[str]) -> int:
    """Generate a DOCX engineering report using the multi-agent LangGraph workflow."""
    import argparse

    ap = argparse.ArgumentParser(
        prog="mdie docx-report",
        description="Generate a professional DOCX engineering calculation sheet from solver results.",
    )
    ap.add_argument("target", nargs="?", default="shaft", help="project name (shaft, chair, bracket, space_frame)")
    ap.add_argument("--output", "-o", dest="output", help="output file path (default: Project/<name>/report.docx)")
    args = ap.parse_args(argv)

    target_name = args.target

    # Load appropriate model and solver
    model, solver = _load_project_model(target_name)

    console.print(f"[bold cyan]>> Generating DOCX report for:[/bold cyan] {target_name}")
    console.print(f"[bold cyan]>> Model:[/bold cyan] {model.name}")

    result = solver.solve(model)

    console.print(f"[bold cyan]>> Solver result:[/bold cyan] {'PASS' if getattr(result, 'all_constraints_passed', getattr(result, 'passed', False)) else 'FAIL'}")
    if hasattr(result, 'min_yield_safety_factor'):
        sf = result.min_yield_safety_factor
        console.print(f"   Yield SF: {sf:.2f}" if sf is not None else "   Yield SF: N/A")
    if hasattr(result, 'min_fatigue_safety_factor'):
        sf = result.min_fatigue_safety_factor
        console.print(f"   Fatigue SF: {sf:.2f}" if sf is not None else "   Fatigue SF: N/A")
    if hasattr(result, 'max_deflection_mm'):
        console.print(f"   Max Deflection: {result.max_deflection_mm:.3f} mm")
    if hasattr(result, 'plate_yield_safety_factor'):
        console.print(f"   Plate Yield SF: {result.plate_yield_safety_factor:.2f}")
    if hasattr(result, 'bolt_safety_factor'):
        console.print(f"   Bolt SF: {result.bolt_safety_factor:.2f}")

    # Check if the model is a frame model - we need to convert to EngineeringModel format
    # for the docgen workflow. For now, only shaft models work with the current workflow.
    # TODO: Implement frame/bracket model to EngineeringModel conversion
    if target_name in ("chair", "bracket", "space_frame"):
        console.print("[yellow]Note:[/yellow] Frame/bracket models not yet fully supported in DOCX workflow - using shaft model")
        # Fall back to shaft model
        model, solver = _load_project_model("shaft")
        result = solver.solve(model)

    output_path, errors = generate_docx_report(model, result)

    if errors:
        for err in errors:
            console.print(f"[bold red]Error:[/bold red] {err}")
        return 1

    if output_path:
        console.print(f"[bold green]>> Report written:[/bold green] {output_path}")
        return 0
    else:
        console.print("[bold red]>> Report generation failed[/bold red]")
        return 1


def _cmd_slides(argv: list[str]) -> int:
    """AI-powered slide deck generator.

    Usage:
      mdie slides --from Project/chair/chair_real_data.md --out Project/chair/armchair_slides.html
      mdie slides --content "..." --out slides.html
    """
    import argparse

    from ai.slide_designer import design_slides
    from reporting.slide_engine import render_slide_deck

    ap = argparse.ArgumentParser(
        prog="mdie slides",
        description="Generate an AI-designed, styled HTML slide deck from engineering content.",
    )
    ap.add_argument("--from", dest="source", help="source markdown/data file")
    ap.add_argument("--content", dest="content", help="inline content string")
    ap.add_argument("--title", dest="title", default="Engineering Slide Deck")
    ap.add_argument(
        "--out", "-o", dest="output", default="Project/slides/deck.html", help="output HTML path"
    )
    ap.add_argument("--no-ai", action="store_true", help="use deterministic fallback design")
    args = ap.parse_args(argv)

    # Build content dict from curated spec, source file, or inline string
    content: dict[str, Any]
    if args.source and "chair" in args.source.lower():
        try:
            from ai.armchair_slides_content import ARMCHAIR_SLIDES

            content = ARMCHAIR_SLIDES
        except ImportError:
            content = _build_content_from_file(args.source, args.title)
    elif args.source:
        content = _build_content_from_file(args.source, args.title)
    elif args.content:
        content = {"title": args.title, "source": "inline", "slides": _parse_slides(args.content)}
    else:
        console.print("[red]No content provided. Use --from or --content.[/red]")
        return 1

    spec = design_slides(content, use_ai=not args.no_ai)
    out = render_slide_deck(spec, Path(args.output))
    console.print(f"[bold green]Slide deck written:[/bold green] {out}")
    return 0


def _build_content_from_file(source: str, title: str) -> dict[str, Any]:
    src = Path(source)
    body_text = src.read_text(encoding="utf-8", errors="replace") if src.exists() else ""
    return {"title": title, "source": source, "slides": _parse_slides(body_text)}


def _parse_slides(text: str) -> list[dict[str, Any]]:
    """Split markdown into slide dicts (one per H1/H2 block)."""
    slides: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            if current:
                slides.append(current)
            current = {"type": "cover", "heading": stripped[2:].strip(), "body": []}
        elif stripped.startswith("## "):
            if current:
                slides.append(current)
            current = {"type": "bullet", "heading": stripped[3:].strip(), "body": []}
        elif stripped.startswith("### "):
            if current:
                slides.append(current)
            current = {"type": "bullet", "heading": stripped[4:].strip(), "body": []}
        elif current is not None and stripped:
            current["body"].append(stripped)
    if current:
        slides.append(current)
    return slides


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Report generation is gated on structural validation, so a malformed
    deliverable is never written. Catching that here turns the gate into a
    readable panel instead of a traceback.
    """
    from reporting.validate import ReportValidationError

    try:
        return _dispatch(argv)
    except ReportValidationError as exc:
        console.print(
            Panel(
                f"[bold]{exc.source}[/bold]\n\n"
                + "\n".join(f"  [red]{i.code}[/red]: {i.message}" for i in exc.issues)
                + "\n\n[dim]The report was not written. Fix the generator, then rerun.[/dim]",
                title="[bold red]Report validation failed[/bold red]",
                border_style="red",
            )
        )
        return 2


def _dispatch(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv:
        interactive_repl()
        return 0

    head = argv[0]
    if head in ("-h", "--help", "help"):
        _show_help()
        return 0
    if head == "info":
        _show_info()
        return 0
    if head == "trace":
        return _cmd_trace(argv[1:])
    if head in ("view",):
        return _cmd_view(argv[1:])
    if head == "convert":
        return _cmd_convert(argv[1:])
    if head == "drawings":
        return _cmd_drawings(argv[1:])
    if head in ("report", "consolidate", "study"):
        return _cmd_report(argv[1:])
    if head == "validate":
        return _cmd_validate(argv[1:])
    if head in ("docx-report", "word-report"):
        return _cmd_docx_report(argv[1:])
    if head == "slides":
        return _cmd_slides(argv[1:])
    if head in ("docx", "convert-docx", "word"):
        return _cmd_convert(["--to", "docx"] + argv[1:])
    if head in ("menu", "interactive"):
        interactive_repl()
        return 0

    if head in CANNED:
        prompt, default_dir = CANNED[head]
        rest = argv[1:]
        out_dir, auto_open = _design_flags(rest)
        return (
            0
            if process_prompt(prompt, output_dir=out_dir or default_dir, auto_open=auto_open)
            else 1
        )

    if head in ("solve", "optimize", "design"):
        prompt = " ".join(a for a in argv[1:] if not a.startswith("-"))
        out_dir, auto_open = _design_flags(argv[1:])
        if not prompt:
            prompt = "stepped shaft 500 mm long"
        return 0 if process_prompt(prompt, output_dir=out_dir, auto_open=auto_open) else 1

    out_dir, auto_open = _design_flags(argv)
    prompt = " ".join(a for a in argv if not a.startswith("-"))
    return 0 if process_prompt(prompt, output_dir=out_dir, auto_open=auto_open) else 1


_DOCUMENT_EXTS = {".docx", ".md", ".markdown", ".html", ".htm", ".txt", ".pdf"}


def _blocks_to_plain(blocks: Iterable[Any]) -> str:
    """Flatten the block model into a single string for use as a prompt."""
    lines: list[str] = []
    for block in blocks:
        kind = block[0]
        if kind == "table":
            for row in block[1]:
                lines.append(" | ".join(str(c) for c in row))
        else:
            lines.append(str(block[-1]))
    return "\n".join(lines).strip()


def _read_document_prompt(path: Path) -> str | None:
    """Extract text from a document file, or ``None`` if it is not readable."""
    ext = path.suffix.lower()
    if ext not in _DOCUMENT_EXTS:
        return None
    try:
        if ext == ".docx":
            from convert.documents import blocks_from_docx

            return _blocks_to_plain(blocks_from_docx(path))
        if ext in (".html", ".htm"):
            from convert.documents import blocks_from_html

            return _blocks_to_plain(blocks_from_html(path.read_text(encoding="utf-8", errors="replace")))
        if ext == ".pdf":
            from convert.documents import blocks_from_pdf

            return _blocks_to_plain(blocks_from_pdf(path))
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def _maybe_read_file_prompt(prompt: str) -> str:
    """If the prompt is a path to a readable document, return its extracted text.

    Lets the agent read a design spec written in Word, Markdown, HTML or PDF
    instead of only accepting a typed sentence. A prompt that is not a file, or
    a file it cannot read, is returned unchanged.
    """
    candidate = Path(prompt.strip().strip('"').strip("'"))
    if not candidate.exists() or not candidate.is_file():
        return prompt
    text = _read_document_prompt(candidate)
    return text if text else prompt


def _design_flags(args: list[str]) -> tuple[str | None, bool]:
    out_dir = None
    auto_open = False
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("--output-dir", "-o") and i + 1 < len(args):
            out_dir = args[i + 1]
            i += 1
        elif a == "--open":
            auto_open = True
        i += 1
    return out_dir, auto_open


if __name__ == "__main__":
    raise SystemExit(main())
