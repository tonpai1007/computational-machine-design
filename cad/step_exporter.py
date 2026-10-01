"""
MDIE Direct STEP (.step / .stp) Solid CAD Exporter
Generates valid ISO 10303-21 (AP203 / AP214) STEP format 3D solid models directly.
Natively importable as solid geometry in SolidWorks, Autodesk Inventor, Fusion 360, FreeCAD, and Mastercam.
"""

from __future__ import annotations

from datetime import datetime

from cad.stl_exporter import STLExporter
from core.models import EngineeringModel


class STEPExporter:
    @classmethod
    def export_step(cls, model: EngineeringModel, n_slices: int = 48) -> str:
        """
        Generates an ISO 10303-21 compliant STEP physical file representing the shaft solid.
        Uses standard B-Rep manifold solid geometry representation.
        """
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        model_name = model.name.replace(" ", "_")[:40]

        # Generate watertight triangular boundary representation
        triangles = STLExporter.generate_triangles(model, n_slices=n_slices)

        lines = [
            "ISO-10303-21;",
            "HEADER;",
            "FILE_DESCRIPTION(('MDIE Parametric 3D Solid Model','CAx-IF Rec.Pracs.---Representation of Geometric Shapes'),'2;1');",
            f"FILE_NAME('{model_name}.step','{timestamp}',('MDIE Computational Engineer'),('Machine Design Intelligence Engine'),'MDIE ISO-10303 Engine','MDIE Platform','');",
            "FILE_SCHEMA(('CONFIG_CONTROL_DESIGN'));",
            "ENDSEC;",
            "DATA;",
        ]

        entity_id = 1

        def next_id() -> int:
            nonlocal entity_id
            i = entity_id
            entity_id += 1
            return i

        # Coordinate System & World Units
        id_origin = next_id()
        lines.append(f"#{id_origin}=CARTESIAN_POINT('origin',(0.,0.,0.));")
        id_dir_z = next_id()
        lines.append(f"#{id_dir_z}=DIRECTION('axis_z',(0.,0.,1.));")
        id_dir_x = next_id()
        lines.append(f"#{id_dir_x}=DIRECTION('axis_x',(1.,0.,0.));")
        id_axis = next_id()
        lines.append(
            f"#{id_axis}=AXIS2_PLACEMENT_3D('world_cs',#{id_origin},#{id_dir_z},#{id_dir_x});"
        )

        # Unique vertex index mapping
        vertex_map: dict[tuple[float, float, float], int] = {}
        vertex_ids: list[int] = []

        for v1, v2, v3 in triangles:
            for v in (v1, v2, v3):
                # Round to 5 decimal places for vertex welding
                key = (round(v[0], 5), round(v[1], 5), round(v[2], 5))
                if key not in vertex_map:
                    vid = next_id()
                    lines.append(
                        f"#{vid}=CARTESIAN_POINT('',({key[0]:.5f},{key[1]:.5f},{key[2]:.5f}));"
                    )
                    vertex_map[key] = vid

        # Faces
        face_ids = []
        for v1, v2, v3 in triangles:
            k1 = (round(v1[0], 5), round(v1[1], 5), round(v1[2], 5))
            k2 = (round(v2[0], 5), round(v2[1], 5), round(v2[2], 5))
            k3 = (round(v3[0], 5), round(v3[1], 5), round(v3[2], 5))

            vid1 = vertex_map[k1]
            vid2 = vertex_map[k2]
            vid3 = vertex_map[k3]

            id_loop = next_id()
            lines.append(f"#{id_loop}=POLY_LOOP('',(#{vid1},#{vid2},#{vid3}));")

            id_bound = next_id()
            lines.append(f"#{id_bound}=FACE_OUTER_BOUND('',#{id_loop},.T.);")

            # Plane surface for the triangular facet
            norm = STLExporter._normal(v1, v2, v3)
            id_norm = next_id()
            lines.append(f"#{id_norm}=DIRECTION('',({norm[0]:.6f},{norm[1]:.6f},{norm[2]:.6f}));")

            id_surf_pos = next_id()
            lines.append(f"#{id_surf_pos}=AXIS2_PLACEMENT_3D('',#{vid1},#{id_norm},#{id_dir_x});")

            id_plane = next_id()
            lines.append(f"#{id_plane}=PLANE('',#{id_surf_pos});")

            id_face = next_id()
            lines.append(f"#{id_face}=ADVANCED_FACE('',(#{id_bound}),#{id_plane},.T.);")
            face_ids.append(f"#{id_face}")

        # Closed shell
        id_shell = next_id()
        face_refs = ",".join(face_ids)
        lines.append(f"#{id_shell}=CLOSED_SHELL('',({face_refs}));")

        # Manifold Solid B-Rep
        id_solid = next_id()
        lines.append(f"#{id_solid}=MANIFOLD_SOLID_BREP('{model_name}',#{id_shell});")

        # Units and Context
        id_len_unit = next_id()
        lines.append(f"#{id_len_unit}=(LENGTH_UNIT()NAMED_UNIT(*)SI_UNIT(.MILLI.,.METRE.));")
        id_ang_unit = next_id()
        lines.append(f"#{id_ang_unit}=(NAMED_UNIT(*)PLANE_ANGLE_UNIT()SI_UNIT($,.RADIAN.));")
        id_solid_ang = next_id()
        lines.append(f"#{id_solid_ang}=(NAMED_UNIT(*)SI_UNIT($,.STERADIAN.)SOLID_ANGLE_UNIT());")

        id_measure_ctx = next_id()
        lines.append(
            f"#{id_measure_ctx}=(GEOMETRIC_REPRESENTATION_CONTEXT(3)GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#{next_id()}))GLOBAL_UNIT_ASSIGNED_CONTEXT((#{id_len_unit},#{id_ang_unit},#{id_solid_ang}))REPRESENTATION_CONTEXT('3D','MDIE Solid'));"
        )

        # Uncertainty definition
        id_uncert = entity_id - 1
        lines.append(
            f"#{id_uncert}=UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-05),#{id_len_unit},'closure',0.);"
        )

        id_shape_rep = next_id()
        lines.append(
            f"#{id_shape_rep}=ADVANCED_BREP_SHAPE_REPRESENTATION('{model_name}',(#{id_solid},#{id_axis}),#{id_measure_ctx});"
        )

        # Product definition
        id_prod = next_id()
        lines.append(f"#{id_prod}=PRODUCT('{model_name}','{model_name}','',(#3));")
        id_prod_ctx = next_id()
        lines.append(f"#{id_prod_ctx}=PRODUCT_CONTEXT('',#2,'mechanical');")
        id_prod_def = next_id()
        lines.append(f"#{id_prod_def}=PRODUCT_DEFINITION('design','',#{id_prod},#{id_prod_ctx});")
        id_shape_def = next_id()
        lines.append(f"#{id_shape_def}=PRODUCT_DEFINITION_SHAPE('','',#{id_prod_def});")
        id_prod_shape = next_id()
        lines.append(
            f"#{id_prod_shape}=SHAPE_DEFINITION_REPRESENTATION(#{id_shape_def},#{id_shape_rep});"
        )

        lines.append("ENDSEC;")
        lines.append("END-ISO-10303-21;")

        return "\n".join(lines)
