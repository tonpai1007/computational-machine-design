"""Curated slide content for the Ergonomic Armchair design deck.

All engineering numbers come from the verified data sheet (chair_real_data.md);
this module only structures them for presentation. Images are pulled from
Project/chair/drawings (CAD renders) and Project/chair/diagrams (FBD/SFD/BMD).
"""
from __future__ import annotations

from typing import Any

ARMCHAIR_SLIDES: dict[str, Any] = {
    "title": "Ergonomic Armchair — Machine Design Project",
    "source": "Project/chair/chair_real_data.md",
    "slides": [
        {
            "type": "cover",
            "heading": "Ergonomic Armchair",
            "subtitle": "2022101 · Principle of Machine Design · Chapter 1 · 2566",
        },
        {
            "type": "image",
            "heading": "3D CAD Assembly Render",
            "images": [
                {
                    "src": "Project/chair/drawings/chair_preview.png",
                    "alt": "Full armchair assembly 3D render",
                    "caption": "Chair assembly — AISI 1018 steel tubing, 4 splayed legs at 3.5°",
                },
                {
                    "src": "Project/chair/drawings/Chair_Assembly.svg",
                    "alt": "Chair assembly vector blueprint",
                    "caption": "Vector blueprint (ISO 128 / ANSI Y14.5)",
                },
            ],
        },
        {
            "type": "bullet",
            "heading": "Design Overview",
            "body": [
                "Seat 480 × 460 × 450 mm, thickness 22 mm",
                "4 splayed legs at 3.5° for overturning stability",
                "Backrest angled at 98° for ergonomic support",
                "Stretcher at 150 mm for lateral bracing",
                "Armrests 210 mm above seat, 60 mm front overhang",
            ],
        },
        {
            "type": "image",
            "heading": "Free-Body Diagram — Overall Chair",
            "images": [
                {
                    "src": "Project/chair/diagrams/fbd_01_overall_chair.svg",
                    "alt": "Overall chair free-body diagram",
                    "caption": "FBD-01: Overall chair — seat 1300 N, arms 450 N each, backrest 300 N",
                },
            ],
        },
        {
            "type": "table",
            "heading": "Section Properties",
            "body": [
                ["Part", "Shape", "OD (mm)", "t (mm)", "A (mm²)", "I (mm⁴)"],
                ["Leg", "round tube", "28", "2", "163.36", "13885.8"],
                ["Frame rail", "square tube", "25", "2", "184.00", "16345.3"],
                ["Arm post", "round tube", "22", "1.8", "114.23", "5872.5"],
                ["Stretcher", "round tube", "19", "1.5", "82.47", "3180.1"],
                ["Arm bracket", "plate", "12×11", "—", "132.00", "1331.00"],
            ],
        },
        {
            "type": "table",
            "heading": "Applied Loads",
            "body": [
                ["Load", "Magnitude (N)", "Source"],
                ["Seat vertical", "1300", "User + seat"],
                ["Left arm vertical", "450", "Armrest reaction"],
                ["Left arm lateral", "-150", "Lateral brace"],
                ["Right arm vertical", "450", "Armrest reaction"],
                ["Backrest force", "300", "Backrest reaction"],
            ],
        },
        {
            "type": "metric",
            "heading": "Material — AISI 1018 Steel",
            "body": [
                {"value": "370 MPa", "label": "Yield Strength"},
                {"value": "440 MPa", "label": "Ultimate Strength"},
                {"value": "205 GPa", "label": "Elastic Modulus"},
                {"value": "7870 kg/m³", "label": "Density"},
            ],
        },
        {
            "type": "metric",
            "heading": "Buckling Safety Factors",
            "body": [
                {"value": "2.15", "label": "Front-left leg"},
                {"value": "2.15", "label": "Front-right leg"},
                {"value": "2.15", "label": "Rear-left leg"},
                {"value": "2.15", "label": "Rear-right leg"},
            ],
        },
        {
            "type": "image",
            "heading": "Shear Force & Bending Moment — Seat Rail",
            "images": [
                {
                    "src": "Project/chair/diagrams/fbd_03_seat_rail_sfd_bmd.svg",
                    "alt": "Seat rail SFD and BMD",
                    "caption": "FBD-03: Seat rail shear force diagram and bending moment diagram",
                },
            ],
        },
        {
            "type": "table",
            "heading": "Overturning Safety vs Leg Splay Angle",
            "body": [
                ["Angle", "Base (mm)", "Safety Factor"],
                ["0°", "480 × 460", "2.98"],
                ["2°", "511 × 491", "3.18"],
                ["3.5° (used)", "535 × 515", "3.33"],
                ["5°", "559 × 539", "3.48"],
                ["8°", "606 × 586", "3.79"],
            ],
        },
        {
            "type": "bullet",
            "heading": "Key Findings",
            "body": [
                "All legs pass buckling with n_d = 2.15 > 2.0 target",
                "Overturning safety factor = 3.33 at the selected 3.5° splay",
                "3.5° chosen for aesthetics and safety margin, not structural necessity",
                "Yield, buckling, and overturning checks all PASS",
            ],
        },
        {
            "type": "bullet",
            "heading": "Deliverables",
            "body": [
                "chair.step — ISO 10303 CAD assembly",
                "chair.stl — Watertight 3D print file",
                "chair.scad — Parametric OpenSCAD source",
                "chair.pdf / chair.dxf — Manufacturing drawings",
                "academic_assignment_report.html — Full dossier",
            ],
        },
        {
            "type": "end",
            "heading": "Thank You",
            "body": [
                "All values verified by deterministic physics solver",
                "See chair_real_data.md for the full audit trace",
            ],
        },
    ],
}


__all__ = ["ARMCHAIR_SLIDES"]
