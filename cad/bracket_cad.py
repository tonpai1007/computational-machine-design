"""
Motor Mounting Bracket CAD Engine
Generates OpenSCAD (.scad), Binary STL (.stl), and ISO-10303 STEP Solids (.step)
for L-brackets, motor faceplates, and foot-mounted brackets.
"""

import math
import struct
from typing import List, Tuple
from core.bracket_model import BracketModel
from cad.assembly import MeshPrimitives, Point3D, Triangle
from cad.step_assembly import MultiBodySTEPExporter, SolidPart


class BracketCADEngine:
    """Parametric CAD generator for motor mounting brackets and plates."""

    @staticmethod
    def generate_openscad(model: BracketModel) -> str:
        g = model.geometry
        m = model.material
        pat = g.motor_bolt_pattern
        base_pat = g.base_bolt_pattern

        lines = [
            "// ==================================================================",
            "// MDIE PARAMETRIC MOTOR MOUNTING BRACKET CAD",
            f"// Model: {model.name}",
            f"// Material: {m.name} (Sy = {m.yield_strength_mpa} MPa)",
            "// ==================================================================",
            "$fn = 32;",
            "",
            f"base_l     = {g.base_length_mm:.1f};",
            f"base_w     = {g.base_width_mm:.1f};",
            f"thick      = {g.thickness_mm:.1f};",
            f"up_h       = {g.upright_height_mm:.1f};",
            f"pilot_d    = {g.motor_pilot_diameter_mm:.1f};",
            f"motor_bcd  = {pat.bolt_circle_diameter_mm:.1f};",
            f"motor_n    = {pat.num_holes};",
            f"motor_hd   = {pat.hole_diameter_mm:.1f};",
            f"base_sx    = {base_pat.spacing_x_mm:.1f};",
            f"base_sy    = {base_pat.spacing_y_mm:.1f};",
            f"base_hd    = {base_pat.hole_diameter_mm:.1f};",
            f"has_gusset = {'true' if g.has_gussets else 'false'};",
            "",
            "module motor_bracket() {",
            "    difference() {",
            "        union() {",
            "            // 1. Horizontal Base Foot",
            "            cube([base_l, base_w, thick]);",
            "",
            "            // 2. Vertical Upright Flange",
            "            cube([thick, base_w, up_h]);",
            "",
            "            // 3. Stiffener Gussets",
            "            if (has_gusset) {",
            "                gusset_t = 4.0;",
            "                translate([0, 10, 0])",
            "                    linear_extrude(height = gusset_t)",
            "                    polygon(points=[[thick, 0], [base_l*0.6, 0], [thick, up_h*0.6]]);",
            "                translate([0, base_w - 10 - gusset_t, 0])",
            "                    linear_extrude(height = gusset_t)",
            "                    polygon(points=[[thick, 0], [base_l*0.6, 0], [thick, up_h*0.6]]);",
            "            }",
            "        }",
            "",
            "        // 4. Central Motor Pilot Hole",
            "        translate([thick/2, base_w/2, up_h*0.6])",
            "            rotate([0, 90, 0])",
            "            cylinder(d = pilot_d, h = thick * 2, center = true);",
            "",
            "        // 5. Motor Flange Mounting Bolt Pattern",
            "        for (i = [0 : motor_n - 1]) {",
            "            ang = i * (360.0 / motor_n) + 45.0;",
            "            bx = (motor_bcd / 2) * cos(ang);",
            "            bz = (motor_bcd / 2) * sin(ang);",
            "            translate([thick/2, base_w/2 + bx, up_h*0.6 + bz])",
            "                rotate([0, 90, 0])",
            "                cylinder(d = motor_hd, h = thick * 2, center = true);",
            "        }",
            "",
            "        // 6. Base Anchoring Bolt Holes",
            "        translate([base_l/2 - base_sx/2, base_w/2 - base_sy/2, -1]) cylinder(d = base_hd, h = thick + 2);",
            "        translate([base_l/2 + base_sx/2, base_w/2 - base_sy/2, -1]) cylinder(d = base_hd, h = thick + 2);",
            "        translate([base_l/2 - base_sx/2, base_w/2 + base_sy/2, -1]) cylinder(d = base_hd, h = thick + 2);",
            "        translate([base_l/2 + base_sx/2, base_w/2 + base_sy/2, -1]) cylinder(d = base_hd, h = thick + 2);",
            "    }",
            "}",
            "",
            "color([0.35, 0.42, 0.52]) motor_bracket();",
        ]
        return "\n".join(lines)

    @classmethod
    def generate_mesh_triangles(cls, model: BracketModel) -> List[Triangle]:
        g = model.geometry
        t = g.thickness_mm
        bl = g.base_length_mm
        bw = g.base_width_mm
        uh = g.upright_height_mm

        tris: List[Triangle] = []
        # Base plate box
        tris.extend(MeshPrimitives.create_box_triangles(bl / 2.0, 0.0, t / 2.0, bl, bw, t))
        # Upright flange box
        tris.extend(MeshPrimitives.create_box_triangles(t / 2.0, 0.0, uh / 2.0, t, bw, uh))
        return tris

    @classmethod
    def export_binary_stl(cls, model: BracketModel) -> bytes:
        triangles = cls.generate_mesh_triangles(model)
        return MeshPrimitives.export_binary_stl(triangles, model_name=model.name)

    @classmethod
    def export_step_solid(cls, model: BracketModel) -> str:
        triangles = cls.generate_mesh_triangles(model)
        part = SolidPart(name=model.name, triangles=triangles, color_rgb=(0.4, 0.45, 0.5))
        return MultiBodySTEPExporter.export_assembly(model.name, [part])
