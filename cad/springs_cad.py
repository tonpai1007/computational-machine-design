"""
MDIE Parametric Spring CAD Generator
Generates clean OpenSCAD code for helical compression and extension springs.
"""

from components.springs import SpringAnalysisResult


class SpringCADGenerator:
    @staticmethod
    def generate_scad(result: SpringAnalysisResult) -> str:
        """
        Generate parametric OpenSCAD code for a 3D helical spring.
        """
        spec = result.spec
        geom = result.geometry

        lines = [
            "// ====================================================================",
            f"// MDIE Parametric Helical Spring: {spec.name}",
            f"// Wire d: {geom.wire_diameter_mm} mm | Mean D: {geom.mean_diameter_mm} mm | Outer Do: {geom.outer_diameter_mm} mm",
            f"// Active Coils: {geom.active_coils} | Total Coils: {geom.total_coils}",
            f"// Free Length L0: {geom.free_length_l0_mm} mm | Solid Ls: {geom.solid_length_ls_mm} mm",
            f"// Spring Rate k: {result.spring_rate_k_n_mm} N/mm | Material: {spec.material_name}",
            "// ====================================================================",
            "",
            "$fn = 40;",
            "",
            f"d = {geom.wire_diameter_mm};",
            f"D = {geom.mean_diameter_mm};",
            f"N = {geom.total_coils};",
            f"L0 = {geom.free_length_l0_mm};",
            f"pitch = {geom.pitch_mm};",
            "",
            "// Helical Spring Generator",
            "module helical_spring() {",
            "    steps_per_turn = 36;",
            "    total_steps = floor(N * steps_per_turn);",
            "    dz = pitch / steps_per_turn;",
            "    ",
            "    for (i = [0 : total_steps - 1]) {",
            "        hull() {",
            "            rotate([0, 0, i * (360 / steps_per_turn)])",
            "            translate([D/2, 0, i * dz])",
            "            sphere(r=d/2);",
            "            ",
            "            rotate([0, 0, (i + 1) * (360 / steps_per_turn)])",
            "            translate([D/2, 0, (i + 1) * dz])",
            "            sphere(r=d/2);",
            "        }",
            "    }",
            "}",
            "",
            "// Render Spring",
            "color([0.35, 0.55, 0.85, 1.0])",
            "helical_spring();",
        ]
        return "\n".join(lines)
