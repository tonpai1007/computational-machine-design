"""Interactive CLI menu and terminal wizard.

Provides a guided, numbered console menu for users who prefer not to memorize
CLI flags and subcommands. Also accepts free-form prompts and direct commands.
"""

from __future__ import annotations

import shlex
import sys
from collections.abc import Callable
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

console = Console()


def render_header() -> Panel:
    """Return the stylized MDIE interactive header panel."""
    return Panel(
        "[bold cyan]MACHINE DESIGN INTELLIGENCE ENGINE (MDIE)[/bold cyan] [bold white]—[/bold white] [bold yellow]🧭 เมนูนำทางแบบโต้ตอบ[/bold yellow]\n"
        "[dim]AI Proposes CAD Solid Geometry  •  Deterministic Physics Solves Forces & Stresses[/dim]\n"
        "[italic white]Select an option by number [1-10], describe a custom machine in plain words, or 'q' to exit.[/italic white]",
        border_style="cyan",
        title="[bold green]MDIE Engineering Terminal Wizard[/bold green]",
        subtitle="[dim]Deterministic Mechanical Engineering • No Guesswork[/dim]",
    )


def render_menu_table() -> Table:
    """Return the main menu options formatted in a rich table."""
    table = Table(
        title="Available Engineering Workflows (เลือกการทำงานตามหมายเลข)",
        show_header=True,
        header_style="bold cyan",
        border_style="blue",
    )
    table.add_column("#", style="bold green", justify="center", width=4)
    table.add_column("Workflow", style="bold white", width=26)
    table.add_column("Thai Description (คำอธิบาย)", style="yellow", width=28)
    table.add_column("Deliverables & Output", style="dim white")

    table.add_row(
        "1",
        "🪑 Armchair Frame",
        "ออกแบบเก้าอี้พักผ่อนโครงเหล็ก",
        "3D CAD (.step/.stl), closed-form physics, 3D FEA, academic report",
    )
    table.add_row(
        "2",
        "⚙️ Transmission Shaft",
        "ออกแบบเพลาส่งกำลังหมุน",
        "ASME B106.1M, keys, bearings, torsional fatigue, 3D stepped shaft",
    )
    table.add_row(
        "3",
        "🔩 Motor Bracket",
        "ออกแบบแป้นยึดมอเตอร์ / L-Bracket",
        "Plate bending, bolt tension/shear, von Mises stress check, 3D solid",
    )
    table.add_row(
        "4",
        "🏗️ 3D Space Frame",
        "คำนวณโครงข้อหมุน 3 มิติ (FEA)",
        "3D direct stiffness solver, nodal deflections, reaction forces",
    )
    table.add_row(
        "5",
        "🔍 Physics Trace & Audit",
        "ตรวจสอบที่มาของสูตรและตัวเลข",
        "Inspect source-of-truth chain, member derivations, step-by-step log",
    )
    table.add_row(
        "6",
        "🔄 Universal Converter",
        "แปลงไฟล์เอกสาร & โมเดล CAD",
        "Convert Word (.docx), PDF, HTML, STEP, STL, SCAD, SVG blueprints",
    )
    table.add_row(
        "7",
        "📐 Engineering Drawings",
        "สร้างแบบร่างวิศวกรรม (Drawing)",
        "ISO 128 / ANSI drawing sheets (SVG blueprints or combined PDF)",
    )
    table.add_row(
        "8",
        "📊 Consolidate Reports",
        "รวบรวมรายงานผลวิศวกรรม",
        "Academic dossier, white-paper calculation sheet, NotebookLM pack",
    )
    table.add_row(
        "9",
        "👓 3D CAD Viewer",
        "เปิดโมเดลใน FreeCAD / OpenSCAD",
        "Launch local CAD viewer to inspect generated STEP / OpenSCAD solids",
    )
    table.add_row(
        "10",
        "ℹ️ System Diagnostics",
        "ตรวจสอบระบบและเครื่องมือ",
        "Detect FreeCAD, OpenSCAD, LLM API keys, supported file converters",
    )
    table.add_row(
        "0",
        "💬 Natural Language",
        "สั่งงานด้วยภาษาพูด (Free Prompt)",
        "Type any custom design prompt in English or Thai",
    )
    table.add_row(
        "q",
        "🚪 Exit / Quit",
        "ออกจากโปรแกรม",
        "Exit MDIE interactive session",
    )
    return table


def handle_chair_action(
    run_cmd: Callable[[list[str]], int], app_console: Console = console
) -> None:
    """Guided wizard for chair design."""
    app_console.print(
        Panel(
            "[bold cyan]🪑 Armchair Framework Design & Physics Synthesis[/bold cyan]\n"
            "[dim]Full parametric armchair: 10 part bodies, 3D FEA, closed-form equilibrium, "
            "academic report & CAD files.[/dim]",
            border_style="cyan",
        )
    )
    app_console.print(
        "  [bold green][1][/bold green] Standard Student Lounge Chair (70 kg occupant, 12×11 mm steel tubing)"
    )
    app_console.print("  [bold green][2][/bold green] Custom Sizing & Occupant Mass")
    app_console.print("  [bold yellow][b][/bold yellow] Back to Main Menu")

    choice = (
        app_console.input("\n[bold yellow]Select chair option [1/2/b, default: 1]: [/bold yellow]")
        .strip()
        .lower()
    )
    if choice in ("b", "back", "cancel"):
        return
    if choice == "2":
        mass = (
            app_console.input("[cyan]Occupant mass in kg [default: 70]: [/cyan]").strip() or "70"
        )
        material = (
            app_console.input(
                "[cyan]Material [steel/aluminum/stainless, default: steel]: [/cyan]"
            ).strip()
            or "steel"
        )
        prompt = (
            f"Design a chair with two arms and four splayed legs for {mass} kg occupant, "
            f"material {material}"
        )
        app_console.print(f"\n[bold green]>> Executing:[/bold green] {prompt}")
        run_cmd([prompt, "-o", "Project/chair"])
    else:
        app_console.print("\n[bold green]>> Executing:[/bold green] Standard Armchair Frame...")
        run_cmd(["chair"])

    view = (
        app_console.input("\n[bold yellow]Open in CAD viewer now? [y/N]: [/bold yellow]")
        .strip()
        .lower()
    )
    if view in ("y", "yes"):
        from cli.viewers import launch_cad_viewer

        launch_cad_viewer(Path("Project/chair"))


def handle_shaft_action(
    run_cmd: Callable[[list[str]], int], app_console: Console = console
) -> None:
    """Guided wizard for transmission shaft design."""
    app_console.print(
        Panel(
            "[bold cyan]⚙️ Rotating Transmission Shaft Design (ASME B106.1M)[/bold cyan]\n"
            "[dim]Calculates stepped shaft diameters, torsional fatigue, keyway stresses, "
            "bearing reactions, and generates 3D CAD (.step, .stl, .scad).[/dim]",
            border_style="cyan",
        )
    )
    dia = (
        app_console.input("[cyan]Shaft diameter at critical section (mm) [default: 40]: [/cyan]").strip()
        or "40"
    )
    length = app_console.input("[cyan]Shaft length (mm) [default: 500]: [/cyan]").strip() or "500"
    torque = (
        app_console.input("[cyan]Applied torque (N·m) [default: 150]: [/cyan]").strip() or "150"
    )
    speed = (
        app_console.input("[cyan]Rotational speed (RPM) [default: 1800]: [/cyan]").strip() or "1800"
    )

    prompt = f"stepped shaft {length} mm long, {dia} mm diameter, {torque} Nm torque at {speed} rpm"
    app_console.print(f"\n[bold green]>> Executing:[/bold green] {prompt}")
    run_cmd([prompt, "-o", "Project/shaft"])

    view = (
        app_console.input("\n[bold yellow]Open in CAD viewer now? [y/N]: [/bold yellow]")
        .strip()
        .lower()
    )
    if view in ("y", "yes"):
        from cli.viewers import launch_cad_viewer

        launch_cad_viewer(Path("Project/shaft"))


def handle_bracket_action(
    run_cmd: Callable[[list[str]], int], app_console: Console = console
) -> None:
    """Guided wizard for motor mounting bracket."""
    app_console.print(
        Panel(
            "[bold cyan]🔩 Motor Mounting Bracket (L-Bracket & Bolt Pattern)[/bold cyan]\n"
            "[dim]Calculates base plate bending, bolt shear/tension under motor mass, "
            "torque and thrust, plus generates 3D CAD & audit sheet.[/dim]",
            border_style="cyan",
        )
    )
    mass = app_console.input("[cyan]Motor mass (kg) [default: 5]: [/cyan]").strip() or "5"
    height = app_console.input("[cyan]Upright height (mm) [default: 120]: [/cyan]").strip() or "120"
    holes = app_console.input("[cyan]Number of bolt holes [default: 4]: [/cyan]").strip() or "4"
    mat = (
        app_console.input(
            "[cyan]Material [steel/aluminum/stainless, default: steel]: [/cyan]"
        ).strip()
        or "steel"
    )

    prompt = (
        f"motor mounting bracket with {holes} bolt holes, {mass} kg motor, "
        f"{height} mm upright, {mat}"
    )
    app_console.print(f"\n[bold green]>> Executing:[/bold green] {prompt}")
    run_cmd([prompt, "-o", "Project/bracket"])

    view = (
        app_console.input("\n[bold yellow]Open in CAD viewer now? [y/N]: [/bold yellow]")
        .strip()
        .lower()
    )
    if view in ("y", "yes"):
        from cli.viewers import launch_cad_viewer

        launch_cad_viewer(Path("Project/bracket"))


def handle_space_frame_action(
    run_cmd: Callable[[list[str]], int], app_console: Console = console
) -> None:
    """Guided wizard for 3D space frame FEA."""
    app_console.print(
        Panel(
            "[bold cyan]🏗️ 3D Space Frame & Truss Solver (Direct Stiffness FEA)[/bold cyan]\n"
            "[dim]Solves 6-DOF per node 3D space trusses, nodal deflections, reaction forces, "
            "and member stress checks.[/dim]",
            border_style="cyan",
        )
    )
    app_console.print("  [bold green][1][/bold green] Space Truss Transmission Tower (5 kN wind load)")
    app_console.print("  [bold green][2][/bold green] Cantilever Space Frame Structure")
    app_console.print("  [bold yellow][b][/bold yellow] Back to Main Menu")

    choice = (
        app_console.input("\n[bold yellow]Select frame option [1/2/b, default: 1]: [/bold yellow]")
        .strip()
        .lower()
    )
    if choice in ("b", "back", "cancel"):
        return
    prompt = (
        "cantilever 3D space frame structure"
        if choice == "2"
        else "transmission tower 3D space frame 5 kN load"
    )

    app_console.print(f"\n[bold green]>> Executing:[/bold green] {prompt}")
    run_cmd([prompt, "-o", "Project/space_frame"])


def handle_trace_action(
    run_cmd: Callable[[list[str]], int], app_console: Console = console
) -> None:
    """Submenu for physics audit and formula traceability."""
    while True:
        app_console.print(
            Panel(
                "[bold cyan]🔍 Physics Traceability & Calculation Audit[/bold cyan]\n"
                "[dim]Inspect the exact mathematical and physics source-of-truth chain in MDIE.[/dim]",
                border_style="cyan",
            )
        )
        app_console.print(
            "  [bold green][1][/bold green] Overview: Source-of-Truth Chain & Equation Flow"
        )
        app_console.print(
            "  [bold green][2][/bold green] Member Derivation Audit (leg, rail, arm, bracket, tipping)"
        )
        app_console.print(
            "  [bold green][3][/bold green] Solver Calculation Log (Chronological execution log)"
        )
        app_console.print(
            "  [bold green][4][/bold green] Complete Variable & Parameter Provenance Table"
        )
        app_console.print("  [bold yellow][b][/bold yellow] Back to Main Menu")

        c = (
            app_console.input(
                "\n[bold yellow]Select trace option [1-4, b, default: 1]: [/bold yellow]"
            )
            .strip()
            .lower()
            or "1"
        )
        if c in ("b", "back", "q", "exit"):
            break
        if c == "1":
            run_cmd(["trace"])
        elif c == "2":
            app_console.print(
                "\n[cyan]Available members:[/cyan] leg, rail, arm, bracket, tipping"
            )
            m = (
                app_console.input("[bold yellow]Enter member name [default: leg]: [/bold yellow]")
                .strip()
                .lower()
                or "leg"
            )
            run_cmd(["trace", "--member", m])
        elif c == "3":
            run_cmd(["trace", "--steps"])
        elif c == "4":
            run_cmd(["trace", "--values"])

        app_console.input("\n[dim]Press Enter to continue...[/dim]")


def handle_convert_action(
    run_cmd: Callable[[list[str]], int], app_console: Console = console
) -> None:
    """Guided wizard for file conversions."""
    from convert import available_formats

    formats = available_formats()
    app_console.print(
        Panel(
            "[bold cyan]🔄 Universal Engineering File Converter[/bold cyan]\n"
            f"[dim]Supported formats: {', '.join(formats)}[/dim]\n\n"
            "[italic white]Common conversions:\n"
            "  * HTML report -> Word DOCX / PDF\n"
            "  * OpenSCAD (.scad) -> STL / STEP\n"
            "  * SVG Blueprints -> PDF / PNG\n"
            "  * Markdown (.md) -> DOCX / HTML / PDF[/italic white]",
            border_style="cyan",
        )
    )

    in_file = app_console.input(
        "\n[bold yellow]Enter input file path (or 'b' to cancel): [/bold yellow]"
    ).strip()
    if in_file.lower() in ("b", "back", "cancel") or not in_file:
        return

    in_path = Path(in_file.strip('"').strip("'"))
    if not in_path.exists():
        app_console.print(f"[bold red]File not found:[/bold red] {in_path}")
        return

    to_fmt = (
        app_console.input(
            "[bold yellow]Enter target format (e.g. docx, pdf, stl, step): [/bold yellow]"
        )
        .strip()
        .lower()
    )
    if not to_fmt:
        return

    out_file = app_console.input(
        "[cyan]Output file path (press Enter for automatic name): [/cyan]"
    ).strip()
    cmd = ["convert", str(in_path), "--to", to_fmt]
    if out_file:
        cmd += ["-o", out_file.strip('"').strip("'")]

    run_cmd(cmd)


def handle_drawings_action(
    run_cmd: Callable[[list[str]], int], app_console: Console = console
) -> None:
    """Guided wizard for technical drawing sheets."""
    app_console.print(
        Panel(
            "[bold cyan]📐 ISO 128 / ANSI Drawing Sheets Generator[/bold cyan]\n"
            "[dim]Produces dimensioned orthographic projection blueprints with title block and BOM.[/dim]",
            border_style="cyan",
        )
    )
    app_console.print("  [bold green][1][/bold green] Generate SVG Vector Blueprints (Default)")
    app_console.print(
        "  [bold green][2][/bold green] Generate Combined PDF Drawing Sheet (--pdf)"
    )
    app_console.print("  [bold yellow][b][/bold yellow] Back to Main Menu")

    c = (
        app_console.input(
            "\n[bold yellow]Select drawing format [1/2/b, default: 1]: [/bold yellow]"
        )
        .strip()
        .lower()
        or "1"
    )
    if c in ("b", "back", "cancel"):
        return
    if c == "2":
        run_cmd(["drawings", "--pdf"])
    else:
        run_cmd(["drawings"])


def handle_report_action(
    run_cmd: Callable[[list[str]], int], app_console: Console = console
) -> None:
    """Guided wizard for engineering report consolidation."""
    app_console.print(
        Panel(
            "[bold cyan]📊 Consolidate Engineering Report[/bold cyan]\n"
            "[dim]Aggregates HTML, DOCX, study notes, and NotebookLM briefing pack.[/dim]",
            border_style="cyan",
        )
    )
    proj = (
        app_console.input("[cyan]Project name or path [default: chair]: [/cyan]").strip()
        or "chair"
    )
    ai_choice = (
        app_console.input("[cyan]Enable AI executive summary synthesis? [y/N]: [/cyan]")
        .strip()
        .lower()
    )
    cmd = ["report", proj]
    if ai_choice in ("y", "yes"):
        cmd.append("--ai")
    run_cmd(cmd)


def handle_view_action(
    run_cmd: Callable[[list[str]], int], app_console: Console = console
) -> None:
    """Guided wizard for launching CAD viewer."""
    app_console.print(
        Panel(
            "[bold cyan]👓 Launch 3D CAD Viewer[/bold cyan]\n"
            "[dim]Open solid model geometry in FreeCAD or OpenSCAD.[/dim]",
            border_style="cyan",
        )
    )
    proj_dir = Path("Project")
    projects: list[str] = []
    if proj_dir.exists():
        projects = [
            p.name for p in proj_dir.iterdir() if p.is_dir() and not p.name.startswith(".")
        ]

    if projects:
        app_console.print("[cyan]Detected projects in Project/:[/cyan]")
        for idx, p in enumerate(projects, 1):
            app_console.print(f"  [{idx}] {p}")
        app_console.print("  [o] Other / custom path")
        target_choice = (
            app_console.input(
                "\n[bold yellow]Select project number or type name [default: 1]: [/bold yellow]"
            ).strip()
            or "1"
        )
        if target_choice.isdigit() and 1 <= int(target_choice) <= len(projects):
            target = projects[int(target_choice) - 1]
        elif target_choice.lower() in ("b", "back"):
            return
        elif target_choice.lower() == "o":
            target = app_console.input("[cyan]Enter project or file path: [/cyan]").strip()
            if not target:
                return
        else:
            target = target_choice
    else:
        target = (
            app_console.input("[cyan]Target project name or file [default: chair]: [/cyan]").strip()
            or "chair"
        )

    viewer_tool = app_console.input(
        "[cyan]CAD Tool [1: Auto-detect, 2: FreeCAD, 3: OpenSCAD, default: 1]: [/cyan]"
    ).strip()
    cmd = ["view", target]
    if viewer_tool == "2":
        cmd.append("--freecad")
    run_cmd(cmd)


def handle_info_action(
    run_cmd: Callable[[list[str]], int], app_console: Console = console
) -> None:
    """Display system diagnostics and detected tools."""
    run_cmd(["info"])


def handle_prompt_action(
    run_cmd: Callable[[list[str]], int], app_console: Console = console
) -> None:
    """Handle free-form natural language prompt."""
    app_console.print(
        Panel(
            "[bold cyan]💬 Natural Language Design Prompt[/bold cyan]\n"
            "[dim]Describe what you want to design, solve, or convert. "
            "MDIE AI router and deterministic solvers will handle it.[/dim]\n\n"
            "[italic white]Examples:\n"
            "  * 'design a transmission shaft 600 mm long, 50 mm dia, 200 Nm'\n"
            "  * 'aluminum motor bracket for 8 kg motor with 4 bolt holes'\n"
            "  * 'chair with 4 legs and armrests'\n"
            "  * 'solve space truss tower under 10 kN lateral load'[/italic white]",
            border_style="cyan",
        )
    )
    p = app_console.input("\n[bold yellow]Enter design prompt: [/bold yellow]").strip()
    if p:
        run_cmd([p])


def run_interactive_menu(
    main_fn: Callable[[list[str]], int], app_console: Console = console
) -> None:
    """Run the interactive numbered menu wizard."""
    while True:
        try:
            app_console.print()
            app_console.print(render_header())
            app_console.print(render_menu_table())

            choice = (
                app_console.input(
                    "\n[bold yellow]MDIE [1-10, 0, or q to exit] > [/bold yellow]"
                )
                .strip()
            )
            if not choice:
                continue

            low = choice.lower()
            if low in ("q", "quit", "exit"):
                app_console.print("[cyan]Exiting MDIE CLI. Goodbye! (ออกจากระบบเรียบร้อย)[/cyan]")
                break

            if choice == "1":
                handle_chair_action(main_fn, app_console)
            elif choice == "2":
                handle_shaft_action(main_fn, app_console)
            elif choice == "3":
                handle_bracket_action(main_fn, app_console)
            elif choice == "4":
                handle_space_frame_action(main_fn, app_console)
            elif choice == "5":
                handle_trace_action(main_fn, app_console)
            elif choice == "6":
                handle_convert_action(main_fn, app_console)
            elif choice == "7":
                handle_drawings_action(main_fn, app_console)
            elif choice == "8":
                handle_report_action(main_fn, app_console)
            elif choice == "9":
                handle_view_action(main_fn, app_console)
            elif choice == "10":
                handle_info_action(main_fn, app_console)
            elif choice == "0":
                handle_prompt_action(main_fn, app_console)
            elif low in ("h", "help", "?"):
                main_fn(["--help"])
            else:
                # Direct command execution (e.g., 'chair', 'mdie view', 'trace --member leg')
                parts = shlex.split(choice)
                if parts and parts[0].lower() == "mdie":
                    parts = parts[1:]
                if not parts:
                    continue
                main_fn(parts)

            app_console.input("\n[dim]Press Enter to return to menu...[/dim]")

        except (KeyboardInterrupt, EOFError):
            app_console.print("\n[cyan]Session ended. (สิ้นสุดเซสชัน)[/cyan]")
            break
        except Exception as exc:
            app_console.print(f"[bold red]Error: {exc}[/bold red]")
            app_console.input("\n[dim]Press Enter to return to menu...[/dim]")
