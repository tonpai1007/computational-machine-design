"""Command line interface.

Usage shapes
------------
``mdie "design a chair with 4 legs"``   free-form design prompt
``mdie chair | bracket | shaft``        canned designs
``mdie convert in.html --to pdf``       file conversion (see :mod:`mdie.convert`)
``mdie view chair --freecad``           open a project in a CAD viewer
``mdie drawings --pdf``                 regenerate chair drawing sheets
``mdie report chair --ai``              consolidate an engineering report
``mdie info``                           show detected tools and LLM providers
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from mdie.cli.designers import (
    _handle_bracket,
    _handle_chair,
    _handle_generative,
    _handle_shaft,
    _handle_space_frame,
)
from mdie.cli.viewers import find_cad_tools, launch_cad_viewer

console = Console()

SUBCOMMANDS = {
    "design", "chair", "bracket", "shaft", "solve", "optimize",
    "view", "convert", "docx", "convert-docx", "word",
    "drawings", "report", "consolidate", "study", "info", "help",
}

CANNED = {
    "chair": ("Design a chair with two arms and four splayed legs", "Project/chair"),
    "bracket": ("motor mounting bracket with 4 bolt holes, 10 kg, steel", "Project/bracket"),
}


def process_prompt(prompt: str, output_dir: Optional[str] = None,
                   auto_open: bool = False) -> bool:
    """Classify a plain-English prompt and run the matching design pipeline."""
    p_lower = prompt.lower().strip()
    if not p_lower:
        return False

    console.print(f"\n[bold cyan]>> Analyzing Prompt:[/bold cyan] [italic]{prompt}[/italic]")

    from mdie.ai.classifier import DomainClassifier
    domain, meta = DomainClassifier.classify(prompt)

    if domain == "bracket":
        console.print(f"[bold cyan]>> Classified Domain:[/bold cyan] [bold green]Mounting Bracket & Flange Plate[/bold green] (confidence: {meta.get('confidence', 0.95):.0%})")
        res = _handle_bracket(prompt, p_lower, output_dir)
        if res and auto_open:
            launch_cad_viewer(Path(output_dir or "Project/bracket"))
        return res

    if domain == "space_frame":
        console.print(f"[bold cyan]>> Classified Domain:[/bold cyan] [bold green]3D Space Frame & Truss[/bold green] (confidence: {meta.get('confidence', 0.95):.0%})")
        res = _handle_space_frame(prompt, p_lower, output_dir)
        if res and auto_open:
            launch_cad_viewer(Path(output_dir or "Project/space_frame"))
        return res

    if domain == "frame":
        console.print(f"[bold cyan]>> Classified Domain:[/bold cyan] [bold green]Structural Frame & Furniture[/bold green] (confidence: {meta.get('confidence', 0.95):.0%})")
        res = _handle_chair(prompt, p_lower, output_dir)
        if res and auto_open:
            launch_cad_viewer(Path(output_dir or "Project/chair"))
        return res

    if (any(w in p_lower for w in ["shaft", "spindle", "rotor", "axle", "bearing seat"])
            or (domain == "shaft" and meta.get("confidence", 0.5) > 0.8)) and not any(
            w in p_lower for w in ["bolt", "fastener", "spring", "gear", "screw"]):
        confidence = meta.get("confidence", 0.50)
        conf_str = f" (confidence: {confidence:.0%})" if confidence < 0.9 else ""
        console.print(f"[bold cyan]>> Classified Domain:[/bold cyan] [bold green]Rotating Shaft & Power Transmission[/bold green]{conf_str}")
        res = _handle_shaft(prompt, p_lower, output_dir)
        if res and auto_open:
            launch_cad_viewer(Path(output_dir or "Project/shaft"))
        return res

    console.print(f"[bold cyan]>> Engaging AI Generative Engineering Agent:[/bold cyan] [bold green]On-the-Fly CAD & Physics Synthesis[/bold green]")
    res = _handle_generative(prompt, p_lower, output_dir)
    if res and auto_open:
        slug = meta.get("slug", "generative_part")
        launch_cad_viewer(Path(output_dir or f"Project/{slug}"))
    return res


def interactive_repl() -> None:
    """Interactive terminal prompt where the user can type anything."""
    console.print(Panel(
        "[bold cyan]MACHINE DESIGN INTELLIGENCE ENGINE (MDIE)[/bold cyan]\n"
        "AI Proposes CAD Solid Geometry. Physics Solves Forces & Stresses.\n"
        "[italic]Type what you want in plain words (e.g. 'design a chair with 4 legs and two arms', "
        "'shaft with keyway', or 'exit')[/italic]",
        border_style="cyan"
    ))

    while True:
        try:
            prompt = console.input("\n[bold yellow]MDIE > [/bold yellow]").strip()
            if not prompt:
                continue
            if prompt.lower() in ["exit", "quit", "q"]:
                console.print("[cyan]Exiting MDIE CLI. Goodbye![/cyan]")
                break
            process_prompt(prompt)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[cyan]Session ended.[/cyan]")
            break
        except Exception as e:
            console.print(f"[bold red]Error: {str(e)}[/bold red]")


def _show_help() -> None:
    tools = find_cad_tools()
    rows = []
    for name in ["openscad", "freecad"]:
        p = tools.get(name)
        rows.append((name.capitalize(),
                     f"[green]Installed[/green] ({p})" if p else "[yellow]Not detected[/yellow]"))

    from mdie.ai.llm_router import LLMRouter
    providers = LLMRouter.get_configured_providers()
    llm = (f"[green]{' -> '.join(p.upper() for p in providers)}[/green]" if providers
           else "[yellow]none configured (offline heuristic engine)[/yellow]")

    from mdie.convert import available_formats
    conv = ", ".join(available_formats())

    console.print(Panel(
        "[bold cyan]MDIE - Mechanical Design Intelligence Engine[/bold cyan]\n\n"
        "[bold]Design:[/bold]\n"
        '  mdie "design a chair with 4 splayed legs" [--output-dir DIR] [--open]\n'
        "  mdie chair | bracket                     canned designs\n"
        "  mdie shaft [--d 40 --l 500]               rotating shaft\n\n"
        "[bold]Files:[/bold]\n"
        "  mdie convert <input> --to <fmt> [-o OUT]  convert a file (see formats below)\n"
        "  mdie drawings [--outdir DIR] [--pdf]      regenerate chair drawing sheets\n"
        "  mdie report <project> [--ai]              consolidate an engineering report\n"
        "  mdie view <project|file> [--freecad]     open in a CAD viewer\n\n"
        "[bold]Other:[/bold]\n"
        "  mdie info                                 detected tools and providers\n"
        "  mdie                                      interactive prompt\n\n"
        f"[bold cyan]Convertible formats:[/bold cyan] {conv}\n\n"
        f"[bold cyan]Local CAD tools:[/bold cyan]\n"
        + "\n".join(f"  * {n}: {s}" for n, s in rows)
        + f"\n\n[bold cyan]LLM cascade:[/bold cyan] {llm}\n"
          "  [dim](GROQ_API_KEY, OPENROUTER_API_KEY, GEMINI_API_KEY, OLLAMA_HOST)[/dim]",
        border_style="cyan"
    ))


def _show_info() -> None:
    from mdie import __version__
    from mdie.ai.llm_router import LLMRouter

    table = Table(title=f"MDIE {__version__}", show_header=True, header_style="bold cyan")
    table.add_column("Component")
    table.add_column("Status")

    table.add_row("python", sys.version.split()[0])
    for name in ["openscad", "freecad"]:
        p = find_cad_tools().get(name)
        table.add_row(name, p or "not detected")
    providers = LLMRouter.get_configured_providers()
    table.add_row("llm cascade", " -> ".join(providers) if providers else "offline heuristic engine")

    from mdie.convert import available_formats, missing_dependencies
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
    for candidate in (Path("Project") / name, Path(f"{name}.scad"),
                      Path("Project") / name / f"{name}.step"):
        if candidate.exists():
            return candidate
    return target


def _cmd_convert(argv: list[str]) -> int:
    from mdie.convert import convert_file, describe_formats

    import argparse
    ap = argparse.ArgumentParser(
        prog="mdie convert",
        description="Convert engineering files between documents, CAD solids and drawing sheets.")
    ap.add_argument("input", nargs="?", help="source file")
    ap.add_argument("--to", "-t", dest="to", help="target format (docx, pdf, html, md, "
                                                   "stl, step, scad, 3mf, iges, obj, png)")
    ap.add_argument("-o", "--output", dest="output", help="output path")
    ap.add_argument("--list-formats", action="store_true", help="show supported conversions")
    ap.add_argument("--ai", action="store_true", help="AI pass on document output (docx/html)")
    ap.add_argument("--dpi", type=int, default=200, help="raster DPI for png output")
    args = ap.parse_args(argv)

    if args.list_formats:
        console.print(Markdown(describe_formats()))
        return 0

    if not args.input:
        console.print("[bold red]No input file given.[/bold red]")
        console.print("[dim]Usage: mdie convert <input> --to <fmt> [-o OUT][/dim]")
        return 1

    try:
        result = convert_file(args.input, target_format=args.to,
                              output_path=args.output, use_ai=args.ai, dpi=args.dpi)
    except Exception as exc:
        console.print(f"[bold red]Conversion failed:[/bold red] {exc}")
        return 1

    size = result.stat().st_size / 1024
    console.print(f"[bold green]>> Wrote[/bold green] [bold cyan]{result}[/bold cyan] ({size:.1f} KB)")
    return 0


def _cmd_drawings(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="mdie drawings",
                                 description="Regenerate the dimensioned chair drawing sheets.")
    ap.add_argument("--outdir", default="Project/chair/drawings")
    ap.add_argument("--pdf", action="store_true", help="also emit a combined PDF sheet")
    ap.add_argument("--chrome", help="explicit Chrome/Chromium path for PDF output")
    args = ap.parse_args(argv)

    import subprocess
    cmd = [sys.executable, "-m", "mdie.drafting.part_drawings", "--outdir", args.outdir]
    if args.pdf:
        cmd.append("--pdf")
    if args.chrome:
        cmd += ["--chrome", args.chrome]
    return subprocess.call(cmd)


def _cmd_report(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="mdie report",
                                 description="Consolidate an engineering report via learning-tools.")
    ap.add_argument("target", nargs="?", default="chair", help="project name or report path")
    ap.add_argument("--ai", action="store_true", help="enable AI summarisation")
    args = ap.parse_args(argv)

    from mdie.integrations.learning_tools import LearningToolsBridge
    bridge = LearningToolsBridge()

    target_p = Path(args.target)
    if target_p.exists() and target_p.is_file():
        target_file = target_p
    else:
        target_file = None
        for cand in (Path("Project") / args.target / "academic_assignment_report.html",
                     Path("Project") / args.target / f"{args.target}_report.html",
                     Path("Project") / args.target / "report.html"):
            if cand.exists():
                target_file = cand
                break
        if target_file is None:
            target_file = Path("Project/chair/academic_assignment_report.html")

    if not target_file.exists():
        console.print(f"[bold red]Report file not found:[/bold red] {target_file}")
        return 1

    console.print(f"[bold cyan]>> Consolidating:[/bold cyan] {target_file}")
    console.print(f"[dim]Bridge mode: {'REST API (port 5000)' if bridge.is_online() else 'Direct Library Import'}[/dim]")
    res = bridge.consolidate_report(report_path=target_file, convert_docx=True,
                                    generate_summaries=True, generate_notebooklm=True,
                                    enable_ai=args.ai)
    console.print(f"[bold green]>> Consolidated[/bold green] (chunks: {res.get('chunks_count', 0)})")
    for ftype, fpath in res.get("generated_files", {}).items():
        console.print(f"   - [bold]{ftype.upper()}:[/bold] [cyan]{fpath}[/cyan]")
    return 0


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


def _build_parser():
    import argparse
    ap = argparse.ArgumentParser(prog="mdie", add_help=False,
                                 description="MDIE - plain-language mechanical design.")
    ap.add_argument("prompt", nargs="*", help="design prompt (omit to open the interactive prompt)")
    ap.add_argument("-o", "--output-dir", dest="output_dir")
    ap.add_argument("--open", dest="auto_open", action="store_true")
    ap.add_argument("-h", "--help", action="store_true", dest="show_help")
    return ap


def main(argv: Optional[list[str]] = None) -> int:
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
    if head in ("view",):
        return _cmd_view(argv[1:])
    if head == "convert":
        return _cmd_convert(argv[1:])
    if head == "drawings":
        return _cmd_drawings(argv[1:])
    if head in ("report", "consolidate", "study"):
        return _cmd_report(argv[1:])
    if head in ("docx", "convert-docx", "word"):
        return _cmd_convert(["--to", "docx"] + argv[1:])

    if head in CANNED:
        prompt, default_dir = CANNED[head]
        rest = argv[1:]
        out_dir, auto_open = _design_flags(rest)
        return 0 if process_prompt(prompt, output_dir=out_dir or default_dir,
                                   auto_open=auto_open) else 1

    if head in ("solve", "optimize", "design"):
        prompt = " ".join(a for a in argv[1:] if not a.startswith("-"))
        out_dir, auto_open = _design_flags(argv[1:])
        if not prompt:
            prompt = "stepped shaft 500 mm long"
        return 0 if process_prompt(prompt, output_dir=out_dir, auto_open=auto_open) else 1

    out_dir, auto_open = _design_flags(argv)
    prompt = " ".join(a for a in argv if not a.startswith("-"))
    return 0 if process_prompt(prompt, output_dir=out_dir, auto_open=auto_open) else 1


def _design_flags(args: list[str]) -> tuple[Optional[str], bool]:
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