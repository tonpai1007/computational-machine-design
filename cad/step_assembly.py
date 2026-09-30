"""
Multi-Body Assembly ISO-10303 STEP Solid Exporter
Generates compliant STEP AP203/AP214 files containing distinct, named solid components
organized into a CAD assembly structure.
Compatible with SolidWorks, Autodesk Fusion 360, Autodesk Inventor, PTC Creo, and FreeCAD.
"""

import math
import datetime
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

Point3D = Tuple[float, float, float]
Triangle = Tuple[Point3D, Point3D, Point3D]

class SolidPart:
    """Represents an individual named solid part within an assembly."""
    def __init__(
        self,
        name: str,
        triangles: List[Triangle],
        color_rgb: Optional[Tuple[float, float, float]] = None,
        origin_offset: Optional[Point3D] = None
    ):
        self.name = name.replace(" ", "_").replace("-", "_")
        self.triangles = triangles
        self.color_rgb = color_rgb or (0.7, 0.7, 0.7)
        self.origin_offset: Point3D = origin_offset or (0.0, 0.0, 0.0)

    def get_bounding_box(self) -> Tuple[Point3D, Point3D]:
        """Returns ((min_x, min_y, min_z), (max_x, max_y, max_z)) in mm."""
        if not self.triangles:
            return ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
        all_pts = [p for tri in self.triangles for p in tri]
        xs = [p[0] for p in all_pts]
        ys = [p[1] for p in all_pts]
        zs = [p[2] for p in all_pts]
        return ((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs)))

    def get_dimensions(self) -> Tuple[float, float, float]:
        """Returns bounding dimensions: (dx, dy, dz) in mm."""
        (min_x, min_y, min_z), (max_x, max_y, max_z) = self.get_bounding_box()
        return (max_x - min_x, max_y - min_y, max_z - min_z)

    def to_local_origin(self, center_xy: bool = True, base_z: bool = True) -> "SolidPart":
        """
        Transforms part geometry from global assembly coordinates to a localized CAM/manufacturing origin.
        By default, centers the part on X-Y (X=0, Y=0) and aligns its lowest point to Z=0.
        """
        if not self.triangles:
            return SolidPart(self.name, [], self.color_rgb, origin_offset=(0.0, 0.0, 0.0))

        (min_x, min_y, min_z), (max_x, max_y, max_z) = self.get_bounding_box()
        dx = -(min_x + max_x) / 2.0 if center_xy else 0.0
        dy = -(min_y + max_y) / 2.0 if center_xy else 0.0
        dz = -min_z if base_z else 0.0

        new_triangles: List[Triangle] = []
        for p1, p2, p3 in self.triangles:
            tp1 = (p1[0] + dx, p1[1] + dy, p1[2] + dz)
            tp2 = (p2[0] + dx, p2[1] + dy, p2[2] + dz)
            tp3 = (p3[0] + dx, p3[1] + dy, p3[2] + dz)
            new_triangles.append((tp1, tp2, tp3))

        return SolidPart(
            name=self.name,
            triangles=new_triangles,
            color_rgb=self.color_rgb,
            origin_offset=(-dx, -dy, -dz)
        )


class MultiBodySTEPExporter:
    """
    Exports multiple distinct solid parts into a unified ISO-10303-21 STEP assembly file.
    Each part maintains its own MANIFOLD_SOLID_BREP, CLOSED_SHELL, and PRODUCT entity.
    """

    @classmethod
    def export_assembly(
        cls,
        assembly_name: str,
        parts: List[SolidPart],
        author: str = "MDIE Computational Engineer"
    ) -> str:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        sanitized_assembly = assembly_name.replace(" ", "_").replace("-", "_")

        lines = [
            "ISO-10303-21;",
            "HEADER;",
            "FILE_DESCRIPTION(('MDIE Multi-Body CAD Solid Assembly','CAx-IF Rec.Pracs.---Representation of Geometric Shapes'),'2;1');",
            f"FILE_NAME('{sanitized_assembly}.step','{timestamp}',('{author}'),('Machine Design Intelligence Engine'),'MDIE Multi-Body STEP Engine','MDIE Platform','');",
            "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));",
            "ENDSEC;",
            "DATA;",
            "#1=APPLICATION_PROTOCOL_DEFINITION('international standard','automotive_design',2000,#2);",
            "#2=APPLICATION_CONTEXT('core data for automotive mechanical design processes');",
            "#3=PRODUCT_CONTEXT('',#2,'mechanical');",
            "#4=CARTESIAN_POINT('origin',(0.,0.,0.));",
            "#5=DIRECTION('axis_z',(0.,0.,1.));",
            "#6=DIRECTION('axis_x',(1.,0.,0.));",
            "#7=AXIS2_PLACEMENT_3D('world_cs',#4,#5,#6);",
            "#8=(LENGTH_UNIT()NAMED_UNIT(*)SI_UNIT(.MILLI.,.METRE.));",
            "#9=(NAMED_UNIT(*)PLANE_ANGLE_UNIT()SI_UNIT($,.RADIAN.));",
            "#10=(NAMED_UNIT(*)SI_UNIT($,.STERADIAN.)SOLID_ANGLE_UNIT());",
            "#11=(GEOMETRIC_REPRESENTATION_CONTEXT(3)GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#12))GLOBAL_UNIT_ASSIGNED_CONTEXT((#8,#9,#10))REPRESENTATION_CONTEXT('3D','MDIE Solid Assembly'));",
            "#12=UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-05),#8,'closure',0.);"
        ]

        eid = 13

        # Root Assembly Product Hierarchy
        top_prod_id = eid; lines.append(f"#{eid}=PRODUCT('{sanitized_assembly}','{sanitized_assembly}','',(#3));"); eid += 1
        top_form_id = eid; lines.append(f"#{eid}=PRODUCT_DEFINITION_FORMATION('','',#{top_prod_id});"); eid += 1
        pdef_ctx_id = eid; lines.append(f"#{eid}=PRODUCT_DEFINITION_CONTEXT('part definition',#2,'design');"); eid += 1
        top_pdef_id = eid; lines.append(f"#{eid}=PRODUCT_DEFINITION('design','',#{top_form_id},#{pdef_ctx_id});"); eid += 1
        top_pshp_id = eid; lines.append(f"#{eid}=PRODUCT_DEFINITION_SHAPE('','',#{top_pdef_id});"); eid += 1
        top_rep_id = eid; lines.append(f"#{eid}=SHAPE_REPRESENTATION('{sanitized_assembly}',(#7),#11);"); eid += 1
        lines.append(f"#{eid}=SHAPE_DEFINITION_REPRESENTATION(#{top_pshp_id},#{top_rep_id});"); eid += 1

        # Process each individual solid part
        for part_idx, part in enumerate(parts):
            if not part.triangles:
                continue

            # Vertex welding per part
            vmap: Dict[Tuple[float, float, float], int] = {}
            for tri in part.triangles:
                for v in tri:
                    key = (round(v[0], 4), round(v[1], 4), round(v[2], 4))
                    if key not in vmap:
                        vmap[key] = eid
                        lines.append(f"#{eid}=CARTESIAN_POINT('',({key[0]:.4f},{key[1]:.4f},{key[2]:.4f}));")
                        eid += 1

            face_ids: List[str] = []
            for v1, v2, v3 in part.triangles:
                k1 = (round(v1[0], 4), round(v1[1], 4), round(v1[2], 4))
                k2 = (round(v2[0], 4), round(v2[1], 4), round(v2[2], 4))
                k3 = (round(v3[0], 4), round(v3[1], 4), round(v3[2], 4))

                loop_id = eid; lines.append(f"#{eid}=POLY_LOOP('',(#{vmap[k1]},#{vmap[k2]},#{vmap[k3]}));"); eid += 1
                bnd_id = eid; lines.append(f"#{eid}=FACE_OUTER_BOUND('',#{loop_id},.T.);"); eid += 1

                ax, ay, az = v2[0] - v1[0], v2[1] - v1[1], v2[2] - v1[2]
                bx, by, bz = v3[0] - v1[0], v3[1] - v1[1], v3[2] - v1[2]
                nx = ay * bz - az * by
                ny = az * bx - ax * bz
                nz = ax * by - ay * bx
                mag = math.sqrt(nx**2 + ny**2 + nz**2)
                if mag > 1e-9:
                    nx, ny, nz = nx/mag, ny/mag, nz/mag
                else:
                    nx, ny, nz = 0.0, 0.0, 1.0

                dir_id = eid; lines.append(f"#{eid}=DIRECTION('',({nx:.5f},{ny:.5f},{nz:.5f}));"); eid += 1
                ax_id = eid; lines.append(f"#{eid}=AXIS2_PLACEMENT_3D('',#{vmap[k1]},#{dir_id},#6);"); eid += 1
                pln_id = eid; lines.append(f"#{eid}=PLANE('',#{ax_id});"); eid += 1
                f_id = eid; lines.append(f"#{eid}=ADVANCED_FACE('',(#{bnd_id}),#{pln_id},.T.);"); eid += 1
                face_ids.append(f"#{f_id}")

            faces_str = ",".join(face_ids)
            shell_id = eid; lines.append(f"#{eid}=CLOSED_SHELL('{part.name}_shell',({faces_str}));"); eid += 1
            brep_id = eid; lines.append(f"#{eid}=MANIFOLD_SOLID_BREP('{part.name}',#{shell_id});"); eid += 1

            # Individual Part Product Hierarchy
            part_prod_id = eid; lines.append(f"#{eid}=PRODUCT('{part.name}','{part.name}','',(#3));"); eid += 1
            part_form_id = eid; lines.append(f"#{eid}=PRODUCT_DEFINITION_FORMATION('','',#{part_prod_id});"); eid += 1
            part_pdef_id = eid; lines.append(f"#{eid}=PRODUCT_DEFINITION('design','',#{part_form_id},#{pdef_ctx_id});"); eid += 1
            part_pshp_id = eid; lines.append(f"#{eid}=PRODUCT_DEFINITION_SHAPE('','',#{part_pdef_id});"); eid += 1
            part_rep_id = eid; lines.append(f"#{eid}=ADVANCED_BREP_SHAPE_REPRESENTATION('{part.name}',(#7,#{brep_id}),#11);"); eid += 1
            lines.append(f"#{eid}=SHAPE_DEFINITION_REPRESENTATION(#{part_pshp_id},#{part_rep_id});"); eid += 1

            # Assembly Usage & Placement Occurrence
            nao_id = eid; lines.append(f"#{eid}=NEXT_ASSEMBLY_USAGE_OCCURRENCE('{part_idx+1}','{part.name}','',#{top_pdef_id},#{part_pdef_id},'$');"); eid += 1
            cd_shp_id = eid; lines.append(f"#{eid}=PRODUCT_DEFINITION_SHAPE('Placement','Placement of item',#{nao_id});"); eid += 1
            rel_id = eid; lines.append(f"#{eid}=(REPRESENTATION_RELATIONSHIP('','',#{part_rep_id},#{top_rep_id})REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION(#{eid+1})SHAPE_REPRESENTATION_RELATIONSHIP());"); eid += 1
            lines.append(f"#{eid}=ITEM_DEFINED_TRANSFORMATION('','',#7,#7);"); eid += 1
            lines.append(f"#{eid}=CONTEXT_DEPENDENT_SHAPE_REPRESENTATION(#{rel_id},#{cd_shp_id});"); eid += 1

        lines.append("ENDSEC;")
        lines.append("END-ISO-10303-21;")
        return "\n".join(lines)

    @classmethod
    def export_single_part_step(
        cls,
        part: SolidPart,
        author: str = "MDIE Computational Engineer",
        localize: bool = True
    ) -> str:
        """
        Exports a single solid part as a standalone ISO 10303 STEP file.
        When localize=True, shifts the part to (0, 0, 0) with base on Z=0 for CAM/manufacturing readiness.
        """
        target = part.to_local_origin() if localize else part
        return cls.export_assembly(target.name, [target], author=author)

    @classmethod
    def export_parts_to_directory(
        cls,
        parts: List[SolidPart],
        output_dir: Path,
        localize: bool = True,
        export_stl: bool = True
    ) -> List[Path]:
        """
        Exports a list of SolidParts to individual files in output_dir.
        When localize=True, each part is transformed so that (X=0, Y=0) is centered and Z_min=0.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        exported: List[Path] = []
        manifest = []
        for part in parts:
            if not part.triangles:
                continue
            target = part.to_local_origin() if localize else part

            step_file = output_dir / f"{target.name}.step"
            with open(step_file, "w", encoding="utf-8") as f:
                f.write(cls.export_assembly(target.name, [target]))
            exported.append(step_file)

            stl_file = None
            if export_stl:
                from mdie.cad.assembly import MeshPrimitives
                stl_file = output_dir / f"{target.name}.stl"
                with open(stl_file, "wb") as f:
                    f.write(MeshPrimitives.export_binary_stl(target.triangles, model_name=target.name))
                exported.append(stl_file)

            dim_x, dim_y, dim_z = target.get_dimensions()
            manifest.append({
                "part_name": target.name,
                "dimensions_mm": {
                    "width_x": round(dim_x, 2),
                    "depth_y": round(dim_y, 2),
                    "height_z": round(dim_z, 2),
                },
                "assembly_origin_offset_mm": {
                    "x": round(target.origin_offset[0], 2),
                    "y": round(target.origin_offset[1], 2),
                    "z": round(target.origin_offset[2], 2),
                },
                "step_file": step_file.name,
                "stl_file": stl_file.name if stl_file else None
            })

        import json
        manifest_path = output_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        exported.append(manifest_path)

        return exported
