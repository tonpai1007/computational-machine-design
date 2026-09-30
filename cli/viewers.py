"""Locate and launch local CAD viewers (OpenSCAD, FreeCAD)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from rich.console import Console

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
