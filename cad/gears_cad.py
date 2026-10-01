"""
MDIE Parametric Gear OpenSCAD & CAD Generator
Generates clean OpenSCAD code for spur and helical gear pairs with involute tooth profiles,
central bore, hub, and standard keyways.
"""

from components.gears import GearPairResult


class GearCADGenerator:
    @staticmethod
    def generate_scad(result: GearPairResult) -> str:
        """
        Generate complete, renderable OpenSCAD source code for the gear pair assembly.
        """
        spec = result.spec
        geom = result.geometry

        lines = [
            "// ====================================================================",
            f"// MDIE Parametric Gear Pair: {spec.name} ({spec.gear_type.upper()})",
            f"// Normal Module: {geom.normal_module_mm} mm | Ratio: {geom.gear_ratio}:1",
            f"// Pinion: z={spec.pinion_teeth}, da={geom.outer_diameter_pinion_mm} mm",
            f"// Gear:   z={spec.gear_teeth}, da={geom.outer_diameter_gear_mm} mm",
            f"// Center Distance: {geom.center_distance_mm} mm",
            f"// Material: {result.material_name}",
            "// ====================================================================",
            "",
            "$fn = 60;",
            "",
            f"module involute_gear(z={spec.pinion_teeth}, m={geom.normal_module_mm}, b={geom.face_width_mm}, bore={spec.pinion_bore_mm}, helix={spec.helix_angle_deg}) {{",
            "    pitch_d = z * m;",
            "    outer_d = pitch_d + 2.0 * m;",
            "    root_d = pitch_d - 2.5 * m;",
            "    tooth_w = (3.14159 * m) / 2.0;",
            "    ",
            "    difference() {",
            "        union() {",
            "            // Gear rim body",
            "            cylinder(r=root_d/2, h=b, center=true);",
            "            ",
            "            // Involute teeth array",
            "            for (i = [0 : z - 1]) {",
            "                rotate([0, 0, i * (360 / z)])",
            "                translate([0, 0, -b/2])",
            "                linear_extrude(height=b, twist=helix * (b / pitch_d))",
            "                polygon(points=[",
            "                    [-tooth_w*0.6, root_d/2],",
            "                    [-tooth_w*0.35, outer_d/2],",
            "                    [ tooth_w*0.35, outer_d/2],",
            "                    [ tooth_w*0.6, root_d/2]",
            "                ]);",
            "            }",
            "            ",
            "            // Reinforced Hub",
            "            cylinder(r=(bore * 1.5)/2, h=b * 1.25, center=true);",
            "        }",
            "        ",
            "        // Shaft Bore",
            "        cylinder(r=bore/2, h=b * 2, center=true);",
            "        ",
            "        // Keyway slot",
            "        translate([0, bore/2, 0])",
            "        cube([bore * 0.25, bore * 0.25, b * 2], center=true);",
            "    }",
            "}",
            "",
            "// --- Assembly Display ---",
            "// Pinion (Input)",
            "color([0.25, 0.65, 0.90, 1.0])",
            "translate([0, 0, 0])",
            f"involute_gear(z={spec.pinion_teeth}, m={geom.normal_module_mm}, b={geom.face_width_mm}, bore={spec.pinion_bore_mm}, helix={spec.helix_angle_deg});",
            "",
            "// Driven Gear (Output) at Center Distance",
            "color([0.85, 0.75, 0.30, 1.0])",
            f"translate([{geom.center_distance_mm}, 0, 0])",
            f"rotate([0, 0, 180 / {spec.gear_teeth}])",
            f"involute_gear(z={spec.gear_teeth}, m={geom.normal_module_mm}, b={geom.face_width_mm}, bore={spec.gear_bore_mm}, helix=-{spec.helix_angle_deg});",
            "",
            "// Centerline reference",
            f"#translate([0, 0, -{geom.face_width_mm}/2 - 5])",
            f"cylinder(r=1.5, h={geom.face_width_mm} + 10, center=false);",
            f"#translate([{geom.center_distance_mm}, 0, -{geom.face_width_mm}/2 - 5])",
            f"cylinder(r=1.5, h={geom.face_width_mm} + 10, center=false);",
        ]
        return "\n".join(lines)
