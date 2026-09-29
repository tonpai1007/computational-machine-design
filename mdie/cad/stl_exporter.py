"""
MDIE Direct STL Exporter
Generates standard binary and ASCII STL (Stereolithography) 3D mesh files
directly from EngineeringModel geometry without requiring external CAD software.
Fully compatible with 3D slicers (Cura, PrusaSlicer, Bambu Studio) and CAD tools (SolidWorks, Fusion360, FreeCAD).
"""

import math
import struct
from typing import List, Tuple
from mdie.core.models import EngineeringModel, ShaftSegment

class STLExporter:
    @staticmethod
    def _normal(v1: Tuple[float, float, float], v2: Tuple[float, float, float], v3: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """Compute outward face normal vector from 3 vertices."""
        ux, uy, uz = v2[0] - v1[0], v2[1] - v1[1], v2[2] - v1[2]
        vx, vy, vz = v3[0] - v1[0], v3[1] - v1[1], v3[2] - v1[2]
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx
        mag = math.sqrt(nx**2 + ny**2 + nz**2)
        if mag > 1e-9:
            return (nx / mag, ny / mag, nz / mag)
        return (0.0, 0.0, 1.0)

    @classmethod
    def generate_triangles(cls, model: EngineeringModel, n_slices: int = 64) -> List[Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]]:
        """
        Generate triangular face mesh of the shaft geometry (dimensions in mm).
        Includes stepped outer cylinders, shoulder transition annular faces, and end caps.
        """
        triangles = []
        segments = sorted(model.segments, key=lambda s: s.start_pos)
        if not segments:
            return triangles

        d_angles = [2.0 * math.pi * i / n_slices for i in range(n_slices)]

        # 1. Outer Cylindrical Surfaces
        for seg in segments:
            x0 = seg.start_pos * 1000.0
            x1 = seg.end_pos * 1000.0
            r_out = (seg.outer_diameter / 2.0) * 1000.0

            for i in range(n_slices):
                a1 = d_angles[i]
                a2 = d_angles[(i + 1) % n_slices]

                cos1, sin1 = math.cos(a1), math.sin(a1)
                cos2, sin2 = math.cos(a2), math.sin(a2)

                p1 = (x0, r_out * cos1, r_out * sin1)
                p2 = (x1, r_out * cos1, r_out * sin1)
                p3 = (x1, r_out * cos2, r_out * sin2)
                p4 = (x0, r_out * cos2, r_out * sin2)

                # Two triangles per quad (CCW winding for outward normal)
                triangles.append((p1, p2, p3))
                triangles.append((p1, p3, p4))

        # 2. Shoulder Steps between consecutive segments
        for k in range(len(segments) - 1):
            s1 = segments[k]
            s2 = segments[k + 1]
            x_step = s1.end_pos * 1000.0
            r1 = (s1.outer_diameter / 2.0) * 1000.0
            r2 = (s2.outer_diameter / 2.0) * 1000.0

            if abs(r1 - r2) > 0.01:
                r_inner = min(r1, r2)
                r_outer = max(r1, r2)
                facing_forward = r2 > r1

                for i in range(n_slices):
                    a1 = d_angles[i]
                    a2 = d_angles[(i + 1) % n_slices]
                    cos1, sin1 = math.cos(a1), math.sin(a1)
                    cos2, sin2 = math.cos(a2), math.sin(a2)

                    p_in1 = (x_step, r_inner * cos1, r_inner * sin1)
                    p_in2 = (x_step, r_inner * cos2, r_inner * sin2)
                    p_out1 = (x_step, r_outer * cos1, r_outer * sin1)
                    p_out2 = (x_step, r_outer * cos2, r_outer * sin2)

                    if facing_forward:
                        # Step faces towards negative X
                        triangles.append((p_in1, p_in2, p_out2))
                        triangles.append((p_in1, p_out2, p_out1))
                    else:
                        # Step faces towards positive X
                        triangles.append((p_in1, p_out2, p_in2))
                        triangles.append((p_in1, p_out1, p_out2))

        # 3. Left End Cap (x = 0)
        s_first = segments[0]
        x_left = s_first.start_pos * 1000.0
        r_left = (s_first.outer_diameter / 2.0) * 1000.0
        r_bore_left = (s_first.inner_diameter / 2.0) * 1000.0

        for i in range(n_slices):
            a1 = d_angles[i]
            a2 = d_angles[(i + 1) % n_slices]
            cos1, sin1 = math.cos(a1), math.sin(a1)
            cos2, sin2 = math.cos(a2), math.sin(a2)

            p_out1 = (x_left, r_left * cos1, r_left * sin1)
            p_out2 = (x_left, r_left * cos2, r_left * sin2)

            if r_bore_left > 0.01:
                p_in1 = (x_left, r_bore_left * cos1, r_bore_left * sin1)
                p_in2 = (x_left, r_bore_left * cos2, r_bore_left * sin2)
                triangles.append((p_in1, p_in2, p_out2))
                triangles.append((p_in1, p_out2, p_out1))
            else:
                p_center = (x_left, 0.0, 0.0)
                triangles.append((p_center, p_out2, p_out1))

        # 4. Right End Cap (x = L)
        s_last = segments[-1]
        x_right = s_last.end_pos * 1000.0
        r_right = (s_last.outer_diameter / 2.0) * 1000.0
        r_bore_right = (s_last.inner_diameter / 2.0) * 1000.0

        for i in range(n_slices):
            a1 = d_angles[i]
            a2 = d_angles[(i + 1) % n_slices]
            cos1, sin1 = math.cos(a1), math.sin(a1)
            cos2, sin2 = math.cos(a2), math.sin(a2)

            p_out1 = (x_right, r_right * cos1, r_right * sin1)
            p_out2 = (x_right, r_right * cos2, r_right * sin2)

            if r_bore_right > 0.01:
                p_in1 = (x_right, r_bore_right * cos1, r_bore_right * sin1)
                p_in2 = (x_right, r_bore_right * cos2, r_bore_right * sin2)
                triangles.append((p_in1, p_out2, p_in2))
                triangles.append((p_in1, p_out1, p_out2))
            else:
                p_center = (x_right, 0.0, 0.0)
                triangles.append((p_center, p_out1, p_out2))

        # 5. Internal Bore Cylinders (if hollow)
        for seg in segments:
            if seg.inner_diameter > 0.01:
                x0 = seg.start_pos * 1000.0
                x1 = seg.end_pos * 1000.0
                r_in = (seg.inner_diameter / 2.0) * 1000.0

                for i in range(n_slices):
                    a1 = d_angles[i]
                    a2 = d_angles[(i + 1) % n_slices]
                    cos1, sin1 = math.cos(a1), math.sin(a1)
                    cos2, sin2 = math.cos(a2), math.sin(a2)

                    p1 = (x0, r_in * cos1, r_in * sin1)
                    p2 = (x1, r_in * cos1, r_in * sin1)
                    p3 = (x1, r_in * cos2, r_in * sin2)
                    p4 = (x0, r_in * cos2, r_in * sin2)

                    # Inward facing normals
                    triangles.append((p1, p3, p2))
                    triangles.append((p1, p4, p3))

        return triangles

    @classmethod
    def export_binary_stl(cls, model: EngineeringModel, n_slices: int = 64) -> bytes:
        """Export geometry as standard binary STL bytes."""
        triangles = cls.generate_triangles(model, n_slices)
        n_tris = len(triangles)

        # 80-byte header
        header = f"MDIE CAD Engine - Model: {model.name[:50]}".encode('ascii')
        header = header.ljust(80, b'\x00')

        parts = [header, struct.pack("<I", n_tris)]

        for v1, v2, v3 in triangles:
            norm = cls._normal(v1, v2, v3)
            # Normal (3 floats), Vertices (9 floats), Attribute byte count (unsigned short)
            record = struct.pack(
                "<3f9fH",
                norm[0], norm[1], norm[2],
                v1[0], v1[1], v1[2],
                v2[0], v2[1], v2[2],
                v3[0], v3[1], v3[2],
                0
            )
            parts.append(record)

        return b"".join(parts)

    @classmethod
    def export_ascii_stl(cls, model: EngineeringModel, n_slices: int = 48) -> str:
        """Export geometry as human-readable ASCII STL."""
        triangles = cls.generate_triangles(model, n_slices)
        lines = [f"solid {model.name.replace(' ', '_')}"]

        for v1, v2, v3 in triangles:
            n = cls._normal(v1, v2, v3)
            lines.append(f"  facet normal {n[0]:.6e} {n[1]:.6e} {n[2]:.6e}")
            lines.append("    outer loop")
            lines.append(f"      vertex {v1[0]:.6f} {v1[1]:.6f} {v1[2]:.6f}")
            lines.append(f"      vertex {v2[0]:.6f} {v2[1]:.6f} {v2[2]:.6f}")
            lines.append(f"      vertex {v3[0]:.6f} {v3[1]:.6f} {v3[2]:.6f}")
            lines.append("    endloop")
            lines.append("  endfacet")

        lines.append(f"endsolid {model.name.replace(' ', '_')}")
        return "\n".join(lines)
