"""
Diagram Generation for DOCX Reports
Generates SVG diagrams and converts to PNG for embedding in Word documents.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from core.models import SolverResult


def generate_svg_diagram(
    x_vals: list[float],
    y_vals: list[float],
    title: str,
    y_label: str,
    stroke_color: str = "#2563eb",
    fill_color: str = "rgba(37, 99, 235, 0.15)",
    width: int = 680,
    height: int = 180,
) -> str:
    """Generate clean, scalable SVG diagram for internal force/moment/stress curves."""
    if not x_vals or not y_vals or len(x_vals) != len(y_vals):
        return f'<div class="diagram-error">No data for {title}</div>'

    padding = 45
    plot_w = width - 2 * padding
    plot_h = height - 2 * padding

    min_x, max_x = min(x_vals), max(x_vals)
    min_y, max_y = min(y_vals), max(y_vals)

    # Ensure 0 line is visible
    min_y = min(min_y, 0.0)
    max_y = max(max_y, 0.0)
    span_y = max_y - min_y
    if span_y < 1e-9:
        span_y = 1.0
    span_x = max_x - min_x
    if span_x < 1e-9:
        span_x = 1.0

    def map_x(x: float) -> float:
        return padding + ((x - min_x) / span_x) * plot_w

    def map_y(y: float) -> float:
        return padding + plot_h - ((y - min_y) / span_y) * plot_h

    zero_y = map_y(0.0)

    points = []
    for x, y in zip(x_vals, y_vals, strict=True):
        points.append(f"{map_x(x):.1f},{map_y(y):.1f}")
    polyline_pts = " ".join(points)

    polygon_pts = (
        f"{map_x(min_x):.1f},{zero_y:.1f} " + polyline_pts + f" {map_x(max_x):.1f},{zero_y:.1f}"
    )

    svg = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">',
        f'  <rect width="{width}" height="{height}" fill="#f8fafc" stroke="#e2e8f0" stroke-width="1" rx="4" />',
        f'  <text x="{padding}" y="22" fill="#0f172a" font-size="12" font-family="sans-serif" font-weight="bold">{html.escape(title)}</text>',
        "  <!-- Zero Baseline -->",
        f'  <line x1="{padding}" y1="{zero_y:.1f}" x2="{width - padding}" y2="{zero_y:.1f}" stroke="#94a3b8" stroke-dasharray="3,3" stroke-width="1" />',
        "  <!-- Y-Axis labels -->",
        f'  <text x="{padding - 8}" y="{map_y(max_y):.1f}" fill="#475569" font-size="10" text-anchor="end">{max_y:.1f}</text>',
        f'  <text x="{padding - 8}" y="{zero_y + 3:.1f}" fill="#475569" font-size="10" text-anchor="end">0.0</text>',
        f'  <text x="{padding - 8}" y="{map_y(min_y):.1f}" fill="#475569" font-size="10" text-anchor="end">{min_y:.1f}</text>',
        "  <!-- Filled Area -->",
        f'  <polygon points="{polygon_pts}" fill="{fill_color}" />',
        "  <!-- Curve Line -->",
        f'  <polyline points="{polyline_pts}" fill="none" stroke="{stroke_color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />',
        "  <!-- X-Axis Labels -->",
        f'  <text x="{padding}" y="{height - 8}" fill="#475569" font-size="10">x = {min_x * 1000:.0f} mm</text>',
        f'  <text x="{width - padding}" y="{height - 8}" fill="#475569" font-size="10" text-anchor="end">x = {max_x * 1000:.0f} mm</text>',
        f'  <text x="{width/2}" y="{height - 8}" fill="#475569" font-size="10" text-anchor="middle">{html.escape(y_label)}</text>',
        "</svg>",
    ]
    return "\n".join(svg)


def svg_to_png(svg_content: str, output_path: Path, dpi: int = 200) -> bool:
    """Convert SVG to PNG using cairosvg if available."""
    try:
        import cairosvg
        cairosvg.svg2png(bytestring=svg_content.encode("utf-8"), write_to=str(output_path), dpi=dpi)
        return True
    except ImportError:
        return False
    except Exception:
        return False


def generate_all_diagrams(result: SolverResult, output_dir: Path) -> dict[str, str]:
    """
    Generate all standard diagrams for a shaft report.
    Returns dict of diagram_name -> PNG file path (or SVG if PNG conversion failed).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    diagrams = {}

    # Shear Force Diagram
    svg_shear = generate_svg_diagram(
        result.x_stations,
        result.shear_force,
        "Shear Force Diagram V(x)",
        "Force (N)",
        stroke_color="#38bdf8",
        fill_color="rgba(56, 189, 248, 0.15)",
    )
    shear_path = output_dir / "shear_force.png"
    if svg_to_png(svg_shear, shear_path):
        diagrams["shear_force"] = str(shear_path)
    else:
        svg_path = output_dir / "shear_force.svg"
        svg_path.write_text(svg_shear, encoding="utf-8")
        diagrams["shear_force"] = str(svg_path)

    # Bending Moment Diagram
    svg_moment = generate_svg_diagram(
        result.x_stations,
        result.bending_moment,
        "Bending Moment Diagram M(x)",
        "Moment (N·m)",
        stroke_color="#a855f7",
        fill_color="rgba(168, 85, 247, 0.15)",
    )
    moment_path = output_dir / "bending_moment.png"
    if svg_to_png(svg_moment, moment_path):
        diagrams["bending_moment"] = str(moment_path)
    else:
        svg_path = output_dir / "bending_moment.svg"
        svg_path.write_text(svg_moment, encoding="utf-8")
        diagrams["bending_moment"] = str(svg_path)

    # Von Mises Stress Diagram
    svg_stress = generate_svg_diagram(
        result.x_stations,
        result.von_mises_stress_mpa,
        "Von Mises Stress Distribution σ_vm(x)",
        "Stress (MPa)",
        stroke_color="#f43f5e",
        fill_color="rgba(244, 63, 94, 0.15)",
    )
    stress_path = output_dir / "von_mises_stress.png"
    if svg_to_png(svg_stress, stress_path):
        diagrams["von_mises_stress"] = str(stress_path)
    else:
        svg_path = output_dir / "von_mises_stress.svg"
        svg_path.write_text(svg_stress, encoding="utf-8")
        diagrams["von_mises_stress"] = str(svg_path)

    # Deflection Diagram
    svg_deflection = generate_svg_diagram(
        result.x_stations,
        result.deflection_mm,
        "Deflection Profile v(x)",
        "Deflection (mm)",
        stroke_color="#10b981",
        fill_color="rgba(16, 185, 129, 0.15)",
    )
    deflection_path = output_dir / "deflection.png"
    if svg_to_png(svg_deflection, deflection_path):
        diagrams["deflection"] = str(deflection_path)
    else:
        svg_path = output_dir / "deflection.svg"
        svg_path.write_text(svg_deflection, encoding="utf-8")
        diagrams["deflection"] = str(svg_path)

    return diagrams


def generate_fbd_diagram(model: Any, result: SolverResult, output_dir: Path) -> str | None:
    """Generate Free Body Diagram SVG for the model."""
    try:
        # This would integrate with drafting/blueprint_2d.py or similar
        # For now, return None - can be extended later
        return None
    except Exception:
        return None


__all__ = [
    "generate_svg_diagram",
    "svg_to_png",
    "generate_all_diagrams",
    "generate_fbd_diagram",
]
