"""
Per-part 2D engineering drawing sheets for the chair frame (ISO 128 / ANSI Y14.5).

Every dimension is read from :class:`FrameDesignModel` (see
``core/frame_model.py``) so the drawings are exact and regenerable --
nothing is measured off a mesh. This deliberately does NOT project the STL:
an STL is a triangle soup with no units, features, or sharp edges, so any
dimension taken from it would be a guess.

Outputs per part:
  * ``<part>.svg``            vector drawing sheet (third-angle projection)
  * ``chair_drawings.html``   printable A4 sheet embedding every part
  * ``chair_drawings.pdf``    same sheet, rasterised via matplotlib

Run::

    python -m drafting.part_drawings
    python -m drafting.part_drawings --outdir Project/chair/drawings
"""

from __future__ import annotations

import argparse
import math
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Any

from cad.assembly import Primitive, armrest_primitives
from core.frame_model import (
    ARM_PAD_THICKNESS_MM,
    FrameDesignModel,
    FrameGeometry,
    TubeProfile,
    resolve_armrest,
)

DEFAULT_OUTDIR = Path("Project/chair/drawings")

# ---------------------------------------------------------------- palette ----
INK = "#0f172a"
LINE = "#0f172a"
HIDDEN = "#94a3b8"
CENTER = "#dc2626"
DIMC = "#2563eb"
MUTED = "#64748b"
FILL = "#f1f5f9"
PAPER = "#ffffff"


# ------------------------------------------------------------- primitives ----
# ``svg`` is the list of SVG element strings that gets joined into the sheet,
# so every drawing helper takes it as ``list[str]`` and appends to it.
def _line(
    svg: list[str],
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    color: str = LINE,
    w: float = 0.6,
    dash: str | None = None,
    cap: str = "round",
) -> None:
    d = f' stroke-dasharray="{dash}"' if dash else ""
    svg.append(
        f'<line x1="{x0:.2f}" y1="{y0:.2f}" x2="{x1:.2f}" y2="{y1:.2f}" '
        f'stroke="{color}" stroke-width="{w}"{d} stroke-linecap="{cap}"/>'
    )


def _circle(
    svg: list[str],
    cx: float,
    cy: float,
    r: float,
    color: str = LINE,
    w: float = 0.6,
    fill: str = "none",
    dash: str | None = None,
) -> None:
    d = f' stroke-dasharray="{dash}"' if dash else ""
    svg.append(
        f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{fill}" '
        f'stroke="{color}" stroke-width="{w}"{d}/>'
    )


def _rect(
    svg: list[str],
    x: float,
    y: float,
    w: float,
    h: float,
    color: str = LINE,
    sw: float = 0.6,
    fill: str = FILL,
    dash: str | None = None,
) -> None:
    d = f' stroke-dasharray="{dash}"' if dash else ""
    svg.append(
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" '
        f'fill="{fill}" stroke="{color}" stroke-width="{sw}"{d}/>'
    )


def _text(
    svg: list[str],
    x: float,
    y: float,
    s: str,
    size: float = 3.0,
    color: str = INK,
    anchor: str = "middle",
    weight: str = "normal",
    italic: bool = False,
    rotate: float | None = None,
    halo: bool = True,
) -> None:
    """
    Draw sheet text with a white halo so it stays readable where it crosses
    geometry or dimension lines. ``paint-order`` strokes the halo behind the
    glyph fill, which keeps the letterforms crisp at any zoom.
    """
    st = ' font-style="italic"' if italic else ""
    tr = f' transform="rotate({rotate} {x:.2f} {y:.2f})"' if rotate is not None else ""
    po = ""
    if halo:
        po = (
            f' stroke="{PAPER}" stroke-width="{size * 0.42:.2f}" '
            f'paint-order="stroke" stroke-linejoin="round"'
        )
    svg.append(
        f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" fill="{color}" '
        f'text-anchor="{anchor}" font-weight="{weight}"{st}{tr}{po}>'
        f"{escape(s)}</text>"
    )


# Text sizes (mm on an A4 sheet). ISO 3098 nominal is ~2.5 mm, which is
# unreadable on screen; these are sized for legibility when zoomed in a PDF
# viewer while still fitting the sheet.
TXT_DIM = 4.2  # dimension values
TXT_VIEW = 4.0  # view titles
TXT_NOTE = 3.4  # notes body
TXT_HEAD = 4.0  # notes heading
TXT_BLOCK = 3.4  # title block cells
TXT_SMALL = 3.2  # projection symbol caption

# Armrest build constants, mirroring cad.assembly so the armrest
# sheet's extents match the exported solid.
ARM_PAD_THICKNESS_MM = 18.0
ARM_STANDOFF_MM = 25.0


ARROW_LEN = 1.8  # arrowhead length used by _dim_h / _dim_v


def _dim_h(
    svg: list[str],
    x0: float,
    x1: float,
    y: float,
    label: str,
    color: str = DIMC,
    size: float = TXT_DIM,
    tick: float = 2.0,
    right_edge: float | None = None,
) -> None:
    """Horizontal linear dimension: line runs parallel to the measurement.

    ISO 128: the dimension line lies on the axis being measured, with the
    arrowhead tips touching the extension lines and pointing outward. When
    the space between the arrowheads is too small for the text, ISO 128
    puts the text outside the dimension line on a short leader -- a narrow
    view would otherwise print its own value across its own arrowheads.
    """
    if abs(x1 - x0) < 1e-6:
        return
    lo, hi = (x0, x1) if x0 <= x1 else (x1, x0)
    _line(svg, lo, y, hi, y, color, 0.35)
    _arrow_head(svg, lo, y, -1.0, 0.0, color)
    _arrow_head(svg, hi, y, 1.0, 0.0, color)
    w = _text_width(label, size)
    if w <= (hi - lo) - 2.0 * ARROW_LEN - 1.2:
        _text(svg, (lo + hi) / 2.0, y + 1.2, label, size=size, color=color)
        return
    if right_edge is not None and hi + 2.6 + w <= right_edge:
        _line(svg, hi, y, hi + 2.6 + w, y, color, 0.25)
        _text(svg, hi + 2.6, y + 1.2, label, size=size, color=color, anchor="start")
    else:
        _line(svg, lo - 2.6 - w, y, lo, y, color, 0.25)
        _text(svg, lo - 2.6, y + 1.2, label, size=size, color=color, anchor="end")


def _dim_v(
    svg: list[str],
    y0: float,
    y1: float,
    x: float,
    label: str,
    color: str = DIMC,
    size: float = TXT_DIM,
    tick: float = 2.0,
    side: int = 1,
) -> None:
    """Vertical linear dimension: line runs parallel to the measurement.

    A value that fits between the arrowheads is centred on the line. One
    that does not is set beside the line horizontally: the space above a
    view is already taken by its caption and by the dimensions of the view
    stacked over it, so a vertical run-out there would collide.
    """
    if abs(y1 - y0) < 1e-6:
        return
    lo, hi = (y0, y1) if y0 <= y1 else (y1, y0)
    _line(svg, x, lo, x, hi, color, 0.35)
    _arrow_head(svg, x, lo, 0.0, -1.0, color)
    _arrow_head(svg, x, hi, 0.0, 1.0, color)
    mid = (lo + hi) / 2.0
    w = _text_width(label, size)
    if w <= (hi - lo) - 2.0 * ARROW_LEN - 1.2:
        # anchor="middle" centres the rotated run on the line, whichever way
        # the rotation sends it.
        _text(svg, x + 1.6 * side, mid, label, size=size, color=color, anchor="middle", rotate=-90)
        return
    clear = 2.2
    if side > 0:
        _line(svg, x, mid, x + clear, mid, color, 0.25)
        _text(svg, x + clear + 0.6, mid + 1.2, label, size=size, color=color, anchor="start")
    else:
        _line(svg, x - clear, mid, x, mid, color, 0.25)
        _text(svg, x - clear - 0.6, mid + 1.2, label, size=size, color=color, anchor="end")


def _arrow_head(
    svg: list[str],
    x: float,
    y: float,
    dx: float,
    dy: float,
    color: str,
    length: float = 1.8,
    half_width: float = 0.45,
) -> None:
    """Filled arrowhead with its tip at (x, y), pointing along (dx, dy)."""
    import math as _m

    mag = _m.hypot(dx, dy)
    if mag < 1e-9:
        return
    ux, uy = dx / mag, dy / mag
    px, py = -uy, ux  # perpendicular unit vector
    bx, by = x - length * ux, y - length * uy  # base centre
    p2 = (bx + half_width * px, by + half_width * py)
    p3 = (bx - half_width * px, by - half_width * py)
    svg.append(
        f'<polygon points="{x:.2f},{y:.2f} {p2[0]:.2f},{p2[1]:.2f} '
        f'{p3[0]:.2f},{p3[1]:.2f}" fill="{color}"/>'
    )


def _centerline(svg: list[str], x0: float, y0: float, x1: float, y1: float) -> None:
    _line(svg, x0, y0, x1, y1, CENTER, 0.35, dash="3,1.5,1,1.5")


def _hatch_rect(
    svg: list[str],
    x: float,
    y: float,
    w: float,
    h: float,
    spacing: float = 2.2,
    color: str = LINE,
) -> None:
    """Section hatching for a cut face (ISO 128 45-degree convention)."""
    i = 0
    t = -h
    while t < w + h:
        x0, y0 = max(x, x + t), y + max(0.0, min(h, -t))
        x1, y1 = min(x + w, x + t + h), y + max(0.0, min(h, w - t))
        if x1 > x0 and y1 > y0:
            _line(svg, x0, y0, x1, y1, color, 0.25)
        t += spacing
        i += 1


# ------------------------------------------------------------ part records ---
@dataclass
class PartDrawing:
    """One part's drawing: a title, its profiles, and its view geometry."""

    key: str
    title: str
    qty: int
    material: str
    profile: TubeProfile
    length_mm: float
    note: str = ""
    sectioned: bool = True
    views: list[Any] = field(default_factory=list)
    # Plan dimensions (X and Y extent). When both are set and differ, the
    # sheet is laid out as a full top/front/side orthographic set.
    width_x_mm: float | None = None
    depth_y_mm: float | None = None
    # Z extent for the front/side views. Defaults to length_mm.
    height_z_mm: float | None = None
    # Exact analytic members (from cad.assembly). When present the
    # sheet draws true silhouettes instead of a bounding rectangle.
    primitives: list[Primitive] | None = None
    # Per-frame feature dimensions: frame -> (dims_h, dims_v), each entry a
    # (start, end, at, text) tuple in model coordinates.
    view_dims: dict[str, tuple[list[tuple[float, float, str, str]], ...]] | None = None


def _prim_extent(prims: list[Primitive], u: int) -> tuple[float, float]:
    """Extreme extent along model axis ``u`` of a list of primitives.

    A tube's reach along an axis is ``r * sqrt(1 - w_u**2)``, not ``r``: a
    splayed column is only as wide across as its cross-section allows, so
    quoting the full radius would overstate the part. Reading the extent off
    the geometry is what keeps a sheet from disagreeing with its own solid.
    """
    vals: list[float] = []
    for p in prims:
        if p["kind"] == "box":
            vals += [p["c"][u] - p["s"][u] / 2.0, p["c"][u] + p["s"][u] / 2.0]
        else:
            a, b, r = p["a"][u], p["b"][u], p["r"]
            d = [p["b"][i] - p["a"][i] for i in range(3)]
            length = math.sqrt(sum(x * x for x in d)) or 1.0
            wu = d[u] / length
            reach = r * math.sqrt(max(0.0, 1.0 - wu * wu))
            vals += [min(a, b) - reach, max(a, b) + reach]
    return min(vals), max(vals)


def _leg_len(g: FrameGeometry) -> float:
    """True slanted length of a column (hypotenuse of rise and splay offset)."""
    return math.hypot(
        g.seat_height_mm, g.seat_height_mm * math.tan(math.radians(g.leg_splay_angle_deg))
    )


def build_parts(model: FrameDesignModel) -> list[PartDrawing]:
    """Derive the per-part drawing records from the parametric model."""
    g = model.geometry
    L = _leg_len(g)
    rail_len = g.seat_width_mm
    side_rail = g.seat_depth_mm
    arm_len = g.armrest_length_mm
    stretch = g.seat_width_mm
    stretch_d = g.seat_depth_mm
    # Stretcher footprint: the legs are splayed, so at stretcher height the
    # perimeter is wider than the seat span by the splay offset *at that
    # height*, plus the tube radius on each side. See assembly.py
    # ``lower_stretchers``: delta_s = (seat_h - stretcher_h) * tan(splay).
    splay = math.radians(g.leg_splay_angle_deg)
    stretcher_r = g.stretcher_profile.outer_dimension_mm / 2.0
    delta_s = (g.seat_height_mm - g.stretcher_height_mm) * math.tan(splay)
    w_floor = g.seat_width_mm + 2.0 * (delta_s + stretcher_r)
    d_floor = g.seat_depth_mm + 2.0 * (delta_s + stretcher_r)

    # Armrest sub-assembly extents, derived the same way ``assembly.py``
    # builds it: bracket stand-off + pad across X, post spread + pad along
    # Y, post rise + pad thickness + tube half-round at the foot in Z.
    arm_tube_d = g.arm_profile.outer_dimension_mm
    arm_pad_thick = ARM_PAD_THICKNESS_MM
    # Same primitives the STEP is meshed from, so the views show the real
    # posts, cross beams and pad rather than a bounding box.
    arm_ag = resolve_armrest(
        g, side=-1.0, arm_tube_r=arm_tube_d / 2.0, pad_thickness_mm=arm_pad_thick
    )
    arm_prims = armrest_primitives(arm_ag)
    # Every dimension coordinate is read back off the drawn geometry. Deriving
    # them from the model instead let the sign slip: the sheet is drawn for
    # the left arm (negative X) while a hand-written arm_x was positive, so
    # the pad-width dimension was anchored to empty space.
    ax0, ax1 = _prim_extent(arm_prims, 0)
    ay0, ay1 = _prim_extent(arm_prims, 1)
    az0, az1 = _prim_extent(arm_prims, 2)
    arm_dx, arm_dy, arm_dz = ax1 - ax0, ay1 - ay0, az1 - az0
    pad = max((p for p in arm_prims if p["kind"] == "box"), key=lambda p: p["s"][2])
    arm_x = pad["c"][0]
    arm_pad_w = pad["s"][0]
    # Post spacing anchors come from the resolved armrest geometry, so the
    # sheet cannot drift from the post positions the STEP and physics use.
    d_post, d_leg = arm_ag.front_post_y_mm, arm_ag.rear_post_y_mm
    arm_y_pad0 = pad["c"][1] - pad["s"][1] / 2.0
    arm_y_pad1 = pad["c"][1] + pad["s"][1] / 2.0
    arm_z_top = pad["c"][2] + pad["s"][2] / 2.0
    arm_z_post = az0 + arm_tube_d / 2.0

    parts = [
        PartDrawing(
            "Leg_Front_Left",
            "เสาหน้าซ้าย  FRONT LEFT LEG",
            1,
            model.material.name,
            g.leg_profile,
            L,
            f"เสาเอียงออก {g.leg_splay_angle_deg:g}°",
        ),
        PartDrawing(
            "Leg_Front_Right",
            "เสาหน้าขวา  FRONT RIGHT LEG",
            1,
            model.material.name,
            g.leg_profile,
            L,
            f"เสาเอียงออก {g.leg_splay_angle_deg:g}°",
        ),
        PartDrawing(
            "Leg_Rear_Left",
            "เสาหลังซ้าย  REAR LEFT LEG",
            1,
            model.material.name,
            g.leg_profile,
            L,
            f"เสาเอียงออก {g.leg_splay_angle_deg:g}°",
        ),
        PartDrawing(
            "Leg_Rear_Right",
            "เสาหลังขวา  REAR RIGHT LEG",
            1,
            model.material.name,
            g.leg_profile,
            L,
            f"เสาเอียงออก {g.leg_splay_angle_deg:g}°",
        ),
        PartDrawing(
            "Seat_Frame_Rails",
            "คานโครงเบาะ  SEAT FRAME RAILS",
            1,
            model.material.name,
            g.frame_profile,
            rail_len,
            "คานหน้า+หลัง",
            width_x_mm=g.seat_width_mm,
            depth_y_mm=g.seat_depth_mm,
            height_z_mm=g.frame_profile.outer_dimension_mm,
        ),
        PartDrawing(
            "Seat_Pan_Deck",
            "เบาะนั่ง  SEAT PAN DECK",
            1,
            model.material.name,
            TubeProfile(
                profile_type="square_solid",
                outer_dimension_mm=g.seat_thickness_mm,
                wall_thickness_mm=0.0,
            ),
            g.seat_depth_mm,
            "แผ่นเบาะบนกรอบ",
            width_x_mm=g.seat_width_mm,
            depth_y_mm=g.seat_depth_mm,
            height_z_mm=g.seat_thickness_mm,
        ),
        PartDrawing(
            "Armrest_Assembly",
            "ชุดท่อแขน  ARMREST ASSEMBLY",
            2,
            model.material.name,
            g.arm_profile,
            arm_len,
            "ท่อแขนตั้ง 2 เสา + แขนตั้งฉาก 2 ชิ้น + หมอนรอง",
            width_x_mm=arm_dx,
            depth_y_mm=arm_dy,
            height_z_mm=arm_dz,
            primitives=arm_prims,
            view_dims={
                # Pad width is only dimensioned on the front view:
                # the plan would repeat the same value over the same
                # member, and repeating it crowds a small drawing.
                "PLAN": (
                    [],
                    [
                        (d_leg, d_post, "left", f"{d_post - d_leg:g}"),
                        (arm_y_pad0, arm_y_pad1, "right", f"{g.armrest_length_mm:g}"),
                    ],
                ),
                "FRONT": (
                    [(arm_x - arm_pad_w / 2.0, arm_x + arm_pad_w / 2.0, "above", f"{arm_pad_w:g}")],
                    [
                        (
                            arm_z_post,
                            arm_z_post + g.armrest_height_above_seat_mm,
                            "left",
                            f"{g.armrest_height_above_seat_mm:g}",
                        )
                    ],
                ),
                "SIDE": (
                    [
                        (d_leg, d_post, "below", f"{d_post - d_leg:g}"),
                        (arm_y_pad0, arm_y_pad1, "below", f"{g.armrest_length_mm:g}"),
                    ],
                    [
                        (
                            arm_z_post,
                            arm_z_post + g.armrest_height_above_seat_mm,
                            "left",
                            f"{g.armrest_height_above_seat_mm:g}",
                        ),
                        (arm_z_top - arm_pad_thick, arm_z_top, "right", f"{arm_pad_thick:g}"),
                    ],
                ),
            },
        ),
        PartDrawing(
            "Backrest_Assembly",
            "โครงพนัก  BACKREST ASSEMBLY",
            1,
            model.material.name,
            g.frame_profile,
            g.backrest_height_above_seat_mm,
            f"เอียงพนัก {g.backrest_angle_deg:g}°",
        ),
        PartDrawing(
            "Lower_Stretchers",
            "สตรัชเตอร์  LOWER STRETCHERS",
            1,
            model.material.name,
            g.stretcher_profile,
            stretch,
            f"สูง {g.stretcher_height_mm:g} mm จากพื้น",
            width_x_mm=w_floor,
            depth_y_mm=d_floor,
            height_z_mm=g.stretcher_profile.outer_dimension_mm,
        ),
    ]
    return parts


# ------------------------------------------------------------ sheet render ---
def _profile_label(p: TubeProfile) -> str:
    od = p.outer_dimension_mm
    if p.profile_type in ("round_tube", "square_tube"):
        return f"{p.profile_type.split('_')[0].upper()} {od:g}×{p.wall_thickness_mm:g}"
    return f"{p.profile_type.split('_')[0].upper()} {od:g}"


def _char_adv(ch: str) -> float:
    """Approximate advance width of one glyph, in em, for the sheet font."""
    if unicodedata.combining(ch):
        return 0.0
    o = ord(ch)
    if 0x0E00 <= o <= 0x0E7F:  # Thai
        return 0.62
    if ch in "iljt.,:;'|!()[]":
        return 0.32
    if ch in "MW":
        return 0.92
    if ch.isupper() or ch.isdigit():
        return 0.64
    return 0.56


def _text_width(s: str, size: float) -> float:
    """Rendered width of ``s`` in mm. Used to fit text and to keep it clear."""
    return sum(_char_adv(c) for c in s) * size


def _fit_size(
    s: str, avail_mm: float, preferred: float, min_size: float = 2.4, ratio: float = 0.62
) -> float:
    """Largest font size (mm) at which ``s`` fits inside ``avail_mm``."""
    if not s or avail_mm <= 0.0:
        return preferred
    need = _text_width(s, preferred)
    if need <= avail_mm:
        return preferred
    scaled = preferred * avail_mm / need
    # Below this the text stops being readable, so let the caller deal with
    # the overflow rather than emitting illegible 1 mm type.
    return max(min_size, scaled)


def _notes_block(
    svg: list[str],
    right_col_w: float,
    top: float,
    lines: Sequence[str],
    head: float = TXT_HEAD,
    size: float = TXT_NOTE,
    lead: float = 6.5,
    step: float = 5.6,
) -> float:
    """Notes column, anchored inside the right-hand column.

    The notes used to be right-anchored just to the left of the title block,
    which let a long Thai note run back under the drawing area and print
    across a view caption. Keeping the text inside its own column and
    fitting it to that width is the fix.
    """
    W = 297.0
    x_right = W - 10.0 - 4.0
    avail = right_col_w - 8.0
    _text(
        svg,
        x_right,
        top,
        "หมายเหตุ  NOTES",
        size=head,
        anchor="end",
        weight="bold",
        color=INK,
        halo=False,
    )
    for i, n in enumerate(lines):
        _text(
            svg,
            x_right,
            top + lead + i * step,
            n,
            size=_fit_size(n, avail, size, min_size=2.8),
            anchor="end",
            color=INK,
            halo=False,
        )
    return top + lead + len(lines) * step


def _title_block(
    svg: list[str],
    x: float,
    y: float,
    w: float,
    h: float,
    part: PartDrawing,
    model: FrameDesignModel,
    scale_text: str,
) -> None:
    m = model.material
    rows = [
        ("DRAWING", "2D ENGINEERING DRAWING"),
        ("PART", part.title),
        ("MATERIAL", m.name),
        ("YIELD / ULT", f"{m.yield_strength_mpa:g} / {m.ultimate_strength_mpa:g} MPa"),
        ("PROFILE", _profile_label(part.profile)),
        ("LENGTH", f"{part.length_mm:g} mm"),
        ("QTY", f"{part.qty}"),
        ("SCALE", scale_text),
        ("UNITS", "mm"),
        ("STANDARD", "ISO 128 / ANSI Y14.5  3rd angle"),
    ]
    _rect(svg, x, y, w, h, INK, 0.8, fill=PAPER)
    rh = h / len(rows)
    # The key column has to hold its longest label ("STANDARD", "YIELD / ULT")
    # or the keys run into the values, so size it from the labels themselves.
    key_w = max(_text_width(k, TXT_BLOCK) for k, _ in rows) + 2.6
    val_w = w - key_w - 3.0
    for i, (k, v) in enumerate(rows):
        yy = y + i * rh
        if i:
            _line(svg, x, yy, x + w, yy, INK, 0.25)
        _line(svg, x + key_w, y, x + key_w, y + h, INK, 0.25)
        _text(
            svg,
            x + 1.6,
            yy + rh * 0.68,
            k,
            size=_fit_size(k, key_w - 2.2, TXT_BLOCK),
            color=MUTED,
            anchor="start",
            weight="bold",
        )
        # Shrink to fit rather than spill outside the block.
        _text(
            svg,
            x + key_w + 1.4,
            yy + rh * 0.68,
            v,
            size=_fit_size(v, val_w, TXT_BLOCK),
            color=INK,
            anchor="start",
        )


def _projection_symbol(
    svg: list[str], x: float, y: float, r: float, third_angle: bool = True
) -> None:
    """ISO 5456 projection-method symbol (cone frustum + truncated cone)."""
    svg.append(
        f'<polygon points="{x:.2f},{y - r:.2f} {x - r * 0.62:.2f},{y:.2f} '
        f'{x + r * 0.62:.2f},{y:.2f}" fill="{PAPER}" stroke="{INK}" '
        f'stroke-width="0.5"/>'
    )
    svg.append(
        f'<polygon points="{x:.2f},{y - r:.2f} {x - r * 0.62:.2f},{y:.2f} '
        f'{x - r * 0.9:.2f},{y + r * 0.9:.2f}" fill="{INK}"/>'
    )
    if third_angle:
        _line(svg, x - r * 0.95, y - r * 0.75, x - r * 0.95, y + r * 0.75, INK, 0.5)
    _circle(svg, x, y - r, 0.001, INK, 0)


def _round_tube_section(
    svg: list[str],
    cx: float,
    cy: float,
    p: TubeProfile,
    r_out: float,
    r_in: float,
    hatched: bool = True,
) -> None:
    _circle(svg, cx, cy, r_out, INK, 0.6, fill=FILL)
    _circle(svg, cx, cy, r_in, INK, 0.5, fill=PAPER)
    _centerline(svg, cx - r_out - 1.6, cy, cx + r_out + 1.6, cy)
    _centerline(svg, cx, cy - r_out - 1.6, cx, cy + r_out + 1.6)
    if hatched:
        # 45-degree hatch confined to the annular wall.
        step = 1.5
        t = -2 * r_out
        while t < 2 * r_out:
            x0, y0 = cx + t, cy - r_out
            x1, y1 = cx + t + 2 * r_out, cy + r_out
            seg = _clip_annulus(x0, y0, x1, y1, cx, cy, r_in, r_out)
            for ax, ay, bx, by in seg:
                _line(svg, ax, ay, bx, by, INK, 0.22)
            t += step
    if p.profile_type == "round_tube":
        _dim_h(svg, cx, cx + r_out, cy + r_out + 4.5, f"⌀{p.outer_dimension_mm:g}", size=TXT_DIM)
        if r_in > 0.2:
            _dim_h(
                svg,
                cx,
                cx + r_in,
                cy - r_out - 4.5,
                f"⌀{p.outer_dimension_mm - 2 * p.wall_thickness_mm:g}",
                size=TXT_DIM,
            )


def _clip_annulus(
    x0: float, y0: float, x1: float, y1: float, cx: float, cy: float, r_in: float, r_out: float
) -> list[tuple[float, float, float, float]]:
    """Return line segments of (x0,y0)-(x1,y1) lying inside the annulus."""
    segs: list[tuple[float, float, float, float]] = []
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return segs
    ts: list[tuple[float, float]] = []
    for r in (r_in, r_out):
        fx, fy = x0 - cx, y0 - cy
        b = 2 * (fx * dx + fy * dy)
        c = fx * fx + fy * fy - r * r
        disc = b * b - 4 * L2 * c
        if disc >= 0:
            sq = math.sqrt(disc)
            for t in ((-b - sq) / (2 * L2), (-b + sq) / (2 * L2)):
                if 0 <= t <= 1:
                    ts.append((t, r))
    if not ts:
        mx, my = x0 + dx / 2, y0 + dy / 2
        d = math.hypot(mx - cx, my - cy)
        if r_in <= d <= r_out:
            return [(x0, y0, x1, y1)]
        return segs
    # Walk the entry/exit crossings of the two circles, pairing the
    # parameter intervals that fall inside the annular wall.
    out: list[list[float]] = []
    bounds = sorted({t for t, _ in ts})
    prev_t, prev_in = 0.0, _inside(x0, y0, cx, cy, r_in, r_out)
    for b in bounds:
        mid = (prev_t + b) / 2.0
        px, py = x0 + dx * mid, y0 + dy * mid
        ins = _inside(px, py, cx, cy, r_in, r_out)
        if ins and not prev_in:
            out.append([prev_t, b, 0, 0])
        elif not ins and prev_in:
            out[-1][1] = prev_t
        prev_t, prev_in = b, ins
    mid = (prev_t + 1.0) / 2.0
    px, py = x0 + dx * mid, y0 + dy * mid
    if _inside(px, py, cx, cy, r_in, r_out) and out:
        out[-1][1] = 1.0
    res: list[tuple[float, float, float, float]] = []
    for seg in out:
        a, b = seg[0], seg[1]
        if b - a > 1e-6:
            res.append((x0 + dx * a, y0 + dy * a, x0 + dx * b, y0 + dy * b))
    return res


def _inside(x: float, y: float, cx: float, cy: float, r_in: float, r_out: float) -> bool:
    d = math.hypot(x - cx, y - cy)
    return (r_in - 1e-9) <= d <= (r_out + 1e-9)


def _square_tube_section(
    svg: list[str],
    cx: float,
    cy: float,
    p: TubeProfile,
    half: float,
    half_in: float,
) -> None:
    _rect(svg, cx - half, cy - half, 2 * half, 2 * half, INK, 0.6, fill=FILL)
    if half_in > 0.05:
        _rect(svg, cx - half_in, cy - half_in, 2 * half_in, 2 * half_in, INK, 0.5, fill=PAPER)
        _hatch_rect(svg, cx - half, cy - half, half - half_in, 2 * half)
        _hatch_rect(svg, cx + half_in, cy - half, half - half_in, 2 * half)
        _hatch_rect(svg, cx - half_in, cy - half, 2 * half_in, half - half_in)
        _hatch_rect(svg, cx - half_in, cy + half_in, 2 * half_in, half - half_in)
    _centerline(svg, cx - half - 1.6, cy, cx + half + 1.6, cy)
    _centerline(svg, cx, cy - half - 1.6, cx, cy + half + 1.6)
    _dim_h(svg, cx - half, cx + half, cy + half + 4.5, f"{p.outer_dimension_mm:g}", size=TXT_DIM)
    if half_in > 0.05:
        _dim_h(
            svg, cx - half, cx - half_in, cy - half - 4.5, f"{p.wall_thickness_mm:g}", size=TXT_DIM
        )
        _dim_h(
            svg, cx + half_in, cx + half, cy - half - 4.5, f"{p.wall_thickness_mm:g}", size=TXT_DIM
        )


def _plan_view(
    svg: list[str],
    cx: float,
    cy: float,
    wx: float,
    dy: float,
    scale: float,
    label: str,
    prof_t: float | None = None,
) -> tuple[float, float, float, float]:
    """Top view: plan rectangle of width_x by depth_y, centred on (cx, cy)."""
    w, d = wx * scale, dy * scale
    x0, y0 = cx - w / 2.0, cy - d / 2.0
    _rect(svg, x0, y0, w, d, INK, 0.6, fill=FILL)
    if prof_t is not None and prof_t > 0.05:
        # Inner line showing the tube wall / hollow core.
        tw = prof_t * scale
        _rect(svg, x0 + tw, y0 + tw, w - 2 * tw, d - 2 * tw, INK, 0.4, fill=PAPER)
    _centerline(svg, x0 - 3.0, cy, x0 + w + 3.0, cy)
    _centerline(svg, cx, y0 - 3.0, cx, y0 + d + 3.0)
    _dim_h(svg, x0, x0 + w, y0 + d + 6.0, f"{wx:g}")
    _dim_v(svg, y0, y0 + d, x0 - 6.0, f"{dy:g}", side=-1)
    _text(svg, cx, y0 - 9.0, label, size=TXT_VIEW, color=INK, weight="bold")
    return x0, y0, w, d


def _elevation_view(
    svg: list[str], cx: float, cy: float, wx: float, thick: float, scale: float, label: str
) -> tuple[float, float, float, float]:
    """Front view: width_x across, thickness tall."""
    w, t = wx * scale, max(thick * scale, 2.0)
    x0, y0 = cx - w / 2.0, cy - t / 2.0
    _rect(svg, x0, y0, w, t, INK, 0.6, fill=FILL)
    _centerline(svg, x0 - 3.0, cy, x0 + w + 3.0, cy)
    _dim_h(svg, x0, x0 + w, y0 + t + 6.0, f"{wx:g}")
    _dim_v(svg, y0, y0 + t, x0 - 6.0, f"{thick:g}", side=-1)
    _text(svg, cx, y0 - 6.0, label, size=TXT_VIEW, color=INK, weight="bold")
    return x0, y0, w, t


def _side_view(
    svg: list[str], cx: float, cy: float, dy: float, thick: float, scale: float, label: str
) -> tuple[float, float, float, float]:
    """Side view: depth_y across, thickness tall."""
    d, t = dy * scale, max(thick * scale, 2.0)
    x0, y0 = cx - d / 2.0, cy - t / 2.0
    _rect(svg, x0, y0, d, t, INK, 0.6, fill=FILL)
    _centerline(svg, x0 - 3.0, cy, x0 + d + 3.0, cy)
    _dim_h(svg, x0, x0 + d, y0 + t + 6.0, f"{dy:g}")
    _dim_v(svg, y0, y0 + t, x0 + d + 6.0, f"{thick:g}", side=1)
    _text(svg, cx, y0 - 6.0, label, size=TXT_VIEW, color=INK, weight="bold")
    return x0, y0, d, t


# --- True silhouette views from analytic primitives ------------------------
# A view is an orthographic frame given by the two model axes kept in the
# picture. Primitives come from cad.assembly, the same source the mesh
# is built from, so a sheet cannot disagree with the exported solid.


# A projected 2D shape: ("quad", corners) or ("circle", x, y, r, stroke).
Shape = tuple[Any, ...]
# One feature dimension: (start, end, side, text) in model coordinates.
ViewDim = tuple[float, float, str, str]
# Model (u, v) -> sheet (x, y).
Projector = Callable[[float, float], tuple[float, float]]


def _project(prim: Primitive, u: int, v: int) -> list[Shape]:
    """Project one primitive into 2D shapes for frame axes ``u``/``v``.

    Returns ("quad", corners) and ("circle", x, y, r, stroke) tuples.
    """
    if prim["kind"] == "box":
        c, s = prim["c"], prim["s"]
        cu, su, cv, sv = c[u], s[u], c[v], s[v]
        return [
            (
                "quad",
                [
                    (cu - su / 2.0, cv - sv / 2.0),
                    (cu + su / 2.0, cv - sv / 2.0),
                    (cu + su / 2.0, cv + sv / 2.0),
                    (cu - su / 2.0, cv + sv / 2.0),
                ],
            )
        ]
    a, b, r = prim["a"], prim["b"], prim["r"]
    du, dv = b[u] - a[u], b[v] - a[v]
    length = math.hypot(du, dv)
    if length < 1e-9:
        # The axis points at the viewer, so the member reads as a circle.
        return [("circle", a[u], a[v], r, True)]
    ux, uy = du / length, dv / length
    nx, ny = -uy * r, ux * r
    # The end caps are covered by the barrel, so they are filled but not
    # stroked -- otherwise the seam circles show through the silhouette.
    return [
        (
            "quad",
            [
                (a[u] + nx, a[v] + ny),
                (b[u] + nx, b[v] + ny),
                (b[u] - nx, b[v] - ny),
                (a[u] - nx, a[v] - ny),
            ],
        ),
        ("circle", a[u], a[v], r, False),
        ("circle", b[u], b[v], r, False),
    ]


def _shapes_bbox(shapes: list[Shape]) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for s in shapes:
        if s[0] == "quad":
            xs.extend(p[0] for p in s[1])
            ys.extend(p[1] for p in s[1])
        else:
            xs.extend((s[1] - s[3], s[1] + s[3]))
            ys.extend((s[2] - s[3], s[2] + s[3]))
    return min(xs), min(ys), max(xs), max(ys)


def _shape_view(
    svg: list[str],
    cx: float,
    cy: float,
    prims: list[Primitive],
    u: int,
    v: int,
    scale: float,
    label: str,
    dims_h: Sequence[ViewDim] = (),
    dims_v: Sequence[ViewDim] = (),
    right_edge: float | None = None,
) -> tuple[float, float, float, float]:
    """
    Draw one true view of ``prims`` centred on (cx, cy).

    ``dims_h`` entries are (u0, u1, side, text) -- a horizontal dimension
    between two model-u values, placed a fixed distance outside the view on
    ``side`` ("above" or "below"). ``dims_v`` is (v0, v1, side, text) with
    ``side`` in ("left", "right"). The measured ends stay in model
    coordinates so every dimension line is axis-parallel, but the *offset*
    is in sheet millimetres so the text never lands on the geometry no
    matter what the drawing scale turns out to be.
    """
    shapes: list[Shape] = []
    for p in prims:
        shapes.extend(_project(p, u, v))
    x0, y0, x1, y1 = _shapes_bbox(shapes)

    # Model midpoint of the silhouette lands on the requested sheet centre.
    ou = cx - (x0 + x1) / 2.0 * scale
    ov = cy + (y0 + y1) / 2.0 * scale

    def T(mu: float, mv: float) -> tuple[float, float]:
        return (ou + mu * scale, ov - mv * scale)

    def pts_of(corners: Sequence[tuple[float, float]]) -> str:
        return " ".join(f"{a:.2f},{b:.2f}" for a, b in (T(p[0], p[1]) for p in corners))

    # Two passes so the union reads as one solid: fill everything, then
    # stroke only the real edges.
    for s in shapes:
        if s[0] == "quad":
            svg.append(f'<polygon points="{pts_of(s[1])}" fill="{FILL}"/>')
        else:
            a, b = T(s[1], s[2])
            svg.append(f'<circle cx="{a:.2f}" cy="{b:.2f}" r="{s[3] * scale:.2f}" fill="{FILL}"/>')
    for s in shapes:
        if s[0] == "quad":
            svg.append(
                f'<polygon points="{pts_of(s[1])}" fill="none" '
                f'stroke="{INK}" stroke-width="0.6" '
                f'stroke-linejoin="round"/>'
            )
        elif s[3]:
            a, b = T(s[1], s[2])
            svg.append(
                f'<circle cx="{a:.2f}" cy="{b:.2f}" '
                f'r="{s[3] * scale:.2f}" fill="none" stroke="{INK}" '
                f'stroke-width="0.6"/>'
            )

    top_left = T(x0, y1)
    bot_right = T(x1, y0)
    view_top, view_bot = top_left[1], bot_right[1]
    view_left, view_right = top_left[0], bot_right[0]

    # Overall envelope, then the feature dimensions stacked outward from it
    # so nothing lands on a member. Each side gets its own ladder, otherwise
    # a vertical feature dimension lands on the overall one beside it.
    ladder = {"below": 5.0, "above": 5.0, "left": 5.0, "right": 5.0}
    ladder_slots = {"below": 0, "above": 0, "left": 0, "right": 0}

    def _next(side: str) -> float:
        off = ladder[side]
        ladder[side] = off + 6.5
        ladder_slots[side] += 1
        return off

    def _ext_v(mu: float, y_from: float, y_to: float) -> None:
        """Extension line running vertically to a horizontal dimension."""
        x = T(mu, 0)[0]
        if abs(y_to - y_from) > 0.3:
            _line(svg, x, y_from, x, y_to, MUTED, 0.2)

    def _ext_h(mv: float, x_from: float, x_to: float) -> None:
        """Extension line running horizontally to a vertical dimension."""
        y = T(0, mv)[1]
        if abs(x_to - x_from) > 0.3:
            _line(svg, x_from, y, x_to, y, MUTED, 0.2)

    gap = 1.5  # dimension line overshoot past the extension line

    off = _next("below")
    _ext_v(x0, view_bot, view_bot + off + gap)
    _ext_v(x1, view_bot, view_bot + off + gap)
    _dim_h(svg, view_left, view_right, view_bot + off, f"{x1 - x0:g}", right_edge=right_edge)

    off = _next("left")
    _ext_h(y1, view_left, view_left - off - gap)
    _ext_h(y0, view_left, view_left - off - gap)
    _dim_v(svg, view_top, view_bot, view_left - off, f"{y1 - y0:g}", side=-1)
    for u0, u1, side, text in dims_h:
        off = _next(side)
        if side == "below":
            y = view_bot + off
            _ext_v(u0, view_bot, y + gap)
            _ext_v(u1, view_bot, y + gap)
        else:
            y = view_top - off
            _ext_v(u0, view_top, y - gap)
            _ext_v(u1, view_top, y - gap)
        _dim_h(svg, T(u0, 0)[0], T(u1, 0)[0], y, text, right_edge=right_edge)
    for v0, v1, side, text in dims_v:
        off = _next(side)
        if side == "left":
            x = view_left - off
            _ext_h(v0, view_left, x - gap)
            _ext_h(v1, view_left, x - gap)
        else:
            x = view_right + off
            _ext_h(v0, view_right, x + gap)
            _ext_h(v1, view_right, x + gap)
        # The value must be set on the same side as its dimension line, or
        # it runs back across the view it belongs to.
        _dim_v(svg, T(0, v0)[1], T(0, v1)[1], x, text, side=-1 if side == "left" else 1)

    # The view caption goes above the view: below it would sit inside the
    # silhouette of any tall, narrow part. The strip it needs is exactly
    # what _caption_space reserved, so it clears the "above" dimensions.
    above = 5.0 + 6.5 * ladder_slots["above"]
    _text(
        svg,
        cx,
        view_top - above - 2.0 - TXT_VIEW * 0.8,
        label,
        size=TXT_VIEW,
        color=INK,
        weight="bold",
    )
    return x0, y0, x1, y1


def _view_cone(svg: list[str], cx: float, cy: float, r: float, third_angle: bool = True) -> None:
    """Small projection-direction marker between views."""
    svg.append(
        f'<polygon points="{cx:.2f},{cy - r:.2f} {cx - r * 0.6:.2f},{cy:.2f} '
        f'{cx + r * 0.6:.2f},{cy:.2f}" fill="{PAPER}" stroke="{MUTED}" '
        f'stroke-width="0.4"/>'
    )


def _ladder_slots(dims: Sequence[ViewDim], side: str, has_overall: bool) -> int:
    """How many dimension lines a view stacks on one side."""
    return sum(1 for d in dims if d[2] == side) + (1 if has_overall else 0)


def _ladder_depth(dims: Sequence[ViewDim], side: str, has_overall: bool) -> float:
    """Sheet depth a view's dimension ladder needs on one side.

    Each dimension on a side pushes the next one 6.5 mm further out, and the
    last one still needs room for its own text. Laying the sheet out from
    this is what keeps a plan dimension from landing on the caption of the
    view sitting underneath it.
    """
    n = _ladder_slots(dims, side, has_overall)
    if not n:
        return 0.0
    return 5.0 + 6.5 * n + TXT_DIM + 1.5


def _caption_space(dims_h: Sequence[ViewDim], side: str) -> float:
    """Clear strip above a view for its caption, clear of that side's dims.

    Must agree exactly with where ``_shape_view`` puts the caption, or the
    layout will reserve the wrong amount and the caption rides the border.
    """
    ladder = 5.0 + 6.5 * _ladder_slots(dims_h, side, False)
    return ladder + 2.0 + TXT_VIEW * 0.8


def render_three_view_svg(part: PartDrawing, model: FrameDesignModel) -> str:
    """
    Full third-angle orthographic set: top, front, side.

    Used for the flat rectangular parts (seat rails, seat pan, stretchers)
    where plan width and depth differ, so a single elevation is insufficient.
    """
    W, H = 297.0, 210.0
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" '
        f'height="{H}mm" viewBox="0 0 {W} {H}">'
    ]
    svg.append(f'<rect width="{W}" height="{H}" fill="{PAPER}"/>')
    _rect(svg, 10, 10, W - 20, H - 20, INK, 0.8, fill="none")

    wx = part.width_x_mm
    dy = part.depth_y_mm
    thick = part.height_z_mm if part.height_z_mm is not None else part.length_mm

    # Scale so the plan block fits horizontally AND the stacked plan +
    # elevation rows fit vertically inside the drawing area.
    # The drawing area is bounded by the border on the left and the
    # title/notes column on the right; views must stay inside it or their
    # dimensions land on top of the notes.
    side_col = 108.0
    left = 10.0
    draw_w = W - left - 10.0 - side_col
    col_w = draw_w / 2.0
    span = max(wx, dy)
    # Each view is dimensioned on its left and right, and the dimension text
    # is centred on its line, so a view needs a clear margin for both.
    dim_margin = 24.0
    view_w = max(col_w - 2.0 * dim_margin, 20.0)
    scale_w = view_w / span

    # Third angle: TOP above FRONT, SIDE to the right of FRONT.
    # Views are centred inside the space left over once the dimension
    # margins are taken out, so no text can reach the border. The vertical
    # gaps are sized from the dimension ladders actually drawn, not guessed.
    dims = part.view_dims or {}
    if part.primitives:
        plan_h = dims.get("PLAN", ((), ()))[0]
        front_h = dims.get("FRONT", ((), ()))[0]
        plan_above = _ladder_depth(plan_h, "above", False) + _caption_space(plan_h, "above")
        plan_below = _ladder_depth(plan_h, "below", True)
        front_above = _ladder_depth(front_h, "above", False) + _caption_space(front_h, "above")
        front_below = _ladder_depth(front_h, "below", True)
    else:
        # The plain rectangle views put their caption 9 mm above the top
        # edge and their overall width dimension 6 mm below the bottom.
        caption = TXT_VIEW * 0.8 + 2.0
        plan_above = 9.0 + caption
        plan_below = 6.0 + TXT_DIM + 1.5
        front_above = 6.0 + caption
        front_below = 6.0 + TXT_DIM + 1.5

    # The elevation row may need more width than the plan row does.
    extra = 0.0
    if part.primitives:
        extra = max(
            _ladder_depth(dims.get("FRONT", ((), ()))[1], "left", True),
            _ladder_depth(dims.get("SIDE", ((), ()))[1], "left", True),
            _ladder_depth(dims.get("FRONT", ((), ()))[1], "right", False),
            _ladder_depth(dims.get("SIDE", ((), ()))[1], "right", False),
        )
        if extra > dim_margin:
            view_w = max(col_w - dim_margin - extra, 16.0)
            scale_w = view_w / span

    # The plan block and the elevation row are stacked, so the scale has to
    # satisfy both heights plus the space their dimensions and captions need.
    fixed = plan_above + plan_below + front_above + front_below
    scale_h = (H - 20.0 - fixed) / (span + max(thick, 12.0))
    scale = min(1.4, scale_w, scale_h)
    scale_text = f"{scale:.2f}:1" if scale >= 0.995 else f"1:{1 / scale:.1f}"

    # Wall thickness of the member, shown as an inner line in plan.
    wall = part.profile.wall_thickness_mm if part.profile.profile_type.endswith("_tube") else 0.0

    plan_tall = span * scale
    elev_tall = max(thick, 12.0) * scale
    top_cy = 10.0 + plan_above + plan_tall / 2.0
    row_cy = top_cy + plan_tall / 2.0 + plan_below + front_above + elev_tall / 2.0
    top_cx = left + dim_margin + view_w / 2.0
    front_cx = top_cx
    side_cx = left + col_w + dim_margin + view_w / 2.0

    if part.primitives:
        # True silhouettes: the members are drawn, not a bounding box.
        col_right = left + col_w + dim_margin + view_w
        _shape_view(
            svg,
            top_cx,
            top_cy,
            part.primitives,
            0,
            1,
            scale,
            "มุมมองด้านบน  TOP VIEW",
            *dims.get("PLAN", ((), ())),
            right_edge=col_right,
        )
        _shape_view(
            svg,
            front_cx,
            row_cy,
            part.primitives,
            0,
            2,
            scale,
            "มุมมองด้านหน้า  FRONT VIEW",
            *dims.get("FRONT", ((), ())),
            right_edge=col_right,
        )
        _shape_view(
            svg,
            side_cx,
            row_cy,
            part.primitives,
            1,
            2,
            scale,
            "มุมมองด้านข้าง  SIDE VIEW",
            *dims.get("SIDE", ((), ())),
            right_edge=W - 10.0 - 108.0,
        )
    else:
        _plan_view(svg, top_cx, top_cy, wx, dy, scale, "มุมมองด้านบน  TOP VIEW", prof_t=wall)
        _elevation_view(svg, front_cx, row_cy, wx, thick, scale, "มุมมองด้านหน้า  FRONT VIEW")
        _side_view(svg, side_cx, row_cy, dy, thick, scale, "มุมมองด้านข้าง  SIDE VIEW")

    # Third-angle alignment: TOP shares width with FRONT, SIDE shares
    # horizontal position with FRONT's depth.
    _line(
        svg,
        front_cx - view_w / 2.0,
        top_cy + plan_tall / 2.0 + 2.0,
        front_cx - view_w / 2.0,
        row_cy - 8.0,
        MUTED,
        0.2,
        dash="2,2",
    )
    _line(
        svg,
        front_cx + view_w / 2.0,
        top_cy + plan_tall / 2.0 + 2.0,
        front_cx + view_w / 2.0,
        row_cy - 8.0,
        MUTED,
        0.2,
        dash="2,2",
    )
    _line(
        svg,
        front_cx,
        row_cy + max(thick * scale, 2.0) / 2.0 + 6.0,
        side_cx,
        row_cy + max(thick * scale, 2.0) / 2.0 + 6.0,
        MUTED,
        0.2,
        dash="2,2",
    )

    # ---- notes ----
    notes = [
        "1. ขนาดทั้งหมดเป็นมิลลิเมตร (mm)",
        f"2. วัสดุ: {model.material.name}",
        f"3. หน้าตัด: {_profile_label(part.profile)}",
        f"4. กว้าง X = {wx:g} mm",
        f"5. ลึก Y = {dy:g} mm",
        f"6. หนา Z = {thick:g} mm",
        "7. มาตรฐานผลิต: ISO 128 / ANSI Y14.5",
    ]
    if part.note:
        notes.append(f"8. {part.note}")
    _notes_block(svg, 108.0, 38.0, notes)

    _title_block(svg, W - 10 - 108, H - 10 - 52, 108, 52, part, model, scale_text)
    _projection_symbol(svg, W - 20, 24, 6.0, third_angle=True)
    _text(svg, W - 32, 24, "THIRD ANGLE", size=TXT_SMALL, color=INK, anchor="end", halo=False)

    svg.append("</svg>")
    return "\n".join(svg)


def render_part_svg(part: PartDrawing, model: FrameDesignModel) -> str:
    """Render one part's ISO 128 sheet, picking the layout the part needs."""
    if part.width_x_mm and part.depth_y_mm:
        return render_three_view_svg(part, model)
    return render_elevation_svg(part, model)


# ------------------------------------------------------------- assembly sheet ---

# Item list for the general arrangement. Keys match the group names coming
# out of cad.assembly.assembly_primitives.
ASSEMBLY_ITEMS: list[tuple[str, int, str]] = [
    ("Leg_Front_Left", 1, "เสาหน้าซ้าย  FRONT LEFT LEG"),
    ("Leg_Front_Right", 1, "เสาหน้าขวา  FRONT RIGHT LEG"),
    ("Leg_Rear_Left", 1, "เสาหลังซ้าย  REAR LEFT LEG"),
    ("Leg_Rear_Right", 1, "เสาหลังขวา  REAR RIGHT LEG"),
    ("Lower_Stretchers", 1, "ชุดสตรัชเตอร์ล่าง  LOWER STRETCHER SET"),
    ("Seat_Frame_Rails", 1, "โครงรองเบาะ  SEAT FRAME RAILS"),
    ("Seat_Pan_Deck", 1, "แผ่นเบาะ  SEAT PAN DECK"),
    ("Armrest_Left", 1, "ชุดท่อแขนซ้าย  LEFT ARMREST SET"),
    ("Armrest_Right", 1, "ชุดท่อแขนขวา  RIGHT ARMREST SET"),
    ("Backrest_Assembly", 1, "ชุดโครงพนัก  BACKREST ASSEMBLY"),
]


def _shape_view_raw(
    svg: list[str],
    cx: float,
    cy: float,
    prims: list[Primitive],
    u: int,
    v: int,
    scale: float,
    bbox_override: tuple[float, float, float, float] | None = None,
) -> tuple[tuple[float, float, float, float], Projector]:
    """Silhouette a group with no dimensions -- used for the assembly views.

    Returns the model-space bounding box that was drawn.
    """
    shapes: list[Shape] = []
    for p in prims:
        shapes.extend(_project(p, u, v))
    x0, y0, x1, y1 = bbox_override or (
        _shapes_bbox(shapes) if shapes else (-1.0, -1.0, 1.0, 1.0)
    )
    ou = cx - (x0 + x1) / 2.0 * scale
    ov = cy + (y0 + y1) / 2.0 * scale

    def T(mu: float, mv: float) -> tuple[float, float]:
        return (ou + mu * scale, ov - mv * scale)

    def pts_of(corners: Sequence[tuple[float, float]]) -> str:
        return " ".join(f"{a:.2f},{b:.2f}" for a, b in (T(p[0], p[1]) for p in corners))

    for stroke in (False, True):
        for s in shapes:
            if s[0] == "quad":
                svg.append(
                    f'<polygon points="{pts_of(s[1])}" '
                    f'fill="{"none" if stroke else FILL}" '
                    f'stroke="{INK if stroke else "none"}" stroke-width="0.5" '
                    f'stroke-linejoin="round"/>'
                )
            elif stroke:
                a, b = T(s[1], s[2])
                svg.append(
                    f'<circle cx="{a:.2f}" cy="{b:.2f}" '
                    f'r="{s[3] * scale:.2f}" fill="none" '
                    f'stroke="{INK}" stroke-width="0.5"/>'
                )
    return (x0, y0, x1, y1), T


def render_assembly_svg(model: FrameDesignModel) -> str:
    """
    General-arrangement sheet for the whole chair.

    Front, side and top silhouettes of every member, ballooned against an
    item table, with the overall envelope and seat height dimensioned.
    """
    from cad.assembly import assembly_primitives

    g = model.geometry
    groups = dict(assembly_primitives(model))
    W, H = 297.0, 210.0
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" '
        f'height="{H}mm" viewBox="0 0 {W} {H}">'
    ]
    svg.append(f'<rect width="{W}" height="{H}" fill="{PAPER}"/>')
    _rect(svg, 10, 10, W - 20, H - 20, INK, 0.8, fill="none")

    prims = [p for _, plist in groups.items() for p in plist]
    # Overall envelope read straight off the geometry rather than derived by
    # hand: these are the extreme points of the members themselves, so the
    # stated overall size is the size of the chair that gets built.
    w_x0, w_x1 = _prim_extent(prims, 0)
    d_y0, d_y1 = _prim_extent(prims, 1)
    _z0, z_top = _prim_extent(prims, 2)
    w_floor = w_x1 - w_x0
    d_floor = d_y1 - d_y0
    total_h = z_top - _z0

    # ---- scale: three views across the top of the sheet ----
    view_top, view_h = 18.0, 116.0
    col_w = (W - 24.0) / 3.0
    scale = min((col_w - 26.0) / w_floor, (view_h - 22.0) / total_h)
    scale = min(scale, 1.0)
    scale_text = f"{scale:.2f}:1" if scale >= 0.995 else f"1:{1 / scale:.1f}"

    row_cy = view_top + view_h / 2.0
    centers = [24.0 + col_w * (i + 0.5) for i in range(3)]
    labels = [
        ("มุมมองด้านหน้า  FRONT VIEW", 0, 2),
        ("มุมมองด้านข้าง  SIDE VIEW", 1, 2),
        ("มุมมองด้านบน  TOP VIEW", 0, 1),
    ]

    drawn = []
    for cx, (label, u, v) in zip(centers, labels):
        box, T = _shape_view_raw(svg, cx, row_cy, prims, u, v, scale)
        drawn.append((box, T))
        _text(
            svg,
            cx,
            row_cy + total_h * scale / 2.0 + 12.0,
            label,
            size=TXT_VIEW,
            color=INK,
            weight="bold",
        )

    # ---- overall dimensions on the front and side views ----
    _fbox, fT = drawn[0]
    _sbox, sT = drawn[1]
    _dim_h(svg, fT(w_x0, 0)[0], fT(w_x1, 0)[0], fT(0, 0)[1] + 6.0, f"{w_floor:.1f}")
    _dim_v(svg, fT(0, _z0)[1], fT(0, z_top)[1], fT(w_x0, 0)[0] - 7.0, f"{total_h:.1f}", side=-1)
    _dim_h(svg, sT(d_y0, 0)[0], sT(d_y1, 0)[0], sT(0, 0)[1] + 6.0, f"{d_floor:.1f}")
    # Seat height off the floor, the one dimension that must not drift.
    _dim_v(
        svg,
        fT(0, _z0)[1],
        fT(0, g.seat_height_mm)[1],
        fT(w_x1, 0)[0] + 7.0,
        f"{g.seat_height_mm:g}",
        side=1,
    )

    # ---- item balloons across a row above the front view ----
    balloon_y = view_top - 1.0
    anchors = []
    for item, (name, qty, _desc) in enumerate(ASSEMBLY_ITEMS, start=1):
        plist = groups.get(name)
        if not plist:
            continue
        shapes = [sh for p in plist for sh in _project(p, 0, 2)]
        x0, y0, x1, y1 = _shapes_bbox(shapes)
        anchors.append((item, (x0 + x1) / 2.0, max(y0, y1)))
    anchors.sort(key=lambda a: a[1])
    n = len(anchors)
    for i, (item, mu, mv) in enumerate(anchors):
        bx = centers[0] - col_w / 2.0 + 10.0 + i * (col_w - 20.0) / max(n - 1, 1)
        ax, ay = fT(mu, mv)
        elbow = (bx, ay - 3.0)
        _line(svg, bx, balloon_y + 1.6, elbow[0], elbow[1], INK, 0.25)
        _line(svg, elbow[0], elbow[1], ax, ay, INK, 0.25)
        svg.append(
            f'<circle cx="{bx:.2f}" cy="{balloon_y:.2f}" r="2.3" '
            f'fill="{PAPER}" stroke="{INK}" stroke-width="0.4"/>'
        )
        _text(svg, bx, balloon_y + 1.05, str(item), size=2.7, color=INK, halo=False)

    # ---- item table ----
    tx, ty = 14.0, view_top + view_h + 16.0
    tw = W - 24.0 - 108.0 - 6.0
    _text(
        svg,
        tx,
        ty,
        "รายการชิ้นส่วน  PARTS LIST",
        size=TXT_HEAD,
        anchor="start",
        weight="bold",
        color=INK,
        halo=False,
    )
    col_item = tx + 2.0
    col_name = tx + 14.0
    _line(svg, tx, ty + 1.6, tx + tw, ty + 1.6, INK, 0.4)
    for i, (name, qty, desc) in enumerate(ASSEMBLY_ITEMS):
        ry = ty + 5.6 + i * 4.0
        _text(svg, col_item, ry, str(i + 1), size=TXT_NOTE, anchor="start", color=INK, halo=False)
        _text(
            svg,
            col_name,
            ry,
            f"{name}   x{qty}   {desc}",
            size=TXT_NOTE,
            anchor="start",
            color=INK,
            halo=False,
        )
        _line(svg, tx, ry + 1.0, tx + tw, ry + 1.0, MUTED, 0.15)

    # ---- notes ----
    _notes_block(
        svg,
        108.0,
        view_top,
        [
            "1. ขนาดทั้งหมดเป็นมิลลิเมตร (mm)",
            f"2. วัสดุ: {model.material.name}",
            f"3. ความสูงวัดจากพื้นถึงพนัก {total_h:.1f} mm",
            "4. ผลิตภัณฑ์ตาม ISO 128 / ANSI Y14.5",
            "5. อนุญาตคลาดทลายทั่วไป ISO 2768-mK",
        ],
        lead=5.4,
        step=4.4,
    )

    part = PartDrawing(
        "Chair_Assembly",
        "ชุดเก้าอี้รวม  CHAIR ASSEMBLY",
        1,
        model.material.name,
        g.frame_profile,
        total_h,
        "",
    )
    _title_block(svg, W - 10 - 108, H - 10 - 52, 108, 52, part, model, scale_text)
    svg.append("</svg>")
    return "\n".join(svg)


def render_elevation_svg(part: PartDrawing, model: FrameDesignModel) -> str:
    """Render one part's ISO 128 sheet as a standalone SVG string."""
    W, H = 297.0, 210.0  # A4 landscape, mm
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" '
        f'height="{H}mm" viewBox="0 0 {W} {H}">'
    ]
    svg.append(f'<rect width="{W}" height="{H}" fill="{PAPER}"/>')
    _rect(svg, 10, 10, W - 20, H - 20, INK, 0.8, fill="none")

    g = model.geometry
    p = part.profile
    is_round = p.profile_type.startswith("round")
    r_out = p.outer_dimension_mm / 2.0
    r_in = (p.outer_dimension_mm - 2 * p.wall_thickness_mm) / 2.0
    half = p.outer_dimension_mm / 2.0
    half_in = (p.outer_dimension_mm - 2 * p.wall_thickness_mm) / 2.0

    # ---- scale so the part length plus dims fit the drawing area ----
    usable_w = W - 20 - 104  # leave room for the title block
    pad = 26.0
    need = part.length_mm + 2 * pad
    scale = min(1.6, usable_w / need)
    scale_text = f"{scale:.2f}:1" if scale >= 0.995 else f"1:{1 / scale:.1f}"

    # ---- LONGITUDINAL VIEW (elevation), horizontal ----
    ox, oy = 22.0, 92.0
    Lp = part.length_mm * scale
    th = max(p.outer_dimension_mm * scale, 2.2)
    if is_round:
        _rect(svg, ox, oy - th / 2, Lp, th, INK, 0.6, fill=FILL)
        _centerline(svg, ox - 4, oy, ox + Lp + 4, oy)
    else:
        _rect(svg, ox, oy - th / 2, Lp, th, INK, 0.6, fill=FILL)
        _line(
            svg,
            ox,
            oy - th / 2 + max(1.0, 2 * p.wall_thickness_mm * scale),
            ox + Lp,
            oy - th / 2 + max(1.0, 2 * p.wall_thickness_mm * scale),
            INK,
            0.35,
        )
        _centerline(svg, ox - 4, oy, ox + Lp + 4, oy)
    _dim_h(svg, ox, ox + Lp, oy + th / 2 + 9.0, f"{part.length_mm:g}")
    _text(
        svg,
        ox + Lp / 2.0,
        oy - th / 2 - 6.0,
        "มุมมองด้านข้าง  ELEVATION",
        size=TXT_VIEW,
        color=INK,
        weight="bold",
    )

    # ---- END / SECTION VIEW ----
    sx, sy = ox + Lp / 2.0, oy + 50.0
    if is_round:
        _round_tube_section(svg, sx, sy, p, r_out * scale, r_in * scale)
    else:
        _square_tube_section(svg, sx, sy, p, half * scale, half_in * scale)
    _text(
        svg,
        sx,
        sy + r_out * scale + 14.0 if is_round else sy + half * scale + 14.0,
        "หัวข้อตัด  SECTION A-A",
        size=TXT_VIEW,
        color=INK,
        weight="bold",
    )

    # ---- notes ----
    notes = [
        "1. ขนาดทั้งหมดเป็นมิลลิเมตร (mm)",
        f"2. วัสดุ: {model.material.name}",
        f"3. หน้าตัด: {_profile_label(p)}",
        f"4. ความยาวตัดงาน: {part.length_mm:g} mm",
        "5. มาตรฐานผลิต: ISO 128 / ANSI Y14.5",
    ]
    if part.note:
        notes.append(f"6. {part.note}")
    _notes_block(svg, 104.0, 38.0, notes)

    _title_block(svg, W - 10 - 104, H - 10 - 52, 104, 52, part, model, scale_text)
    _projection_symbol(svg, W - 20, 24, 6.0, third_angle=True)
    _text(svg, W - 32, 24, "THIRD ANGLE", size=TXT_SMALL, color=INK, anchor="end", halo=False)

    svg.append("</svg>")
    return "\n".join(svg)


# ------------------------------------------------------------------ html -----
def render_html(model: FrameDesignModel, parts: list[PartDrawing]) -> str:
    """Self-contained printable A4 sheet embedding every part drawing."""
    title = f"{model.geometry.topology_type.upper()} — 2D ENGINEERING DRAWING SET"
    cards = [
        f'<figure class="sheet">'
        f'<div class="lbl">00 / {len(parts):02d} — '
        f"ชุดเก้าอี้รวม CHAIR ASSEMBLY</div>"
        f"{render_assembly_svg(model)}</figure>"
    ]
    for i, part in enumerate(parts, 1):
        svg = render_part_svg(part, model)
        cards.append(
            f'<figure class="sheet">'
            f'<div class="lbl">{i:02d} / {len(parts):02d} — '
            f"{escape(part.title)}</div>"
            f"{svg}</figure>"
        )
    return f"""<!DOCTYPE html>
<html lang="th"><head><meta charset="utf-8">
<title>{escape(title)}</title>
<style>
  @page {{ size: A4 landscape; margin: 6mm; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: #e9edf3; font-family: Tahoma, "Segoe UI", sans-serif; }}
  header {{ background: #0f172a; color: #fff; padding: 10px 16px; }}
  header h1 {{ margin: 0; font-size: 15px; letter-spacing: .3px; }}
  header p {{ margin: 3px 0 0; font-size: 11px; color: #94a3b8; }}
  .sheet {{ margin: 10mm auto; background: #fff; page-break-after: always;
            break-after: page; width: 285mm; box-shadow: 0 2px 10px rgba(15,23,42,.18); }}
  .sheet:last-child {{ page-break-after: auto; }}
  .sheet svg {{ display: block; width: 100%; height: auto; }}
  .lbl {{ padding: 4px 10px; font-size: 10px; color: #64748b;
          border-bottom: 1px solid #e2e8f0; }}
  @media print {{
    body {{ background: #fff; }}
    header {{ display: none; }}
    .sheet {{ margin: 0; box-shadow: none; width: auto; }}
    .lbl {{ display: none; }}
    .sheet svg {{ width: 100%; height: 197mm; }}
  }}
</style></head>
<body>
<header>
  <h1>{escape(title)}</h1>
  <p>{len(parts)} parts &middot; material {escape(model.material.name)}
     &middot; ISO 128 / ANSI Y14.5 &middot; third angle &middot; units mm</p>
</header>
{"".join(cards)}
</body></html>"""


def _print_pdf(html_path: Path, pdf_path: Path, chrome: str | None = None) -> bool:
    """Print the HTML sheet to a vector PDF via headless Chrome."""
    import subprocess

    from drafting.render_mermaid import find_chrome

    exe = find_chrome(chrome)
    if not exe:
        print(f"  [skip] no Chrome found; cannot write {pdf_path.name}")
        return False
    cmd = [
        exe,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        "--print-to-pdf=" + str(pdf_path.resolve()),
        html_path.resolve().as_uri(),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=180)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f"  [fail] PDF print failed: {exc}")
        return False
    if not pdf_path.exists():
        print(f"  [fail] Chrome did not write {pdf_path.name}")
        return False
    return True


def write_drawings(model: FrameDesignModel, outdir: Path = DEFAULT_OUTDIR) -> list[Path]:
    """Write every part SVG plus the combined HTML sheet. Returns written paths."""
    outdir.mkdir(parents=True, exist_ok=True)
    parts = build_parts(model)
    written = []
    for part in parts:
        f = outdir / f"{part.key}.svg"
        f.write_text(render_part_svg(part, model), encoding="utf-8")
        written.append(f)
    # The general arrangement leads the set: it is the sheet that shows
    # which member is which before the detail sheets follow.
    asm = outdir / "Chair_Assembly.svg"
    asm.write_text(render_assembly_svg(model), encoding="utf-8")
    written.append(asm)
    html = outdir / "chair_drawings.html"
    html.write_text(render_html(model, parts), encoding="utf-8")
    written.append(html)
    return written


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    ap.add_argument(
        "--pdf", action="store_true", help="also print a vector PDF sheet (requires Chrome)"
    )
    ap.add_argument("--chrome", default=None, help="explicit Chrome/Chromium path for PDF output")
    args = ap.parse_args(argv)

    model = FrameDesignModel()
    written = write_drawings(model, outdir=args.outdir)
    for f in written:
        print(f"[ok] {f}")

    if args.pdf:
        _print_pdf(
            args.outdir / "chair_drawings.html", args.outdir / "chair_drawings.pdf", args.chrome
        )
        print(f"[ok] {args.outdir / 'chair_drawings.pdf'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
