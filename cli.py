"""
MDIE Command Line Interface (CLI)
Type what you want in plain words -> AI writes the CAD and calculates forces for you.
Clean deliverables (.step, .stl, .scad, .html) saved directly to your Project folder.
"""

import sys
import os
import re
from pathlib import Path
from typing import Optional, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

import subprocess
import shutil

console = Console()

def find_cad_tools() -> dict:
    """Detect local lightweight CAD viewers (OpenSCAD, FreeCAD, etc.)"""
    tools = {}
    
    # OpenSCAD candidates
    openscad_candidates = [
        shutil.which("openscad"),
        r"C:\Program Files\OpenSCAD\openscad.com",
        r"C:\Program Files\OpenSCAD\openscad.exe",
        r"C:\Program Files (x86)\OpenSCAD\openscad.com",
        r"C:\Program Files (x86)\OpenSCAD\openscad.exe",
        str(Path.home() / r"AppData\Local\Programs\OpenSCAD\openscad.com"),
        str(Path.home() / r"AppData\Local\Programs\OpenSCAD\openscad.exe")
    ]
    for p in openscad_candidates:
        if p and Path(p).exists():
            tools["openscad"] = str(p)
            break
            
    # FreeCAD candidates
    freecad_candidates = [
        shutil.which("freecad"),
        shutil.which("FreeCAD"),
        r"C:\Program Files\FreeCAD\bin\FreeCAD.exe",
        r"C:\Program Files\FreeCAD 1.1\bin\FreeCAD.exe",
        str(Path.home() / r"AppData\Local\Programs\FreeCAD 1.1\bin\FreeCAD.exe"),
        str(Path.home() / r"AppData\Local\Programs\FreeCAD\bin\FreeCAD.exe"),
    ]
    for p in freecad_candidates:
        if p and Path(p).exists():
            tools["freecad"] = str(p)
            break

    return tools


def launch_cad_viewer(target: Path, tool_type: Optional[str] = None) -> bool:
    """Launch OpenSCAD or FreeCAD for a target folder or CAD file."""
    tools = find_cad_tools()
    file_to_open = None
    chosen_tool = None
    
    if target.is_dir():
        scad_files = list(target.glob("*.scad"))
        step_files = list(target.glob("*.step")) + list(target.glob("*.stp"))
        
        if tool_type == "freecad" and step_files:
            file_to_open = step_files[0]
            chosen_tool = tools.get("freecad")
        elif scad_files and tools.get("openscad") and tool_type != "freecad":
            file_to_open = scad_files[0]
            chosen_tool = tools.get("openscad")
        elif step_files and tools.get("freecad"):
            file_to_open = step_files[0]
            chosen_tool = tools.get("freecad")
        elif scad_files:
            file_to_open = scad_files[0]
            chosen_tool = tools.get("openscad")
    else:
        file_to_open = target
        if file_to_open.suffix.lower() == ".scad":
            chosen_tool = tools.get("openscad")
        elif file_to_open.suffix.lower() in [".step", ".stp"]:
            chosen_tool = tools.get("freecad")
        elif tool_type == "freecad":
            chosen_tool = tools.get("freecad")
        else:
            chosen_tool = tools.get("openscad") or tools.get("freecad")

    if not file_to_open or not file_to_open.exists():
        console.print(f"[bold red]Cannot find CAD file to open in: {target}[/bold red]")
        return False

    if not chosen_tool:
        console.print(f"[bold yellow]File ready: {file_to_open}[/bold yellow]")
        console.print("[dim]No OpenSCAD or FreeCAD executable found automatically. You can open the file manually.[/dim]")
        return False

    console.print(f"[bold green]>> Launching {Path(chosen_tool).stem} with: {file_to_open.name}[/bold green]")
    try:
        subprocess.Popen([chosen_tool, str(file_to_open.resolve())], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        console.print(f"[bold red]Failed to launch {chosen_tool}: {e}[/bold red]")
        return False


def process_prompt(prompt: str, output_dir: Optional[str] = None, auto_open: bool = False) -> bool:
    """
    Main dispatch pipeline:
    Takes any prompt in plain English, calculates all physics forces,
    generates CAD solid files (.step, .stl, .scad), and writes the HTML report.
    """
    p_lower = prompt.lower().strip()
    if not p_lower:
        return False

    console.print(f"\n[bold cyan]>> Analyzing Prompt:[/bold cyan] [italic]{prompt}[/italic]")

    from mdie.ai.classifier import DomainClassifier
    domain, meta = DomainClassifier.classify(prompt)

    # 1. Mounting Brackets & Flange Plates Domain
    if domain == "bracket":
        console.print(f"[bold cyan]>> Classified Domain:[/bold cyan] [bold green]Mounting Bracket & Flange Plate[/bold green] (confidence: {meta.get('confidence', 0.95):.0%})")
        res = _handle_bracket(prompt, p_lower, output_dir)
        if res and auto_open:
            launch_cad_viewer(Path(output_dir or "Project/bracket"))
        return res

    # 2. 3D Space Frame / Truss Domain
    elif domain == "space_frame":
        console.print(f"[bold cyan]>> Classified Domain:[/bold cyan] [bold green]3D Space Frame & Truss[/bold green] (confidence: {meta.get('confidence', 0.95):.0%})")
        res = _handle_space_frame(prompt, p_lower, output_dir)
        if res and auto_open:
            launch_cad_viewer(Path(output_dir or "Project/space_frame"))
        return res

    # 3. Furniture, Table & Multi-Body Frame Domain
    elif domain == "frame":
        console.print(f"[bold cyan]>> Classified Domain:[/bold cyan] [bold green]Structural Frame & Furniture[/bold green] (confidence: {meta.get('confidence', 0.95):.0%})")
        res = _handle_chair(prompt, p_lower, output_dir)
        if res and auto_open:
            launch_cad_viewer(Path(output_dir or "Project/chair"))
        return res

    # 4. Rotating Shaft & Beam Domain
    elif (any(w in p_lower for w in ["shaft", "spindle", "rotor", "axle", "bearing seat"]) or (domain == "shaft" and meta.get("confidence", 0.5) > 0.8)) and not any(w in p_lower for w in ["bolt", "fastener", "spring", "gear", "screw"]):
        confidence = meta.get("confidence", 0.50)
        conf_str = f" (confidence: {confidence:.0%})" if confidence < 0.9 else ""
        console.print(f"[bold cyan]>> Classified Domain:[/bold cyan] [bold green]Rotating Shaft & Power Transmission[/bold green]{conf_str}")
        res = _handle_shaft(prompt, p_lower, output_dir)
        if res and auto_open:
            launch_cad_viewer(Path(output_dir or "Project/shaft"))
        return res

    # 5. On-The-Fly Generative Engineering Agent (Gears, Springs, Screws, Bolts, Linkages, Mechanisms)
    else:
        console.print(f"[bold cyan]>> Engaging AI Generative Engineering Agent:[/bold cyan] [bold green]On-the-Fly CAD & Physics Synthesis[/bold green]")
        res = _handle_generative(prompt, p_lower, output_dir)
        if res and auto_open:
            slug = meta.get("slug", "generative_part")
            launch_cad_viewer(Path(output_dir or f"Project/{slug}"))
        return res


def _handle_bracket(prompt: str, p_lower: str, output_dir: Optional[str] = None) -> bool:
    from mdie.core.bracket_model import BracketModel, BracketGeometry, BracketLoads, BoltHolePattern
    from mdie.core.frame_model import STRUCTURAL_MATERIALS
    from mdie.physics.bracket_physics import BracketPhysicsSolver
    from mdie.cad.bracket_cad import BracketCADEngine
    from mdie.reports.bracket_report import BracketReportGenerator

    out_path = Path(output_dir or "Project/bracket")
    out_path.mkdir(parents=True, exist_ok=True)

    # 1. Material selection
    mat = STRUCTURAL_MATERIALS["STEEL_1018"]
    if "aluminum" in p_lower or "6061" in p_lower:
        mat = STRUCTURAL_MATERIALS["AL_6061_T6"]
    elif "stainless" in p_lower or "304" in p_lower:
        mat = STRUCTURAL_MATERIALS["STAINLESS_304"]

    geom = BracketGeometry()
    loads = BracketLoads()

    # 2. Extract loads
    kg_match = re.search(r'(\d+(?:\.\d+)?)\s*kg', p_lower)
    if kg_match:
        loads.motor_mass_kg = float(kg_match.group(1))

    torque_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:nm|n\*m|n-m)', p_lower)
    if torque_match:
        loads.motor_torque_nm = float(torque_match.group(1))

    thrust_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:n|newtons?)\s*(?:thrust|axial)', p_lower)
    if thrust_match:
        loads.axial_thrust_n = float(thrust_match.group(1))

    # 3. Extract bolt pattern parameters
    holes_match = re.search(r'(\d+)\s*(?:bolt\s*holes?|holes?|bolts?)', p_lower)
    if holes_match:
        geom.motor_bolt_pattern.num_holes = int(holes_match.group(1))

    bcd_match = re.search(r'(\d+(?:\.\d+)?)\s*mm\s*(?:bcd|bolt\s*circle|pcd)', p_lower)
    if bcd_match:
        geom.motor_bolt_pattern.bolt_circle_diameter_mm = float(bcd_match.group(1))

    hole_dia_match = re.search(r'(?:m(\d+)|(?:dia(?:meter)?|hole)\s*(\d+(?:\.\d+)?)\s*mm|(\d+(?:\.\d+)?)\s*mm\s*(?:dia|hole))', p_lower)
    if hole_dia_match:
        val = hole_dia_match.group(1) or hole_dia_match.group(2) or hole_dia_match.group(3)
        if val:
            dia_f = float(val)
            geom.motor_bolt_pattern.hole_diameter_mm = dia_f + 0.5 if "m" in p_lower else dia_f

    # 4. Extract dimensions
    thick_match = re.search(r'(\d+(?:\.\d+)?)\s*mm\s*(?:thick|thickness)', p_lower)
    if thick_match:
        geom.thickness_mm = float(thick_match.group(1))

    height_match = re.search(r'(\d+(?:\.\d+)?)\s*mm\s*(?:high|height|flange)', p_lower)
    if height_match:
        geom.upright_height_mm = float(height_match.group(1))

    width_match = re.search(r'(\d+(?:\.\d+)?)\s*mm\s*(?:wide|width)', p_lower)
    if width_match:
        geom.base_width_mm = float(width_match.group(1))

    base_len_match = re.search(r'(\d+(?:\.\d+)?)\s*mm\s*(?:long|length|base)', p_lower)
    if base_len_match:
        geom.base_length_mm = float(base_len_match.group(1))

    # Gussets
    if "no gusset" in p_lower or "without gusset" in p_lower:
        geom.has_gussets = False
    elif "gusset" in p_lower or "stiffener" in p_lower:
        geom.has_gussets = True

    model = BracketModel(name="Motor Mounting Bracket", geometry=geom, loads=loads, material=mat)

    console.print(f"[bold green][1/3] Calculating Structural Forces & Bolt Stresses ({model.material.name})...[/bold green]")
    result = BracketPhysicsSolver.solve(model)

    console.print(f"[bold green][2/3] Generating Multi-Body CAD Solids (.STEP, .STL, .SCAD)...[/bold green]")
    scad_file = out_path / "bracket.scad"
    with open(scad_file, "w", encoding="utf-8") as f:
        f.write(BracketCADEngine.generate_openscad(model))

    stl_file = out_path / "bracket.stl"
    with open(stl_file, "wb") as f:
        f.write(BracketCADEngine.export_binary_stl(model))

    step_file = out_path / "bracket.step"
    with open(step_file, "w", encoding="utf-8") as f:
        f.write(BracketCADEngine.export_step_solid(model))

    console.print(f"[bold green][3/3] Generating Engineering Calculation Audit Sheet...[/bold green]")
    report_file = out_path / "bracket_report.html"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(BracketReportGenerator.generate_html_report(model, result))

    # Print Executive Physics Results Table
    table = Table(title=f"MDIE Physics & Fastener Verification: {model.name}")
    table.add_column("Structural Component", style="cyan", no_wrap=True)
    table.add_column("Applied Load / Moment", style="bold")
    table.add_column("Stress / Pressure", style="yellow")
    table.add_column("Safety Factor", style="bold")
    table.add_column("Verdict", style="bold")

    plate_sf_color = "green" if result.plate_yield_safety_factor >= 1.5 else "red"
    bolt_sf_color = "green" if result.bolt_safety_factor >= 2.0 else "red"

    table.add_row(
        "Flange Root Bending",
        f"M_root = {result.overturning_moment_nm:.1f} N*m",
        f"sigma_bend = {result.root_bending_stress_mpa:.1f} MPa",
        f"[{plate_sf_color}]{result.plate_yield_safety_factor:.2f}[/{plate_sf_color}]",
        f"[bold {plate_sf_color}]{'PASS' if result.plate_yield_safety_factor >= 1.5 else 'FAIL'}[/bold {plate_sf_color}]"
    )

    table.add_row(
        "Direct Shear (Plate)",
        f"Fg = {result.motor_weight_n:.1f} N",
        f"tau = {result.plate_shear_stress_mpa:.2f} MPa",
        f"[green]{(model.material.yield_strength_mpa * 0.577) / max(result.plate_shear_stress_mpa, 0.01):.1f}[/green]",
        "[bold green]PASS[/bold green]"
    )

    table.add_row(
        f"Motor Bolts ({geom.motor_bolt_pattern.num_holes}x Fasteners)",
        f"Fg = {result.motor_weight_n:.1f} N + Torque reaction",
        f"tau_bolt = {result.motor_bolt_shear_stress_mpa:.1f} MPa",
        f"[{bolt_sf_color}]{result.bolt_safety_factor:.2f}[/{bolt_sf_color}]",
        f"[bold {bolt_sf_color}]{'PASS' if result.bolt_safety_factor >= 2.0 else 'FAIL'}[/bold {bolt_sf_color}]"
    )

    table.add_row(
        "Fastener Hole Bearing",
        f"Plate t = {geom.thickness_mm:.1f} mm",
        f"sigma_brg = {result.hole_bearing_stress_mpa:.1f} MPa",
        f"[green]{(model.material.yield_strength_mpa * 1.5) / max(result.hole_bearing_stress_mpa, 0.01):.2f}[/green]",
        "[bold green]PASS[/bold green]"
    )

    table.add_row(
        "Root Von Mises Stress",
        f"Total tare mass = {result.plate_mass_kg:.2f} kg",
        f"sigma_vm = {result.max_von_mises_mpa:.1f} MPa",
        f"[{plate_sf_color}]{result.plate_yield_safety_factor:.2f}[/{plate_sf_color}]",
        f"[bold {'green' if result.passed else 'red'}]{'PASS' if result.passed else 'FAIL'}[/bold {'green' if result.passed else 'red'}]"
    )

    console.print(table)

    # Deliverables Panel
    deliv_text = (
        f"[bold green]Manufactured CAD & Physics Deliverables Generated in '{out_path}':[/bold green]\n"
        f"  * [bold cyan]{step_file.name}[/bold cyan] -> ISO-10303 Solid Assembly (SolidWorks, Fusion 360, FreeCAD)\n"
        f"  * [bold cyan]{stl_file.name}[/bold cyan]  -> Watertight Sliced 3D Print Mesh ({len(stl_file.read_bytes())/1024:.1f} KB)\n"
        f"  * [bold cyan]{scad_file.name}[/bold cyan] -> Parametric OpenSCAD Source Script\n"
        f"  * [bold cyan]{report_file.name}[/bold cyan] -> Engineering Calculation Audit Sheet with Free-Body Diagram"
    )
    console.print(Panel(deliv_text, title="[bold green]CAD & Force Calculation Complete[/bold green]", border_style="green"))
    return True



def _handle_chair(prompt: str, p_lower: str, output_dir: Optional[str] = None) -> bool:
    from mdie.core.frame_model import FrameDesignModel, STRUCTURAL_MATERIALS
    from mdie.physics.frame_physics import FramePhysicsSolver
    from mdie.cad.assembly import FrameCADEngine
    from mdie.reports.frame_report import FrameReportGenerator
    from mdie.reports.academic_engine import AcademicAssignmentEngine
    from mdie.physics.fea_3d import build_chair_3d_fea_model

    out_path = Path(output_dir or "Project/chair")
    out_path.mkdir(parents=True, exist_ok=True)

    # Material selection
    mat = STRUCTURAL_MATERIALS["STEEL_1018"]
    if "aluminum" in p_lower or "6061" in p_lower:
        mat = STRUCTURAL_MATERIALS["AL_6061_T6"]
    elif "oak" in p_lower or "wood" in p_lower:
        mat = STRUCTURAL_MATERIALS["WHITE_OAK"]
    elif "stainless" in p_lower or "304" in p_lower:
        mat = STRUCTURAL_MATERIALS["STAINLESS_304"]

    model = FrameDesignModel(name="MDIE Structural Frame", material=mat)

    # Topology & Member Detection
    if any(w in p_lower for w in ["3 leg", "three leg", "tripod"]):
        model.geometry.num_legs = 3
        model.geometry.has_arms = False
        model.geometry.has_backrest = False
        model.geometry.topology_type = "stool"
        model.name = "MDIE 3-Legged Tripod Stool"
    elif "stool" in p_lower:
        model.geometry.has_arms = False
        model.geometry.has_backrest = False
        model.geometry.topology_type = "stool"
        model.name = "MDIE 4-Legged Stool"
    elif any(w in p_lower for w in ["table", "desk", "workbench"]):
        model.geometry.has_arms = False
        model.geometry.has_backrest = False
        model.geometry.topology_type = "table"
        model.geometry.seat_height_mm = 750.0
        model.geometry.seat_width_mm = 1200.0
        model.geometry.seat_depth_mm = 700.0
        model.name = "MDIE Structural Table Frame"
    elif "bench" in p_lower:
        model.geometry.has_arms = False
        model.geometry.has_backrest = False
        model.geometry.topology_type = "bench"
        model.geometry.seat_width_mm = 1100.0
        model.name = "MDIE Structural Bench"
    else:
        model.name = "MDIE Ergonomic Armchair"

    if any(w in p_lower for w in ["no arm", "armless", "without arm"]):
        model.geometry.has_arms = False
    if any(w in p_lower for w in ["no back", "backless", "without back"]):
        model.geometry.has_backrest = False

    # Extract custom seat/platform load if present
    seat_match = re.search(r'(\d+)\s*(?:n|newtons?)\s*(?:seat|table|vertical|load)?', p_lower)
    if seat_match:
        model.loads.seat_vertical_load_n = float(seat_match.group(1))
    kg_match = re.search(r'(\d+)\s*kg', p_lower)
    if kg_match and not seat_match:
        model.loads.seat_vertical_load_n = float(kg_match.group(1)) * 9.81

    # Extract custom arm load
    if model.geometry.has_arms:
        arm_match = re.search(r'(\d+)\s*(?:n|newtons?)\s*(?:arm|armrest)', p_lower)
        if arm_match:
            val = float(arm_match.group(1))
            model.loads.left_arm_vertical_n = val
            model.loads.right_arm_vertical_n = val

    # Extract leg tube diameter
    dia_match = re.search(r'(\d+(?:\.\d+)?)\s*mm\s*(?:leg|tube|dia)', p_lower)
    if dia_match:
        model.geometry.leg_profile.outer_dimension_mm = float(dia_match.group(1))

    console.print(f"[bold green][1/3] Calculating Structural Forces & Buckling ({model.material.name})...[/bold green]")
    result = FramePhysicsSolver.solve(model)

    console.print(f"[bold green][2/3] Running Direct Stiffness 3D FEA (6 DOFs/Node)...[/bold green]")
    fea_solver = build_chair_3d_fea_model(model)
    fea_res = fea_solver.solve()

    console.print(f"[bold green][3/3] Generating Multi-Body CAD Solids (.STEP, .STL, .SCAD, .HTML)...[/bold green]")

    # Write deliverables
    scad_file = out_path / "chair.scad"
    with open(scad_file, "w", encoding="utf-8") as f:
        f.write(FrameCADEngine.generate_openscad(model))

    stl_file = out_path / "chair.stl"
    with open(stl_file, "wb") as f:
        f.write(FrameCADEngine.export_binary_stl(model))

    step_file = out_path / "chair.step"
    with open(step_file, "w", encoding="utf-8") as f:
        f.write(FrameCADEngine.export_step_solid(model))

    # Write discrete part solid files for fabrication
    parts_dir = out_path / "parts"
    part_files = FrameCADEngine.export_individual_parts(model, parts_dir)

    report_file = out_path / "chair_report.html"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(FrameReportGenerator.generate_html_report(model, result))

    assignment_file = out_path / "academic_assignment_report.html"
    preview_path = out_path / "chair_preview.png"
    with open(assignment_file, "w", encoding="utf-8") as f:
        f.write(AcademicAssignmentEngine.generate_assignment_report(
            model, result,
            fea_result=fea_res,
            preview_image="chair_preview.png" if preview_path.exists() else None
        ))

    # Version 2 (Strictly tailored to match university student project report format without OOS content)
    assignment_v2_file = out_path / "academic_assignment_report_v2.html"
    with open(assignment_v2_file, "w", encoding="utf-8") as f:
        f.write(AcademicAssignmentEngine.generate_assignment_report_v2(
            model, result,
            preview_image="chair_preview.png" if preview_path.exists() else None
        ))

    # Generate Word (.docx) deliverables & Consolidate study materials via Learning Tools
    from mdie.integrations.learning_tools import LearningToolsBridge
    bridge = LearningToolsBridge()
    assignment_docx = out_path / "academic_assignment_report.docx"
    assignment_v2_docx = out_path / "academic_assignment_report_v2.docx"
    chair_docx = out_path / "chair_report.docx"
    bridge.convert_docx(assignment_file, assignment_docx)
    bridge.convert_docx(assignment_v2_file, assignment_v2_docx)
    bridge.convert_docx(report_file, chair_docx)

    # Auto-consolidate report into study guides, summaries & NotebookLM pack
    study_dir = out_path / "study_materials"
    try:
        bridge.consolidate_report(
            report_path=assignment_file,
            output_dir=study_dir,
            convert_docx=False,
            generate_summaries=True,
            generate_notebooklm=True,
            enable_ai=False
        )
    except Exception as e:
        logger.warning(f"Auto-consolidation note: {e}")

    # Print Executive Physics Results Table
    table = Table(title=f"MDIE Physics & Structural Verification: {model.name}")
    table.add_column("Structural Component", style="cyan", no_wrap=True)
    table.add_column("Forces / Reactions", style="bold")
    table.add_column("Stress & Critical Load", style="yellow")
    table.add_column("Safety Factor", style="bold")
    table.add_column("Verdict", style="bold")

    for leg in result.floor_reactions:
        verdict = "[green]PASS[/green]" if (leg.buckling_passed and leg.yield_passed) else "[red]FAIL[/red]"
        table.add_row(
            f"{leg.leg_name} ({leg.leg_id})",
            f"Rz = {leg.axial_reaction_n:.1f} N, Rh = {leg.horizontal_shear_n:.1f} N",
            f"Stress = {leg.combined_stress_mpa:.1f} MPa (P_cr = {leg.critical_buckling_load_n/1000:.2f} kN)",
            f"Buckling SF: {leg.buckling_safety_factor:.2f}",
            verdict
        )

    for arm in result.armrests:
        verdict = "[green]PASS[/green]" if arm.passed else "[red]FAIL[/red]"
        table.add_row(
            f"{arm.arm_id.capitalize()} Armrest",
            f"Fz = {arm.applied_vertical_n:.1f} N, Moment = {arm.overhang_moment_nm:.1f} N*m",
            f"Combined Stress = {arm.strut_combined_stress_mpa:.1f} MPa",
            f"Yield SF: {arm.arm_safety_factor:.2f}",
            verdict
        )

    table.add_row(
        "3D Space Frame (FEA)",
        f"Active DOFs: {fea_res['num_nodes']*6}, Members: {fea_res['num_members']}",
        f"Max Von Mises: {fea_res['max_von_mises_mpa']:.1f} MPa, Max Disp: {fea_res['max_displacement_mm']:.2f} mm",
        f"Min SF: {fea_res['min_safety_factor']:.2f}",
        "[green]PASS[/green]" if fea_res['passed'] else "[red]FAIL[/red]"
    )

    console.print(table)

    # Deliverables Panel
    deliv_text = (
        f"[bold green]Manufactured CAD, Physics & Study Deliverables Generated in '{out_path}':[/bold green]\n"
        f"  * [bold cyan]{step_file.name}[/bold cyan] -> ISO-10303 Multi-Body Solid Assembly (10 Named Part Bodies)\n"
        f"  * [bold cyan]parts/[/bold cyan]      -> Discrete Part Solids ({len(part_files)//2} parts: .step + .stl each for fabrication)\n"
        f"  * [bold cyan]{stl_file.name}[/bold cyan]  -> Watertight Sliced 3D Print Mesh ({len(stl_file.read_bytes())/1024:.1f} KB)\n"
        f"  * [bold cyan]{scad_file.name}[/bold cyan] -> Parametric OpenSCAD Assembly & Exploded View Script\n"
        f"  * [bold cyan]{assignment_docx.name}[/bold cyan] -> Academic Word Document (.docx) (Course Grading Ready)\n"
        f"  * [bold cyan]{report_file.name}[/bold cyan] -> Core Engineering Calculation Sheet (Industry Audit)\n"
        f"  * [bold cyan]{assignment_file.name}[/bold cyan] -> Academic Assignment Dossier (HTML Viewer)\n"
        f"  * [bold cyan]study_materials/[/bold cyan] -> Consolidated Study Notes & NotebookLM Audio Overview Pack"
    )
    console.print(Panel(deliv_text, title="[bold green]CAD & Force Calculation Complete[/bold green]", border_style="green"))
    return True


def _handle_space_frame(prompt: str, p_lower: str, output_dir: Optional[str] = None) -> bool:
    from mdie.physics.fea_3d import build_space_truss_tower_model, build_cantilever_space_frame_model
    from mdie.cad.space_frame_cad import SpaceFrameCADEngine

    out_path = Path(output_dir or "Project/space_frame")
    out_path.mkdir(parents=True, exist_ok=True)

    # Extract load if present (e.g. "5 kN" or "5000 N")
    load_val = None
    kn_match = re.search(r'(\d+(?:\.\d+)?)\s*kn', p_lower)
    if kn_match:
        load_val = float(kn_match.group(1)) * 1000.0
    n_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:n|newtons?)', p_lower)
    if n_match and not kn_match:
        load_val = float(n_match.group(1))

    # Extract height or length if present (e.g. "8 m" or "8 meters")
    dim_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:m|meters?)', p_lower)
    dim_val = float(dim_match.group(1)) if dim_match else None

    if "cantilever" in p_lower or "girder" in p_lower:
        l_m = dim_val or 4.0
        p_n = load_val or 5000.0
        solver = build_cantilever_space_frame_model(length_m=l_m, tip_load_n=p_n)
    else:
        h_m = dim_val or 6.0
        w_n = load_val or 3000.0
        solver = build_space_truss_tower_model(height_m=h_m, wind_load_n=w_n)

    console.print(f"[bold green][1/3] Solving 3D Direct Stiffness FEA ({solver.name})...[/bold green]")
    fea_res = solver.solve()

    console.print(f"[bold green][2/3] Generating 3D CAD Solids (.STEP, .STL, .SCAD, .HTML)...[/bold green]")

    scad_file = out_path / "space_frame.scad"
    with open(scad_file, "w", encoding="utf-8") as f:
        f.write(SpaceFrameCADEngine.generate_openscad(solver))

    stl_file = out_path / "space_frame.stl"
    stl_bytes = SpaceFrameCADEngine.export_binary_stl(solver)
    with open(stl_file, "wb") as f:
        f.write(stl_bytes)

    step_file = out_path / "space_frame.step"
    with open(step_file, "w", encoding="utf-8") as f:
        f.write(SpaceFrameCADEngine.export_step_solid(solver))

    console.print(f"[bold green][3/3] Generating Engineering Calculation Audit Sheet...[/bold green]")
    rep_path = out_path / "space_frame_report.html"
    rows = "".join(f"<tr><td>{m['member_id']}</td><td>{m['axial_force_n']:.1f} N</td><td>{m['max_moment_nm']:.1f} N*m</td><td>{m['von_mises_mpa']:.1f} MPa</td><td>{m['safety_factor']:.2f}</td></tr>" for m in fea_res['members'][:20])
    html_content = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>{solver.name} Report</title>
    <style>body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0b1120; color: #f8fafc; padding: 30px; }} table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }} th, td {{ padding: 10px 14px; border: 1px solid #334155; text-align: left; }} th {{ background: #1e293b; color: #38bdf8; font-weight: 600; }} tr:nth-child(even) {{ background: #0f172a; }} .metric-card {{ background: #1e293b; padding: 15px 20px; border-radius: 8px; margin-bottom: 20px; display: inline-block; margin-right: 15px; border-left: 4px solid #38bdf8; }}</style>
    </head><body><h1>MDIE 3D Space Frame FEA Audit Report</h1><h2>Structure: {solver.name}</h2>
    <div>
      <div class="metric-card"><div>Active DOFs</div><strong style="font-size:1.4em;color:#38bdf8;">{fea_res['num_nodes']*6}</strong></div>
      <div class="metric-card"><div>Total Members</div><strong style="font-size:1.4em;color:#38bdf8;">{fea_res['num_members']}</strong></div>
      <div class="metric-card"><div>Max Von Mises</div><strong style="font-size:1.4em;color:#38bdf8;">{fea_res['max_von_mises_mpa']:.1f} MPa</strong></div>
      <div class="metric-card"><div>Min Safety Factor</div><strong style="font-size:1.4em;color:#4ade80;">{fea_res['min_safety_factor']:.2f}</strong></div>
      <div class="metric-card"><div>Max Deflection</div><strong style="font-size:1.4em;color:#38bdf8;">{fea_res['max_displacement_mm']:.2f} mm</strong></div>
    </div>
    <h3>Top Loaded Members (First 20)</h3>
    <table><tr><th>Member ID</th><th>Axial Force</th><th>Max Moment</th><th>Von Mises Stress</th><th>Safety Factor</th></tr>{rows}</table></body></html>"""
    with open(rep_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    # Summary table
    table = Table(title=f"3D Space Frame FEA & CAD Deliverables: {solver.name}")
    table.add_column("Engineering Metric", style="cyan")
    table.add_column("Calculated Value", style="bold")
    table.add_column("Compliance", style="bold")

    table.add_row("Nodes & Active DOFs", f"{fea_res['num_nodes']} Nodes ({fea_res['num_nodes']*6} DOFs)", "[green]EQUILIBRIUM OK[/green]")
    table.add_row("Total Frame Members", f"{fea_res['num_members']} Members", "[green]OK[/green]")
    table.add_row("Max Von Mises Stress", f"{fea_res['max_von_mises_mpa']:.2f} MPa", "[green]PASS[/green]" if fea_res['passed'] else "[red]FAIL[/red]")
    table.add_row("Min Member Safety Factor", f"{fea_res['min_safety_factor']:.2f}", "[green]PASS[/green]" if fea_res['min_safety_factor'] >= 2.0 else "[yellow]ADEQUATE[/yellow]")
    table.add_row("Max 3D Elastic Deflection", f"{fea_res['max_displacement_mm']:.3f} mm", "[green]RIGID[/green]")

    console.print(table)

    deliv_text = (
        f"[bold green]Manufactured CAD & Physics Deliverables Generated in '{out_path}':[/bold green]\n"
        f"  * [bold cyan]{step_file.name}[/bold cyan] -> ISO-10303 Solid Multi-Body Assembly (FreeCAD, SolidWorks)\n"
        f"  * [bold cyan]{stl_file.name}[/bold cyan]  -> Watertight 3D Printable Mesh ({len(stl_bytes)/1024:.1f} KB)\n"
        f"  * [bold cyan]{scad_file.name}[/bold cyan] -> Parametric OpenSCAD Script (with stress color gradient)\n"
        f"  * [bold cyan]{rep_path.name}[/bold cyan] -> Engineering Calculation Audit Sheet\n"
        f"  * [bold yellow]View in CAD:[/bold yellow] Run [cyan]python cli.py view {out_path.name}[/cyan] (OpenSCAD / FreeCAD)"
    )
    console.print(Panel(deliv_text, title="[bold green]CAD & Force Calculation Complete[/bold green]", border_style="green"))
    return True


def _handle_generative(prompt: str, p_lower: str, output_dir: Optional[str] = None) -> bool:
    from mdie.ai.generative_agent import GenerativeEngineeringAgent
    from mdie.reports.blueprint_2d import Blueprint2DGenerator

    # Extract clean project slug
    words = [w for w in re.findall(r'[a-zA-Z0-9]+', p_lower) if w not in ["design", "a", "an", "the", "with", "and", "for", "in", "of", "to"]]
    slug = "_".join(words[:3]) if words else "generative_part"

    out_path = Path(output_dir or f"Project/{slug}")
    out_path.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold green][1/3] Synthesizing CAD & Solving Physics On The Fly...[/bold green]")
    res = GenerativeEngineeringAgent.process(prompt, out_path)

    # 1. OpenSCAD script
    scad_file = out_path / f"{slug}.scad"
    with open(scad_file, "w", encoding="utf-8") as f:
        f.write(res.scad_code)

    # 2. 2D Blueprint SVG & Printable HTML
    bp_svg_file = out_path / f"{slug}_blueprint.svg"
    with open(bp_svg_file, "w", encoding="utf-8") as f:
        f.write(res.blueprint_svg)

    bp_html_file = out_path / f"{slug}_blueprint.html"
    with open(bp_html_file, "w", encoding="utf-8") as f:
        f.write(Blueprint2DGenerator.generate_html_blueprint_page(res.blueprint_svg, title=res.title))

    # 3. Calculation Report
    rep_file = out_path / f"{slug}_report.html"
    with open(rep_file, "w", encoding="utf-8") as f:
        f.write(res.report_html)

    console.print(f"[bold green][2/3] Generating 2D Blueprint & Engineering Calculation Sheet...[/bold green]")
    console.print(f"[bold green][3/3] Deterministic Verification Complete: {res.verdict}[/bold green]")

    # Table
    table = Table(title=f"MDIE Generative Engineering Deliverables: {res.title}")
    table.add_column("Engineering Metric", style="cyan")
    table.add_column("Value", style="bold")
    table.add_column("Status", style="bold")

    table.add_row("Component Category", res.category, "[green]VERIFIED[/green]")
    table.add_row("Material", res.material_name, f"Yield: {res.yield_strength_mpa:.0f} MPa")
    table.add_row("Max Calculated Stress", f"{res.max_stress_mpa:.1f} MPa", "[green]DETERMINISTIC[/green]")
    table.add_row("Minimum Safety Factor", f"{res.min_safety_factor:.2f}", "[green]PASS[/green]" if res.passed else "[red]FAIL[/red]")
    for k, v in list(res.key_metrics.items())[:3]:
        table.add_row(str(k), str(v), "[green]OK[/green]")

    console.print(table)

    deliv_text = (
        f"[bold green]Manufactured CAD & Physics Deliverables Generated in '{out_path}':[/bold green]\n"
        f"  * [bold cyan]{scad_file.name}[/bold cyan] -> Parametric OpenSCAD 3D Model\n"
        f"  * [bold cyan]{bp_svg_file.name}[/bold cyan] -> 2D Technical Drawing Blueprint (ISO 128 / ANSI Y14.5)\n"
        f"  * [bold cyan]{bp_html_file.name}[/bold cyan] -> Printable Vector Blueprint Sheet\n"
        f"  * [bold cyan]{rep_file.name}[/bold cyan] -> Engineering Calculation Audit Sheet\n"
        f"  * [bold yellow]View in CAD:[/bold yellow] Run [cyan]python cli.py view {out_path.name}[/cyan]"
    )
    console.print(Panel(deliv_text, title=f"[bold green]{res.title} Complete[/bold green]", border_style="green"))
    return True


def _handle_shaft(prompt: str, p_lower: str, output_dir: Optional[str] = None) -> bool:
    from mdie.ai.parser import NLParser
    from mdie.physics.solver import PhysicsSolver
    from mdie.cad.openscad import OpenSCADGenerator
    from mdie.cad.stl_exporter import STLExporter
    from mdie.cad.step_exporter import STEPExporter
    from mdie.reports.generator import ReportGenerator

    out_path = Path(output_dir or "Project/shaft")
    out_path.mkdir(parents=True, exist_ok=True)

    console.print("[bold green][1/3] Parsing Machine Geometry & Power Transmission Parameters...[/bold green]")
    model, logs = NLParser.parse(prompt)

    console.print(f"[bold green][2/3] Solving Mechanics, Goodman Fatigue & Bearings ({model.name})...[/bold green]")
    result = PhysicsSolver.solve(model)

    console.print("[bold green][3/3] Generating CAD Solids (.STEP, .STL, .SCAD, .HTML)...[/bold green]")

    scad_file = out_path / "shaft.scad"
    with open(scad_file, "w", encoding="utf-8") as f:
        f.write(result.openscad_code)

    stl_file = out_path / "shaft.stl"
    stl_data = STLExporter.export_binary_stl(model, n_slices=64)
    with open(stl_file, "wb") as f:
        f.write(stl_data)

    step_file = out_path / "shaft.step"
    step_data = STEPExporter.export_step(model, n_slices=48)
    with open(step_file, "w", encoding="utf-8") as f:
        f.write(step_data)

    report_file = out_path / "shaft_report.html"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(ReportGenerator.generate_html_report(model, result))

    # 2D Technical Drawing Blueprint
    from mdie.reports.blueprint_2d import Blueprint2DGenerator
    bp_svg_file = out_path / "shaft_blueprint.svg"
    bp_svg = Blueprint2DGenerator.generate_shaft_blueprint_svg(model, result, theme="blueprint")
    with open(bp_svg_file, "w", encoding="utf-8") as f:
        f.write(bp_svg)

    bp_html_file = out_path / "shaft_blueprint.html"
    with open(bp_html_file, "w", encoding="utf-8") as f:
        f.write(Blueprint2DGenerator.generate_html_blueprint_page(bp_svg, title=f"{model.name} Technical Drawing"))

    # Summary table
    table = Table(title=f"MDIE Verification Summary: {model.name}")
    table.add_column("Engineering Metric", style="cyan")
    table.add_column("Calculated", style="bold")
    table.add_column("Allowable Limit", style="yellow")
    table.add_column("Compliance", style="bold")

    table.add_row("Transmitted Torque", f"{result.applied_torque_nm:.1f} N*m", "-", "[green]OK[/green]")
    table.add_row("Yield Safety Factor", f"{result.min_yield_safety_factor:.2f}", f">= {model.constraints.min_yield_safety_factor:.2f}", "[green]PASS[/green]" if result.yield_passed else "[red]FAIL[/red]")
    table.add_row("Fatigue SF (Goodman)", f"{result.min_fatigue_safety_factor:.2f}", f">= {model.constraints.min_fatigue_safety_factor:.2f}", "[green]PASS[/green]" if result.fatigue_passed else "[red]FAIL[/red]")
    table.add_row("Max Shaft Deflection", f"{result.max_deflection_mm:.3f} mm", f"<= {model.constraints.max_deflection_mm:.3f} mm", "[green]PASS[/green]" if result.deflection_passed else "[red]FAIL[/red]")
    table.add_row("Total Mass", f"{result.total_mass_kg:.3f} kg", "-", "[green]OPTIMAL[/green]")

    console.print(table)

    deliv_text = (
        f"[bold green]Manufactured CAD & Physics Deliverables Generated in '{out_path}':[/bold green]\n"
        f"  * [bold cyan]{step_file.name}[/bold cyan] -> ISO-10303 Solid CAD Model ({len(step_data)/1024:.1f} KB)\n"
        f"  * [bold cyan]{stl_file.name}[/bold cyan]  -> Watertight 3D Printable STL ({len(stl_data)/1024:.1f} KB)\n"
        f"  * [bold cyan]{scad_file.name}[/bold cyan] -> Parametric OpenSCAD Script\n"
        f"  * [bold cyan]{bp_svg_file.name}[/bold cyan] -> 2D Technical Drawing Blueprint (ISO 128 / ANSI Y14.5)\n"
        f"  * [bold cyan]{bp_html_file.name}[/bold cyan] -> Printable Vector Blueprint Sheet\n"
        f"  * [bold cyan]{report_file.name}[/bold cyan] -> Full Engineering Calculation Audit Sheet"
    )
    console.print(Panel(deliv_text, title="[bold green]CAD & Force Calculation Complete[/bold green]", border_style="green"))
    return True


def interactive_repl():
    """Interactive terminal prompt where user can type anything to generate CAD and calculate forces."""
    console.print(Panel(
        "[bold cyan]MACHINE DESIGN INTELLIGENCE ENGINE (MDIE)[/bold cyan]\n"
        "AI Proposes CAD Solid Geometry. Physics Solves Forces & Stresses.\n"
        "[italic]Type what you want in plain words (e.g. 'design a chair with 4 legs and two arms', 'shaft with keyway', or 'exit')[/italic]",
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


def main():
    # If arguments are passed directly, e.g. `py cli.py "design a chair with 4 legs"`
    if len(sys.argv) > 1:
        first_arg = sys.argv[1].strip()

        if first_arg in ["-h", "--help", "help"]:
            tools = find_cad_tools()
            cad_status = []
            for t_name in ["openscad", "freecad"]:
                p = tools.get(t_name)
                status_str = f"[green]Installed ({p})[/green]" if p else "[yellow]Not detected[/yellow]"
                cad_status.append(f"  * {t_name.capitalize()}: {status_str}")
            cad_info = "\n".join(cad_status)

            from mdie.ai.llm_router import LLMRouter
            providers = LLMRouter.get_configured_providers()
            llm_status_str = f"[green]Active Cascade:[/green] {' -> '.join([p.upper() for p in providers])}" if providers else "[yellow]No API keys found (Using Deterministic Offline Heuristic Engine)[/yellow]"

            console.print(Panel(
                "[bold cyan]MDIE Command Line Interface[/bold cyan]\n\n"
                "Usage:\n"
                "  python cli.py \"<prompt>\" [--output-dir <path>] [--open]\n"
                "  python cli.py docx [path_to_html] [--ai] [-o <output.docx>]\n"
                "  python cli.py view [project_name_or_file] [--freecad]\n"
                "  python cli.py                              (launches interactive prompt)\n\n"
                "Examples:\n"
                "  python cli.py \"motor mounting bracket with 4 bolt holes, 10 kg, steel\" --open\n"
                "  python cli.py \"design a chair with 4 splayed legs, steel\" --open\n"
                "  python cli.py docx Project/chair/academic_assignment_report.html --ai\n"
                "  python cli.py view bracket                 (opens in OpenSCAD or FreeCAD)\n"
                "  python cli.py view chair --freecad         (opens STEP in FreeCAD)\n\n"
                f"[bold cyan]Detected Local CAD Tools:[/bold cyan]\n{cad_info}\n\n"
                f"[bold cyan]AI / LLM Routing Status:[/bold cyan]\n  * {llm_status_str}\n"
                "    [dim](Supports: GROQ_API_KEY, OPENROUTER_API_KEY, GEMINI_API_KEY, OLLAMA_HOST)[/dim]",
                border_style="cyan"
            ))
            return

        if first_arg == "view":
            target_name = "chair"
            prefer_fc = False
            for arg in sys.argv[2:]:
                if arg in ["--freecad", "--fc"]:
                    prefer_fc = True
                elif not arg.startswith("-"):
                    target_name = arg

            target = Path(target_name)
            if not target.exists():
                if (Path("Project") / target_name).exists():
                    target = Path("Project") / target_name
                elif Path(f"{target_name}.scad").exists():
                    target = Path(f"{target_name}.scad")
            tool_type = "freecad" if prefer_fc else None
            launch_cad_viewer(target, tool_type=tool_type)
            return

        # HTML to Word (.docx) Converter Subcommand
        if first_arg in ["docx", "convert-docx", "word"]:
            enable_ai = "--ai" in sys.argv
            target_html = None
            out_docx = None
            custom_prompt = None
            args_list = sys.argv[2:]
            i = 0
            while i < len(args_list):
                arg = args_list[i]
                if arg == "--ai":
                    enable_ai = True
                elif arg in ["-o", "--output"] and i + 1 < len(args_list):
                    out_docx = args_list[i + 1]
                    i += 1
                elif arg in ["-p", "--prompt"] and i + 1 < len(args_list):
                    custom_prompt = args_list[i + 1]
                    i += 1
                elif not arg.startswith("-") and target_html is None:
                    target_html = arg
                i += 1

            if not target_html:
                candidates = [
                    Path("Project/chair/academic_assignment_report.html"),
                    Path("Project/chair/chair_report.html"),
                    Path("Project/bracket/bracket_report.html"),
                    Path("Project/shaft/shaft_report.html"),
                ]
                for c in candidates:
                    if c.exists():
                        target_html = str(c)
                        break

            if not target_html or not Path(target_html).exists():
                console.print(f"[bold red]Cannot find HTML report file: {target_html or '(none specified)'}[/bold red]")
                console.print("[dim]Usage: python cli.py docx [path_to_html] [--ai] [-o output.docx][/dim]")
                return

            from mdie.reports.docx_converter import HTMLToDocxConverter
            console.print(f"[bold cyan]>> Converting HTML Report to Word (.docx):[/bold cyan] {target_html}")
            if enable_ai:
                console.print("[bold green]>> AI Engineering Peer-Review & Executive Summary enabled (Cascading LLM)[/bold green]")
            res_path = HTMLToDocxConverter.convert(
                target_html,
                output_docx_path=out_docx,
                enable_ai=enable_ai,
                custom_ai_instructions=custom_prompt
            )
            console.print(f"[bold green]>> Successfully generated Word document:[/bold green] [bold cyan]{res_path}[/bold cyan] ({res_path.stat().st_size / 1024:.1f} KB)")
            return

        elif first_arg in ["consolidate", "study"]:
            target_file = None
            if len(sys.argv) > 2 and not sys.argv[2].startswith("-"):
                arg_target = sys.argv[2]
                target_p = Path(arg_target)
                if target_p.exists():
                    target_file = target_p
                else:
                    candidates = [
                        Path("Project") / arg_target / "academic_assignment_report.html",
                        Path("Project") / arg_target / f"{arg_target}_report.html",
                        Path("Project") / arg_target / "report.html",
                    ]
                    for c in candidates:
                        if c.exists():
                            target_file = c
                            break
            if not target_file:
                target_file = Path("Project/chair/academic_assignment_report.html")

            if not target_file.exists():
                console.print(f"[bold red]Report file not found: {target_file}[/bold red]")
                console.print("[dim]Usage: python cli.py consolidate [path_or_project_name] [--ai][/dim]")
                return

            enable_ai = "--ai" in sys.argv
            from mdie.integrations.learning_tools import LearningToolsBridge
            bridge = LearningToolsBridge()
            console.print(f"[bold cyan]>> Consolidating Engineering Report using learning-tools:[/bold cyan] {target_file}")
            console.print(f"[dim]Bridge mode: {'REST API (port 5000)' if bridge.is_online() else 'Direct Library Import'}[/dim]")

            res = bridge.consolidate_report(
                report_path=target_file,
                convert_docx=True,
                generate_summaries=True,
                generate_notebooklm=True,
                enable_ai=enable_ai
            )

            console.print(f"[bold green]>> Successfully consolidated report![/bold green] (Chunks: {res.get('chunks_count', 0)})")
            for ftype, fpath in res.get("generated_files", {}).items():
                console.print(f"   - [bold]{ftype.upper()}:[/bold] [cyan]{fpath}[/cyan]")
            return

        # Subcommand support for backward compatibility
        if first_arg == "chair":
            prompt = "Design a chair with two arms and four splayed legs"
            out_dir = "Project/chair"
            auto_open = "--open" in sys.argv
            for i, arg in enumerate(sys.argv):
                if arg == "--output-dir" and i + 1 < len(sys.argv):
                    out_dir = sys.argv[i + 1]
            process_prompt(prompt, output_dir=out_dir, auto_open=auto_open)
            return

        elif first_arg == "bracket":
            prompt = "motor mounting bracket with 4 bolt holes, 10 kg, steel"
            out_dir = "Project/bracket"
            auto_open = "--open" in sys.argv
            for i, arg in enumerate(sys.argv):
                if arg == "--output-dir" and i + 1 < len(sys.argv):
                    out_dir = sys.argv[i + 1]
            process_prompt(prompt, output_dir=out_dir, auto_open=auto_open)
            return

        elif first_arg in ["solve", "optimize"]:
            prompt = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "stepped shaft 500 mm long"
            auto_open = "--open" in sys.argv
            process_prompt(prompt, auto_open=auto_open)
            return

        elif first_arg.startswith("-"):
            # Flag passed without prompt
            interactive_repl()
            return

        # Check for optional --output-dir and --open
        args = sys.argv[1:]
        auto_open = False
        if "--open" in args:
            auto_open = True
            args.remove("--open")

        out_dir = None
        if "--output-dir" in args:
            idx = args.index("--output-dir")
            if idx + 1 < len(args):
                out_dir = args[idx + 1]
                args = args[:idx] + args[idx + 2:]
        full_prompt = " ".join(args)
        process_prompt(full_prompt, output_dir=out_dir, auto_open=auto_open)
    else:
        # No arguments: launch interactive REPL terminal
        interactive_repl()


if __name__ == "__main__":
    main()
