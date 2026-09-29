"""
3D Space Frame & Truss CAD Engine
Converts arbitrary 3D FEA frame models (nodes and members) into:
- Parametric OpenSCAD scripts (.scad)
- Watertight 3D printable meshes (.stl)
- Multi-Body ISO-10303 STEP Solid assemblies (.step)
"""

import math
import struct
from typing import List, Tuple, Dict, Any, Optional
from mdie.physics.fea_3d import FEA3DSolver, FEAMember, FEANode
from mdie.cad.assembly import MeshPrimitives, Point3D, Triangle
from mdie.cad.step_assembly import MultiBodySTEPExporter, SolidPart


class SpaceFrameCADEngine:
    """Parametric CAD generator for arbitrary 3D space frames and trusses."""

    @staticmethod
    def generate_openscad(solver: FEA3DSolver, color_by_stress: bool = True) -> str:
        """Generates OpenSCAD source code for the 3D frame assembly."""
        lines = [
            f"// ==================================================================",
            f"// MDIE PARAMETRIC 3D SPACE FRAME CAD",
            f"// Structure: {solver.name}",
            f"// Nodes: {len(solver.nodes)}, Members: {len(solver.members)}",
            f"// ==================================================================",
            "$fn = 24;",
            "",
            "// Helper: Beam cylinder connecting two 3D points",
            "module beam(p1, p2, dia) {",
            "    hull() {",
            "        translate(p1) sphere(d=dia);",
            "        translate(p2) sphere(d=dia);",
            "    }",
            "}",
            "",
            "// Joint sphere at nodes",
            "module joint_node(p, dia) {",
            "    translate(p) sphere(d=dia);",
            "}",
            "",
            f"module {solver.name.lower().replace(' ', '_').replace('-', '_')}() {{",
        ]

        # Max stress for coloring
        max_vm = max((m.von_mises_stress_mpa for m in solver.members), default=1.0)
        max_vm = max(max_vm, 1e-3)

        # Draw members
        lines.append("    // 3D Frame Members")
        for m in solver.members:
            p1 = [round(m.n1.x * 1000.0, 2), round(m.n1.y * 1000.0, 2), round(m.n1.z * 1000.0, 2)]
            p2 = [round(m.n2.x * 1000.0, 2), round(m.n2.y * 1000.0, 2), round(m.n2.z * 1000.0, 2)]
            dia = round(m.outer_dim * 1000.0, 2)

            if color_by_stress and m.von_mises_stress_mpa > 0:
                ratio = min(1.0, m.von_mises_stress_mpa / max_vm)
                # Gradient from blue/cyan (low) to orange/red (high)
                r = round(ratio, 2)
                g = round(max(0.0, 0.8 - ratio * 0.6), 2)
                b = round(max(0.0, 1.0 - ratio), 2)
                lines.append(f"    color([{r}, {g}, {b}]) // {m.id} ({m.von_mises_stress_mpa:.1f} MPa)")
            else:
                lines.append(f"    color([0.35, 0.45, 0.55]) // {m.id}")

            lines.append(f"        beam([{p1[0]}, {p1[1]}, {p1[2]}], [{p2[0]}, {p2[1]}, {p2[2]}], {dia});")

        lines.append("}")
        lines.append("")
        lines.append(f"{solver.name.lower().replace(' ', '_').replace('-', '_')}();")
        return "\n".join(lines)

    @classmethod
    def generate_member_triangles(cls, member: FEAMember) -> List[Triangle]:
        """Generate closed watertight triangular mesh for a single beam member."""
        p1: Point3D = (member.n1.x * 1000.0, member.n1.y * 1000.0, member.n1.z * 1000.0)
        p2: Point3D = (member.n2.x * 1000.0, member.n2.y * 1000.0, member.n2.z * 1000.0)
        radius = (member.outer_dim * 1000.0) / 2.0
        return MeshPrimitives.create_cylinder_triangles(p1, p2, radius, n_slices=16)

    @classmethod
    def export_binary_stl(cls, solver: FEA3DSolver) -> bytes:
        """Exports complete watertight binary STL mesh of the space frame."""
        all_triangles: List[Triangle] = []
        for m in solver.members:
            all_triangles.extend(cls.generate_member_triangles(m))

        header = f"MDIE 3D Space Frame STL: {solver.name}".encode('ascii')[:80].ljust(80, b'\0')
        count = len(all_triangles)
        body = bytearray()
        body.extend(header)
        body.extend(struct.pack('<I', count))

        for v1, v2, v3 in all_triangles:
            # Normal calculation
            ux = v2[0] - v1[0]; uy = v2[1] - v1[1]; uz = v2[2] - v1[2]
            vx = v3[0] - v1[0]; vy = v3[1] - v1[1]; vz = v3[2] - v1[2]
            nx = uy * vz - uz * vy
            ny = uz * vx - ux * vz
            nz = ux * vy - uy * vx
            mag = math.sqrt(nx**2 + ny**2 + nz**2)
            if mag > 1e-9:
                nx /= mag; ny /= mag; nz /= mag
            else:
                nx = 0.0; ny = 0.0; nz = 1.0

            body.extend(struct.pack('<3f', nx, ny, nz))
            body.extend(struct.pack('<3f', v1[0], v1[1], v1[2]))
            body.extend(struct.pack('<3f', v2[0], v2[1], v2[2]))
            body.extend(struct.pack('<3f', v3[0], v3[1], v3[2]))
            body.extend(struct.pack('<H', 0))

        return bytes(body)

    @classmethod
    def export_step_solid(cls, solver: FEA3DSolver) -> str:
        """Exports multi-body ISO-10303 STEP solid file with each member as a distinct solid part."""
        parts: List[SolidPart] = []
        max_vm = max((m.von_mises_stress_mpa for m in solver.members), default=1.0)
        max_vm = max(max_vm, 1e-3)

        for m in solver.members:
            tris = cls.generate_member_triangles(m)
            if tris:
                ratio = min(1.0, m.von_mises_stress_mpa / max_vm) if m.von_mises_stress_mpa > 0 else 0.2
                color = (ratio, max(0.0, 0.8 - ratio * 0.6), max(0.0, 1.0 - ratio))
                parts.append(SolidPart(name=m.id, triangles=tris, color_rgb=color))

        return MultiBodySTEPExporter.export_assembly(solver.name, parts)
