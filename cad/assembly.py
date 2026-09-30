"""
General Multi-Body Frame & Structural CAD Assembly Generator
Supports parametric generation of 3D spatial frames, chassis, tables, chairs, stands,
and trusses into OpenSCAD (.scad), Binary STL (.stl), and ISO-10303 STEP Solids (.step).
"""

import math
import struct
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
from cad.step_assembly import MultiBodySTEPExporter, SolidPart
from core.frame_model import FrameDesignModel, FrameGeometry

Point3D = Tuple[float, float, float]
Triangle = Tuple[Point3D, Point3D, Point3D]

class MeshPrimitives:
    """Deterministic 3D geometric mesh primitives for structural members and solids."""

    @staticmethod
    def create_cylinder_triangles(
        p1: Point3D,
        p2: Point3D,
        radius: float,
        n_slices: int = 16
    ) -> List[Triangle]:
        """Creates closed triangular mesh surface for a 3D cylindrical member between two 3D points."""
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        dz = p2[2] - p1[2]
        length = math.sqrt(dx**2 + dy**2 + dz**2)
        if length < 1e-6:
            return []

        w = (dx / length, dy / length, dz / length)
        u_cand = (0.0, 0.0, 1.0) if (abs(w[0]) > 0.1 or abs(w[1]) > 0.1) else (1.0, 0.0, 0.0)

        ux_raw = (u_cand[1]*w[2] - u_cand[2]*w[1],
                  u_cand[2]*w[0] - u_cand[0]*w[2],
                  u_cand[0]*w[1] - u_cand[1]*w[0])
        mag_u = math.sqrt(sum(x**2 for x in ux_raw))
        ux = tuple(x / max(mag_u, 1e-9) for x in ux_raw)

        uy = (w[1]*ux[2] - w[2]*ux[1],
              w[2]*ux[0] - w[0]*ux[2],
              w[0]*ux[1] - w[1]*ux[0])

        bot_ring: List[Point3D] = []
        top_ring: List[Point3D] = []
        for i in range(n_slices):
            theta = 2.0 * math.pi * i / n_slices
            ca = radius * math.cos(theta)
            sa = radius * math.sin(theta)
            bx = p1[0] + ca * ux[0] + sa * uy[0]
            by = p1[1] + ca * ux[1] + sa * uy[1]
            bz = p1[2] + ca * ux[2] + sa * uy[2]
            bot_ring.append((bx, by, bz))
            tx = p2[0] + ca * ux[0] + sa * uy[0]
            ty = p2[1] + ca * ux[1] + sa * uy[1]
            tz = p2[2] + ca * ux[2] + sa * uy[2]
            top_ring.append((tx, ty, tz))

        tris: List[Triangle] = []
        for i in range(n_slices):
            nxt = (i + 1) % n_slices
            tris.append((bot_ring[i], bot_ring[nxt], top_ring[nxt]))
            tris.append((bot_ring[i], top_ring[nxt], top_ring[i]))
            tris.append((p1, bot_ring[nxt], bot_ring[i]))
            tris.append((p2, top_ring[i], top_ring[nxt]))
        return tris

    @staticmethod
    def create_box_triangles(
        cx: float, cy: float, cz: float,
        wx: float, wy: float, wz: float
    ) -> List[Triangle]:
        """Creates closed triangular mesh facets for a 3D rectangular box/panel."""
        x0, x1 = cx - wx/2, cx + wx/2
        y0, y1 = cy - wy/2, cy + wy/2
        z0, z1 = cz - wz/2, cz + wz/2

        corners = [
            (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
            (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)
        ]

        faces = [
            (0, 2, 1), (0, 3, 2), # -Z bottom
            (4, 5, 6), (4, 6, 7), # +Z top
            (0, 1, 5), (0, 5, 4), # -Y front
            (2, 3, 7), (2, 7, 6), # +Y back
            (0, 4, 7), (0, 7, 3), # -X left
            (1, 2, 6), (1, 6, 5), # +X right
        ]

        return [(corners[f[0]], corners[f[1]], corners[f[2]]) for f in faces]

    @classmethod
    def export_binary_stl(cls, triangles: List[Triangle], model_name: str = "MDIE Structural Solid") -> bytes:
        """Serializes triangles into standard IEEE binary STL format."""
        header = f"MDIE Solid Model - {model_name}".encode('ascii')[:80].ljust(80, b'\0')
        n_tris = len(triangles)
        parts = [header, struct.pack("<I", n_tris)]

        for v1, v2, v3 in triangles:
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

            facet = struct.pack(
                "<ffffffffffffH",
                nx, ny, nz,
                v1[0], v1[1], v1[2],
                v2[0], v2[1], v2[2],
                v3[0], v3[1], v3[2],
                0
            )
            parts.append(facet)

        return b"".join(parts)


# --- Analytic primitive descriptions ---------------------------------------
# A "primitive" is an exact description of one member (box or tube) in model
# coordinates. The drawing generator consumes these to draw true silhouettes
# and the mesh builder consumes them to make the solid, so a sheet can never
# drift away from the exported geometry.
#
#   box  -> {"kind": "box",  "c": (x, y, z), "s": (sx, sy, sz)}
#   tube -> {"kind": "tube", "a": (x, y, z), "b": (x, y, z), "r": radius}


def primitives_to_triangles(prims: List[dict], n_slices: int = 12) -> List[Triangle]:
    """Build a closed mesh from a list of analytic primitives."""
    tris: List[Triangle] = []
    for p in prims:
        if p["kind"] == "box":
            cx, cy, cz = p["c"]
            sx, sy, sz = p["s"]
            tris.extend(MeshPrimitives.create_box_triangles(
                cx, cy, cz, sx, sy, sz))
        elif p["kind"] == "tube":
            # An optional "n" lets a member keep its own tessellation
            # density, so a described assembly meshes identically to the
            # solids exported from it.
            tris.extend(MeshPrimitives.create_cylinder_triangles(
                p["a"], p["b"], p["r"], n_slices=p.get("n", n_slices)))
    return tris


def armrest_primitives(
    w: float, d: float, h: float,
    arm_h: float, arm_pad_w: float, arm_pad_len: float,
    arm_pad_thick: float, arm_tube_r: float,
    side: float = -1.0,
) -> List[dict]:
    """
    Exact armrest sub-assembly: two cross brackets, two posts, one pad.

    ``side`` is -1 for the left arm and +1 for the right; the two are mirror
    images about the YZ plane, so a single sheet is drawn for both.
    """
    arm_x = side * (w / 2.0 + 25.0)
    bracket_len = abs(arm_x) - w / 2.0
    bracket_x = side * (w / 2.0 + bracket_len / 2.0)
    post_ys = (40.0, -d / 3.0)
    prims: List[dict] = []
    for post_y in post_ys:
        # Cross beam tying the post back to the seat-frame rail.
        prims.append({
            "kind": "box",
            "c": (bracket_x, post_y, h - arm_tube_r / 2.0),
            "s": (bracket_len, arm_tube_r * 0.8, arm_tube_r),
        })
        # Vertical post carrying the pad.
        prims.append({
            "kind": "tube",
            "a": (arm_x, post_y, h),
            "b": (arm_x, post_y, h + arm_h),
            "r": arm_tube_r,
        })
    prims.append({
        "kind": "box",
        "c": (arm_x, 10.0, h + arm_h + arm_pad_thick / 2.0),
        "s": (arm_pad_w, arm_pad_len, arm_pad_thick),
    })
    return prims


def assembly_primitives(model: FrameDesignModel) -> List[Tuple[str, List[dict]]]:
    """
    Exact description of the whole chair, grouped by item number.

    Used by the assembly drawing so the general-arrangement sheet shows the
    real members. The numbers mirror ``generate_assembly_parts``; the
    regression suite pins the two together.
    """
    g = model.geometry
    w, d, h = g.seat_width_mm, g.seat_depth_mm, g.seat_height_mm
    splay = math.radians(g.leg_splay_angle_deg)
    delta = h * math.tan(splay)
    r_leg = g.leg_profile.outer_dimension_mm / 2.0
    groups: List[Tuple[str, List[dict]]] = []

    if g.num_legs == 3:
        r_top = min(w, d) / 2.0
        r_bot = r_top + delta
        angles = [math.pi / 2.0, 7.0 * math.pi / 6.0, 11.0 * math.pi / 6.0]
        legs = [(f"Leg_{i+1}",
                 (r_top * math.cos(a), r_top * math.sin(a), h),
                 (r_bot * math.cos(a), r_bot * math.sin(a), 0.0))
                for i, a in enumerate(angles)]
    else:
        legs = [
            ("Leg_Front_Left",  (-w/2,  d/2, h), (-w/2 - delta,  d/2 + delta, 0.0)),
            ("Leg_Front_Right", ( w/2,  d/2, h), ( w/2 + delta,  d/2 + delta, 0.0)),
            ("Leg_Rear_Right",  ( w/2, -d/2, h), ( w/2 + delta, -d/2 - delta, 0.0)),
            ("Leg_Rear_Left",   (-w/2, -d/2, h), (-w/2 - delta, -d/2 - delta, 0.0)),
        ]
    for name, p_top, p_bot in legs:
        groups.append((name, [{"kind": "tube", "a": p_bot, "b": p_top,
                               "r": r_leg, "n": 16}]))

    if g.has_stretchers:
        sh = g.stretcher_height_mm
        sr = g.stretcher_profile.outer_dimension_mm / 2.0
        s_delta = (h - sh) * math.tan(splay)
        s_prims: List[dict] = []
        if g.num_legs == 3:
            r_s = (min(w, d) / 2.0) + s_delta
            angles = [math.pi / 2.0, 7.0 * math.pi / 6.0, 11.0 * math.pi / 6.0]
            pts = [(r_s * math.cos(a), r_s * math.sin(a), sh) for a in angles]
            for i in range(len(pts)):
                s_prims.append({"kind": "tube", "a": pts[i],
                                "b": pts[(i + 1) % len(pts)], "r": sr})
        else:
            xl, xr = -w/2 - s_delta, w/2 + s_delta
            yf, yr = d/2 + s_delta, -d/2 - s_delta
            for a, b in (((xl, yf, sh), (xr, yf, sh)), ((xl, yr, sh), (xr, yr, sh)),
                         ((xl, yf, sh), (xl, yr, sh)), ((xr, yf, sh), (xr, yr, sh))):
                s_prims.append({"kind": "tube", "a": a, "b": b, "r": sr})
        groups.append(("Lower_Stretchers", s_prims))

    f_dim = g.frame_profile.outer_dimension_mm
    groups.append(("Seat_Frame_Rails", [
        {"kind": "box", "c": (0.0,  d/2 - f_dim/2, h - f_dim/2), "s": (w, f_dim, f_dim)},
        {"kind": "box", "c": (0.0, -d/2 + f_dim/2, h - f_dim/2), "s": (w, f_dim, f_dim)},
        {"kind": "box", "c": (-w/2 + f_dim/2, 0.0, h - f_dim/2), "s": (f_dim, d, f_dim)},
        {"kind": "box", "c": ( w/2 - f_dim/2, 0.0, h - f_dim/2), "s": (f_dim, d, f_dim)},
    ]))

    if g.has_seat_plate:
        groups.append(("Seat_Pan_Deck", [
            {"kind": "box", "c": (0.0, 0.0, h + g.seat_thickness_mm / 2.0),
             "s": (w, d, g.seat_thickness_mm)}]))

    if g.has_arms:
        for side, name in [(-1.0, "Armrest_Left"), (1.0, "Armrest_Right")]:
            groups.append((name, armrest_primitives(
                w, d, h, g.armrest_height_above_seat_mm, g.armrest_width_mm,
                g.armrest_length_mm, 18.0,
                g.arm_profile.outer_dimension_mm / 2.0, side=side)))

    if g.has_backrest:
        back_h = g.backrest_height_above_seat_mm
        back_rad = math.radians(g.backrest_angle_deg - 90.0)
        dy_back = back_h * math.sin(back_rad)
        dz_back = back_h * math.cos(back_rad)
        b_prims: List[dict] = []
        for sx in (-1.0, 1.0):
            px = sx * (w/2 - r_leg)
            b_prims.append({"kind": "tube",
                            "a": (px, -d/2 + r_leg, h),
                            "b": (px, -d/2 + r_leg - dy_back, h + dz_back),
                            "r": r_leg})
        b_prims.append({
            "kind": "box",
            "c": (0.0, -d/2 + r_leg - dy_back * 0.7, h + dz_back * 0.7),
            "s": (w - 30.0, 16.0, back_h * 0.45)})
        groups.append(("Backrest_Assembly", b_prims))

    return groups


class FrameCADEngine:
    """Parametric CAD generator for multi-member spatial frames, tables, chairs, and stands."""

    @staticmethod
    def generate_openscad(model: FrameDesignModel) -> str:
        g = model.geometry
        m = model.material

        return f"""// ==================================================================
// MACHINE DESIGN INTELLIGENCE ENGINE (MDIE) - PARAMETRIC FRAME CAD
// Model: {model.name}
// Material: {m.name} (Sy = {m.yield_strength_mpa} MPa)
// ==================================================================
$fn = 36;

// Global Dimensions (mm)
seat_h      = {g.seat_height_mm:.1f};
seat_w      = {g.seat_width_mm:.1f};
seat_d      = {g.seat_depth_mm:.1f};
seat_thick  = {g.seat_thickness_mm:.1f};

leg_d       = {g.leg_profile.outer_dimension_mm:.1f};
leg_splay   = {g.leg_splay_angle_deg:.1f};
stretcher_h = {g.stretcher_height_mm:.1f};
stretcher_d = {g.stretcher_profile.outer_dimension_mm:.1f};

arm_h       = {g.armrest_height_above_seat_mm:.1f};
arm_len     = {g.armrest_length_mm:.1f};
arm_w       = {g.armrest_width_mm:.1f};
arm_thick   = 18.0;
arm_tube_d  = {g.arm_profile.outer_dimension_mm:.1f};

back_h      = {g.backrest_height_above_seat_mm:.1f};
back_angle  = {g.backrest_angle_deg:.1f};

// Assembly & Exploded View Controls
explode_distance = 0.0; // Change to e.g. 50.0 for exploded assembly view
show_legs        = true;
show_glides      = true;
show_stretchers  = true;
show_frame       = true;
show_seat_pan    = true;
show_armrests    = true;
show_backrest    = true;

// Colors
metal_color = [0.22, 0.26, 0.32, 1.0];
wood_color  = [0.72, 0.48, 0.28, 1.0];
cap_color   = [0.10, 0.10, 0.12, 1.0];

// Main Assembly Call
chair_assembly();

module chair_assembly() {{
    // 1. Support Legs
    if (show_legs) {{
        translate([0, 0, -explode_distance * 0.5])
        color(metal_color) {{
            if ({g.num_legs} == 3) {{
                tripod_r = min(seat_w, seat_d) / 2;
                leg(0, tripod_r, 0, 1);
                leg(-tripod_r * 0.866, -tripod_r * 0.5, -0.866, -0.5);
                leg( tripod_r * 0.866, -tripod_r * 0.5,  0.866, -0.5);
            }} else {{
                leg(-seat_w/2,  seat_d/2, -1,  1); // Front-Left
                leg( seat_w/2,  seat_d/2,  1,  1); // Front-Right
                leg( seat_w/2, -seat_d/2,  1, -1); // Rear-Right
                leg(-seat_w/2, -seat_d/2, -1, -1); // Rear-Left
            }}
        }}
    }}

    // 2. Leg Floor Glides / Caps
    if (show_glides) {{
        translate([0, 0, -explode_distance * 0.8])
        color(cap_color) {{
            if ({g.num_legs} == 3) {{
                tripod_r = min(seat_w, seat_d) / 2;
                foot_glide(0, tripod_r, 0, 1);
                foot_glide(-tripod_r * 0.866, -tripod_r * 0.5, -0.866, -0.5);
                foot_glide( tripod_r * 0.866, -tripod_r * 0.5,  0.866, -0.5);
            }} else {{
                foot_glide(-seat_w/2,  seat_d/2, -1,  1);
                foot_glide( seat_w/2,  seat_d/2,  1,  1);
                foot_glide( seat_w/2, -seat_d/2,  1, -1);
                foot_glide(-seat_w/2, -seat_d/2, -1, -1);
            }}
        }}
    }}

    // 3. Lower Perimeter Stretchers / Braces
    if (show_stretchers && {'true' if g.has_stretchers else 'false'}) {{
        translate([0, 0, -explode_distance * 0.25])
        color(metal_color) lower_stretchers();
    }}

    // 4. Seat Frame Perimeter Sub-structure
    if (show_frame) {{
        color(metal_color) seat_frame();
    }}

    // 5. Ergonomic Deck
    if (show_seat_pan && {'true' if g.has_seat_plate else 'false'}) {{
        translate([0, 0, explode_distance * 0.6])
        color(wood_color) seat_pan();
    }}

    // 6. Armrests
    if (show_armrests && {'true' if g.has_arms else 'false'}) {{
        translate([-explode_distance * 0.5, 0, explode_distance * 0.3])
            armrest_assembly(-1);
        translate([ explode_distance * 0.5, 0, explode_distance * 0.3])
            armrest_assembly( 1);
    }}

    // 7. Backrest Assembly
    if (show_backrest && {'true' if g.has_backrest else 'false'}) {{
        translate([0, -explode_distance * 0.7, explode_distance * 0.4])
            backrest_assembly();
    }}
}}

module leg(top_x, top_y, dir_x, dir_y) {{
    delta_splay = seat_h * tan(leg_splay);
    bot_x = top_x + dir_x * delta_splay;
    bot_y = top_y + dir_y * delta_splay;
    hull() {{
        translate([top_x, top_y, seat_h - 2])
            sphere(r = leg_d/2);
        translate([bot_x, bot_y, 0])
            cylinder(r = leg_d/2, h = 1);
    }}
}}

module foot_glide(top_x, top_y, dir_x, dir_y) {{
    delta_splay = seat_h * tan(leg_splay);
    bot_x = top_x + dir_x * delta_splay;
    bot_y = top_y + dir_y * delta_splay;
    translate([bot_x, bot_y, -5])
        cylinder(r = leg_d/2 + 2, h = 6);
}}

module lower_stretchers() {{
    delta_s = (seat_h - stretcher_h) * tan(leg_splay);
    x_l = -seat_w/2 - delta_s;
    x_r =  seat_w/2 + delta_s;
    y_f =  seat_d/2 + delta_s;
    y_r = -seat_d/2 - delta_s;

    // Front & Rear stretchers
    translate([0, y_f, stretcher_h])
        rotate([0, 90, 0])
            cylinder(r = stretcher_d/2, h = x_r - x_l, center = true);
    translate([0, y_r, stretcher_h])
        rotate([0, 90, 0])
            cylinder(r = stretcher_d/2, h = x_r - x_l, center = true);

    // Left & Right stretchers
    translate([x_l, 0, stretcher_h])
        rotate([90, 0, 0])
            cylinder(r = stretcher_d/2, h = y_f - y_r, center = true);
    translate([x_r, 0, stretcher_h])
        rotate([90, 0, 0])
            cylinder(r = stretcher_d/2, h = y_f - y_r, center = true);
}}

module seat_frame() {{
    f_d = {g.frame_profile.outer_dimension_mm:.1f};
    translate([0, 0, seat_h - f_d/2]) {{
        translate([0,  seat_d/2 - f_d/2, 0]) cube([seat_w, f_d, f_d], center=true);
        translate([0, -seat_d/2 + f_d/2, 0]) cube([seat_w, f_d, f_d], center=true);
        translate([-seat_w/2 + f_d/2, 0, 0]) cube([f_d, seat_d, f_d], center=true);
        translate([ seat_w/2 - f_d/2, 0, 0]) cube([f_d, seat_d, f_d], center=true);
    }}
}}

module seat_pan() {{
    translate([0, 0, seat_h + seat_thick/2])
        cube([seat_w, seat_d, seat_thick], center=true);
}}

module armrest_assembly(side) {{
    arm_x = side * (seat_w/2 + 25);
    // Bracket span: from seat-frame rail outer face to arm post axis
    bracket_len = abs(arm_x) - seat_w/2;
    bracket_x = side * (seat_w/2 + bracket_len/2);
    color(metal_color) {{
        // Mounting brackets tying each post to the seat frame rail
        for (post_y = [40, -seat_d/3]) {{
            translate([bracket_x, post_y, seat_h - arm_tube_d/2])
                cube([bracket_len, arm_tube_d*0.8, arm_tube_d], center=true);
        }}
        translate([arm_x, 40, seat_h])
            cylinder(r = arm_tube_d/2, h = arm_h);
        translate([arm_x, -seat_d/3, seat_h])
            cylinder(r = arm_tube_d/2, h = arm_h);
    }}
    color(wood_color) {{
        translate([arm_x, 10, seat_h + arm_h + arm_thick/2])
            cube([arm_w, arm_len, arm_thick], center=true);
    }}
}}

module backrest_assembly() {{
    r_back = leg_d/2;
    rad_b = (back_angle - 90) * 3.14159 / 180;
    dy = back_h * sin(rad_b);
    dz = back_h * cos(rad_b);

    color(metal_color) {{
        for (sx = [-1, 1]) {{
            hull() {{
                translate([sx * (seat_w/2 - r_back), -seat_d/2 + r_back, seat_h])
                    sphere(r = r_back);
                translate([sx * (seat_w/2 - r_back), -seat_d/2 + r_back - dy, seat_h + dz])
                    sphere(r = r_back);
            }}
        }}
    }}
    color(wood_color) {{
        translate([0, -seat_d/2 + r_back - dy*0.7, seat_h + dz*0.7])
            cube([seat_w - 30, 16, back_h * 0.45], center=true);
    }}
}}
"""

    @classmethod
    def generate_stl_triangles(cls, model: FrameDesignModel) -> List[Triangle]:
        g = model.geometry
        tris: List[Triangle] = []

        h = g.seat_height_mm
        w = g.seat_width_mm
        d = g.seat_depth_mm
        splay = math.radians(g.leg_splay_angle_deg)
        delta = h * math.tan(splay)
        r_leg = g.leg_profile.outer_dimension_mm / 2.0

        # 1. Support Legs
        if g.num_legs == 3:
            r_top = min(w, d) / 2.0
            r_bot = r_top + delta
            angles = [math.pi / 2.0, 7.0 * math.pi / 6.0, 11.0 * math.pi / 6.0]
            legs = [((r_top * math.cos(ang), r_top * math.sin(ang), h),
                     (r_bot * math.cos(ang), r_bot * math.sin(ang), 0.0)) for ang in angles]
        else:
            legs = [
                ((-w/2,  d/2, h), (-w/2 - delta,  d/2 + delta, 0)),
                (( w/2,  d/2, h), ( w/2 + delta,  d/2 + delta, 0)),
                (( w/2, -d/2, h), ( w/2 + delta, -d/2 - delta, 0)),
                ((-w/2, -d/2, h), (-w/2 - delta, -d/2 - delta, 0)),
            ]
        for p_top, p_bot in legs:
            tris.extend(MeshPrimitives.create_cylinder_triangles(p_bot, p_top, r_leg, n_slices=16))

        # 2. Lower Stretchers
        if g.has_stretchers:
            sh = g.stretcher_height_mm
            sr = g.stretcher_profile.outer_dimension_mm / 2.0
            stretcher_delta = (h - sh) * math.tan(splay)
            if g.num_legs == 3:
                r_stretcher = (min(w, d) / 2.0) + stretcher_delta
                angles = [math.pi / 2.0, 7.0 * math.pi / 6.0, 11.0 * math.pi / 6.0]
                pts = [(r_stretcher * math.cos(ang), r_stretcher * math.sin(ang), sh) for ang in angles]
                for i in range(len(pts)):
                    tris.extend(MeshPrimitives.create_cylinder_triangles(pts[i], pts[(i+1)%len(pts)], sr, 12))
            else:
                xl, xr = -w/2 - stretcher_delta, w/2 + stretcher_delta
                yf, yr =  d/2 + stretcher_delta, -d/2 - stretcher_delta
                tris.extend(MeshPrimitives.create_cylinder_triangles((xl, yf, sh), (xr, yf, sh), sr, 12))
                tris.extend(MeshPrimitives.create_cylinder_triangles((xl, yr, sh), (xr, yr, sh), sr, 12))
                tris.extend(MeshPrimitives.create_cylinder_triangles((xl, yf, sh), (xl, yr, sh), sr, 12))
                tris.extend(MeshPrimitives.create_cylinder_triangles((xr, yf, sh), (xr, yr, sh), sr, 12))

        # 3. Platform Pan
        if g.has_seat_plate:
            tris.extend(MeshPrimitives.create_box_triangles(0, 0, h + g.seat_thickness_mm/2, w, d, g.seat_thickness_mm))

        # 4. Rails
        f_dim = g.frame_profile.outer_dimension_mm
        tris.extend(MeshPrimitives.create_box_triangles(0,  d/2 - f_dim/2, h - f_dim/2, w, f_dim, f_dim))
        tris.extend(MeshPrimitives.create_box_triangles(0, -d/2 + f_dim/2, h - f_dim/2, w, f_dim, f_dim))
        tris.extend(MeshPrimitives.create_box_triangles(-w/2 + f_dim/2, 0, h - f_dim/2, f_dim, d, f_dim))
        tris.extend(MeshPrimitives.create_box_triangles( w/2 - f_dim/2, 0, h - f_dim/2, f_dim, d, f_dim))

        # 5. Upper Arms
        if g.has_arms:
            arm_h = g.armrest_height_above_seat_mm
            r_arm_tube = g.arm_profile.outer_dimension_mm / 2.0
            arm_pad_w = g.armrest_width_mm
            arm_pad_len = g.armrest_length_mm
            arm_pad_thick = 18.0

            for side in (-1.0, 1.0):
                arm_x = side * (w/2 + 25.0)
                bracket_len = abs(arm_x) - w/2
                bracket_x = side * (w/2 + bracket_len/2.0)
                for post_y in (40.0, -d/3.0):
                    tris.extend(MeshPrimitives.create_box_triangles(
                        bracket_x, post_y, h - r_arm_tube/2.0,
                        bracket_len, r_arm_tube*0.8, r_arm_tube))
                tris.extend(MeshPrimitives.create_cylinder_triangles((arm_x, 40.0, h), (arm_x, 40.0, h + arm_h), r_arm_tube, 12))
                tris.extend(MeshPrimitives.create_cylinder_triangles((arm_x, -d/3, h), (arm_x, -d/3, h + arm_h), r_arm_tube, 12))
                tris.extend(MeshPrimitives.create_box_triangles(arm_x, 10.0, h + arm_h + arm_pad_thick/2, arm_pad_w, arm_pad_len, arm_pad_thick))

        # 6. Backrest
        if g.has_backrest:
            back_h = g.backrest_height_above_seat_mm
            back_rad = math.radians(g.backrest_angle_deg - 90.0)
            dy_back = back_h * math.sin(back_rad)
            dz_back = back_h * math.cos(back_rad)

            tris.extend(MeshPrimitives.create_cylinder_triangles((-w/2 + r_leg, -d/2 + r_leg, h), (-w/2 + r_leg, -d/2 + r_leg - dy_back, h + dz_back), r_leg, 12))
            tris.extend(MeshPrimitives.create_cylinder_triangles(( w/2 - r_leg, -d/2 + r_leg, h), ( w/2 - r_leg, -d/2 + r_leg - dy_back, h + dz_back), r_leg, 12))
            tris.extend(MeshPrimitives.create_box_triangles(0, -d/2 + r_leg - dy_back * 0.7, h + dz_back * 0.7, w - 30.0, 16.0, back_h * 0.45))

        return tris

    @classmethod
    def export_binary_stl(cls, model: FrameDesignModel) -> bytes:
        triangles = cls.generate_stl_triangles(model)
        return MeshPrimitives.export_binary_stl(triangles, model_name=model.name)

    @classmethod
    def generate_assembly_parts(cls, model: FrameDesignModel) -> List[SolidPart]:
        g = model.geometry
        h = g.seat_height_mm
        w = g.seat_width_mm
        d = g.seat_depth_mm
        splay = math.radians(g.leg_splay_angle_deg)
        delta = h * math.tan(splay)
        r_leg = g.leg_profile.outer_dimension_mm / 2.0

        parts: List[SolidPart] = []

        # 1. Support Legs
        if g.num_legs == 3:
            r_top = min(w, d) / 2.0
            r_bot = r_top + delta
            angles = [math.pi / 2.0, 7.0 * math.pi / 6.0, 11.0 * math.pi / 6.0]
            legs_data = [(f"Leg_{i+1}",
                          (r_top * math.cos(ang), r_top * math.sin(ang), h),
                          (r_bot * math.cos(ang), r_bot * math.sin(ang), 0.0)) for i, ang in enumerate(angles)]
        else:
            legs_data = [
                ("Leg_Front_Left",  (-w/2,  d/2, h), (-w/2 - delta,  d/2 + delta, 0)),
                ("Leg_Front_Right", ( w/2,  d/2, h), ( w/2 + delta,  d/2 + delta, 0)),
                ("Leg_Rear_Right",  ( w/2, -d/2, h), ( w/2 + delta, -d/2 - delta, 0)),
                ("Leg_Rear_Left",   (-w/2, -d/2, h), (-w/2 - delta, -d/2 - delta, 0)),
            ]
        for name, p_top, p_bot in legs_data:
            t = MeshPrimitives.create_cylinder_triangles(p_bot, p_top, r_leg, n_slices=16)
            parts.append(SolidPart(name, t, color_rgb=(0.25, 0.3, 0.35)))

        # 2. Lower Stretchers
        if g.has_stretchers:
            sh = g.stretcher_height_mm
            sr = g.stretcher_profile.outer_dimension_mm / 2.0
            stretcher_delta = (h - sh) * math.tan(splay)
            s_tris = []
            if g.num_legs == 3:
                r_stretcher = (min(w, d) / 2.0) + stretcher_delta
                angles = [math.pi / 2.0, 7.0 * math.pi / 6.0, 11.0 * math.pi / 6.0]
                pts = [(r_stretcher * math.cos(ang), r_stretcher * math.sin(ang), sh) for ang in angles]
                for i in range(len(pts)):
                    s_tris.extend(MeshPrimitives.create_cylinder_triangles(pts[i], pts[(i+1)%len(pts)], sr, 12))
            else:
                xl, xr = -w/2 - stretcher_delta, w/2 + stretcher_delta
                yf, yr =  d/2 + stretcher_delta, -d/2 - stretcher_delta
                s_tris.extend(MeshPrimitives.create_cylinder_triangles((xl, yf, sh), (xr, yf, sh), sr, 12))
                s_tris.extend(MeshPrimitives.create_cylinder_triangles((xl, yr, sh), (xr, yr, sh), sr, 12))
                s_tris.extend(MeshPrimitives.create_cylinder_triangles((xl, yf, sh), (xl, yr, sh), sr, 12))
                s_tris.extend(MeshPrimitives.create_cylinder_triangles((xr, yf, sh), (xr, yr, sh), sr, 12))
            parts.append(SolidPart("Lower_Stretchers", s_tris, color_rgb=(0.25, 0.3, 0.35)))

        # 3. Rails
        f_dim = g.frame_profile.outer_dimension_mm
        frame_tris = []
        frame_tris.extend(MeshPrimitives.create_box_triangles(0,  d/2 - f_dim/2, h - f_dim/2, w, f_dim, f_dim))
        frame_tris.extend(MeshPrimitives.create_box_triangles(0, -d/2 + f_dim/2, h - f_dim/2, w, f_dim, f_dim))
        frame_tris.extend(MeshPrimitives.create_box_triangles(-w/2 + f_dim/2, 0, h - f_dim/2, f_dim, d, f_dim))
        frame_tris.extend(MeshPrimitives.create_box_triangles( w/2 - f_dim/2, 0, h - f_dim/2, f_dim, d, f_dim))
        parts.append(SolidPart("Seat_Frame_Rails", frame_tris, color_rgb=(0.2, 0.25, 0.3)))

        # 4. Pan Deck
        if g.has_seat_plate:
            pan_tris = MeshPrimitives.create_box_triangles(0, 0, h + g.seat_thickness_mm/2, w, d, g.seat_thickness_mm)
            parts.append(SolidPart("Seat_Pan_Deck", pan_tris, color_rgb=(0.7, 0.45, 0.25)))

        # 5. Armrests
        if g.has_arms:
            for side, name in [(-1.0, "Armrest_Left"), (1.0, "Armrest_Right")]:
                prims = armrest_primitives(
                    w, d, h,
                    g.armrest_height_above_seat_mm,
                    g.armrest_width_mm, g.armrest_length_mm,
                    18.0, g.arm_profile.outer_dimension_mm / 2.0, side=side,
                )
                parts.append(SolidPart(
                    name, primitives_to_triangles(prims, n_slices=12),
                    color_rgb=(0.6, 0.4, 0.2)))

        # 6. Backrest
        if g.has_backrest:
            back_h = g.backrest_height_above_seat_mm
            back_rad = math.radians(g.backrest_angle_deg - 90.0)
            dy_back = back_h * math.sin(back_rad)
            dz_back = back_h * math.cos(back_rad)
            back_tris = []
            back_tris.extend(MeshPrimitives.create_cylinder_triangles((-w/2 + r_leg, -d/2 + r_leg, h), (-w/2 + r_leg, -d/2 + r_leg - dy_back, h + dz_back), r_leg, 12))
            back_tris.extend(MeshPrimitives.create_cylinder_triangles(( w/2 - r_leg, -d/2 + r_leg, h), ( w/2 - r_leg, -d/2 + r_leg - dy_back, h + dz_back), r_leg, 12))
            back_tris.extend(MeshPrimitives.create_box_triangles(0, -d/2 + r_leg - dy_back * 0.7, h + dz_back * 0.7, w - 30.0, 16.0, back_h * 0.45))
            parts.append(SolidPart("Backrest_Assembly", back_tris, color_rgb=(0.7, 0.45, 0.25)))

        return parts

    @classmethod
    def generate_3d_preview_mesh(cls, model: FrameDesignModel) -> Dict[str, Any]:
        """Generates lightweight 3D geometry structure for real-time 3D rendering."""
        g = model.geometry
        h = g.seat_height_mm
        w = g.seat_width_mm
        d = g.seat_depth_mm
        splay = math.radians(g.leg_splay_angle_deg)
        delta = h * math.tan(splay)
        r_leg = g.leg_profile.outer_dimension_mm / 2.0

        cylinders = []
        legs = [
            ((-w/2,  d/2, h), (-w/2 - delta,  d/2 + delta, 0), "Column_FL"),
            (( w/2,  d/2, h), ( w/2 + delta,  d/2 + delta, 0), "Column_FR"),
            (( w/2, -d/2, h), ( w/2 + delta, -d/2 - delta, 0), "Column_RR"),
            ((-w/2, -d/2, h), (-w/2 - delta, -d/2 - delta, 0), "Column_RL"),
        ]
        for p_top, p_bot, lname in legs:
            cylinders.append({
                "name": lname,
                "p1": [p_bot[0], p_bot[2], p_bot[1]],
                "p2": [p_top[0], p_top[2], p_top[1]],
                "radius": r_leg,
                "color": "#475569"
            })

        if g.has_stretchers:
            sh = g.stretcher_height_mm
            sr = g.stretcher_profile.outer_dimension_mm / 2.0
            stretcher_delta = (h - sh) * math.tan(splay)
            xl, xr = -w/2 - stretcher_delta, w/2 + stretcher_delta
            yf, yr =  d/2 + stretcher_delta, -d/2 - stretcher_delta
            stretcher_lines = [
                ((xl, yf, sh), (xr, yf, sh)),
                ((xl, yr, sh), (xr, yr, sh)),
                ((xl, yf, sh), (xl, yr, sh)),
                ((xr, yf, sh), (xr, yr, sh)),
            ]
            for p1, p2 in stretcher_lines:
                cylinders.append({
                    "name": "Stretcher",
                    "p1": [p1[0], p1[2], p1[1]],
                    "p2": [p2[0], p2[2], p2[1]],
                    "radius": sr,
                    "color": "#334155"
                })

        boxes = [
            {
                "name": "Deck_Pan",
                "pos": [0, h + g.seat_thickness_mm/2, 0],
                "dims": [w, g.seat_thickness_mm, d],
                "color": "#b45309"
            }
        ]

        return {
            "name": model.name,
            "cylinders": cylinders,
            "boxes": boxes,
            "total_h": h + g.backrest_height_above_seat_mm
        }

    @classmethod
    def export_step_solid(cls, model: FrameDesignModel) -> str:
        parts = cls.generate_assembly_parts(model)
        return MultiBodySTEPExporter.export_assembly(
            assembly_name=model.name,
            parts=parts,
            author="MDIE Computational Engineer"
        )

    @classmethod
    def export_individual_parts(cls, model: FrameDesignModel, parts_dir: Path, localize: bool = True) -> List[Path]:
        """
        Exports individual STEP and STL files for every discrete solid part.
        When localize=True, centers each part on (X=0, Y=0) with base resting on Z=0.
        """
        parts = cls.generate_assembly_parts(model)
        return MultiBodySTEPExporter.export_parts_to_directory(
            parts=parts,
            output_dir=parts_dir,
            localize=localize,
            export_stl=True
        )

    export_stl = export_binary_stl


# Aliases for backwards compatibility
ChairCADEngine = FrameCADEngine

