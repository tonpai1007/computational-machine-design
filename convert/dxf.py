"""STEP -> first-angle 2D DXF (AutoCAD) via FreeCAD's console binary.

FreeCAD's ``TechDraw.projectToDXF`` performs hidden-line removal and returns
bare ``LINE`` entities, but it fixes no up-vector, so each view arrives in an
arbitrary in-plane rotation. This module recovers that rotation robustly: the
kernel projects small calibration segments along +X/+Y/+Z *through the same
projection path* as the views, and Python derives each view's signed axis
mapping from where those segments land - no guessing from bounding boxes::

    front: X2 = -Z, Y2 = +X        top: X2 = -X, Y2 = +Y
    side:  X2 = -Z, Y2 = -Y

(The axis parallel to the view direction collapses to zero, which is how the
depth axis is identified.) Views are reoriented into a standard frame - width
horizontal, height vertical, correct non-mirrored sense - and laid out
first-angle (ISO 128, as used in Thailand): top below front sharing the width
axis, the right-side view left of front sharing the height axis.

Each view sits on its own layer (``front`` / ``top`` / ``side``) so it can be
toggled independently. Overall width + height dimensions ride on a shared
``dimensions`` layer; their witness lines attach to the placed view outlines
while the text values are the kernel-measured model extents, so the numbers
stay honest.

Paths travel by environment variable, not argv: ``freecadcmd`` sets
``sys.argv[0]`` to its own executable, so positional indexes are unreliable
-- the same convention :mod:`convert.solids` uses.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from collections.abc import Iterable
from pathlib import Path

from convert.solids import ConversionError, find_kernel

# Windows: keep FreeCAD's console window from flashing up.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

#: Orthographic view name -> projection direction.
VIEWS = {
    "front": (0.0, -1.0, 0.0),
    "top": (0.0, 0.0, -1.0),
    "side": (-1.0, 0.0, 0.0),
}

#: Desired drawing frame per view: which model axis goes right / up, and with
#: what sign. Every view ends upright, width horizontal, height vertical, in
#: the conventional non-mirrored sense (verified against the calibration: the
#: raw mapping is a pure signed permutation, so the reorient is an exact
#: axis swap with optional sign flips - no shear, no resampling).
TARGET_FRAME = {
    "front": ("X", 1.0, "Z", 1.0),
    "top": ("X", 1.0, "Y", 1.0),
    "side": ("Y", 1.0, "Z", 1.0),
}

#: Model axes probed by the in-kernel calibration.
_AXES = ("X", "Y", "Z")

# Runs inside freecadcmd. TechDraw.projectToDXF returns bare LINE entities, one
# view per file, plus a calibration file recording where axis-aligned probe
# segments land: the same projection maps the *same* geometry as the views,
# so Python recovers each view's signed axis mapping exactly from the probes.
# The kernel also measures the compound's true 3D bounding box into
# model.json; Python reads it back as the source of dimension values, so the
# drawing annotates measured extents rather than estimated ones. Keeping the
# projection on the kernel side but all assembly on the Python side lets the
# layout be unit-tested without a FreeCAD install.
_KERNEL_SCRIPT = """
import json
import os

import FreeCAD
import Import
import Part
import TechDraw

DIRECTIONS = {
    "front": FreeCAD.Vector(0, -1, 0),
    "top": FreeCAD.Vector(0, 0, -1),
    "side": FreeCAD.Vector(-1, 0, 0),
}


def _frag_span(fragment):
    xs, ys = [], []
    lines = fragment.splitlines()
    for i in range(0, len(lines) - 1, 2):
        code, val = lines[i].strip(), lines[i + 1]
        try:
            num = float(val)
        except ValueError:
            continue
        if code in ("10", "11"):
            xs.append(num)
        elif code in ("20", "21"):
            ys.append(num)
    n = min(len(xs), len(ys))
    if n < 2:
        return None
    return (xs[-1] - xs[0], ys[-1] - ys[0])


views = json.loads(os.environ["MDIE_VIEWS"])
out = os.environ["MDIE_DST_DIR"]
os.makedirs(out, exist_ok=True)

doc = FreeCAD.newDocument("step2dxf")
Import.insert(os.environ["MDIE_SRC"], doc.Name)
shapes = [
    o.Shape
    for o in doc.Objects
    if hasattr(o, "Shape") and o.Shape and o.Shape.Solids
]
if not shapes:
    raise RuntimeError("no solids found in the STEP document")
compound = Part.makeCompound(shapes)

bb = compound.BoundBox
with open(os.path.join(out, "model.json"), "w", encoding="utf-8") as fh:
    json.dump(
        {"X": [bb.XMin, bb.XMax], "Y": [bb.YMin, bb.YMax], "Z": [bb.ZMin, bb.ZMax]}, fh
    )

# Calibration origin clearly outside the model so nothing occludes the probes.
origin = FreeCAD.Vector(bb.XMax + 50.0, bb.YMax + 50.0, bb.ZMax + 50.0)
probes = {
    axis: origin.add(
        FreeCAD.Vector(1 if axis == "X" else 0, 1 if axis == "Y" else 0, 1 if axis == "Z" else 0).multiply(10.0)
    )
    for axis in ("X", "Y", "Z")
}

for name in views:
    direction = DIRECTIONS[name]
    entities = TechDraw.projectToDXF(compound, direction)
    if not entities or "LINE" not in entities:
        raise RuntimeError(f"projection {name!r} produced no geometry")
    with open(os.path.join(out, name + ".entities"), "w", encoding="utf-8") as fh:
        fh.write(entities)
    calib = {}
    for axis, target in probes.items():
        vec = _frag_span(TechDraw.projectToDXF(Part.makeLine(origin, target), direction))
        calib[axis] = None if vec is None else [vec[0], vec[1]]
    with open(os.path.join(out, name + ".calib"), "w", encoding="utf-8") as fh:
        json.dump(calib, fh)
FreeCAD.closeDocument(doc.Name)
"""


# ------------------------------------------------------------------ DXF assembly
#
# A DXF file is a stream of (group-code, value) pairs, one per line. These
# helpers reorient each view's bare LINE entities into its standard frame
# (width horizontal, height vertical, non-mirrored) using the signed axis
# mapping recovered from the in-kernel calibration probes, then translate
# the views into a first-angle layout and concatenate them into one ENTITIES
# section wrapped in a minimal standalone document.

#: Group codes whose following value is an X / Y coordinate.
_X_CODES = {"10", "11"}
_Y_CODES = {"20", "21"}


def calib_to_mapping(calib: dict[str, list[float] | None]) -> dict[str, tuple[str, float]]:
    """Map each model axis to its drawing axis and sign from probe landings.

    ``calib`` maps a model axis to the projected 2D span ``[dx2, dy2]`` of a
    +10 mm probe along it (``None`` when the probe collapses, i.e. the depth
    axis parallel to the view direction). A probe landing overwhelmingly on
    drawing-X means that model axis *is* the drawing-X axis; the sign is the
    landing's sign. Returns model axis -> ``(drawing axis, sign)`` over the
    two non-depth axes. Raises :class:`ConversionError` when the calibration
    is degenerate or ambiguous instead of guessing.
    """
    mapping: dict[str, tuple[str, float]] = {}
    for axis in _AXES:
        vec = calib.get(axis)
        if vec is None:
            continue
        dx2, dy2 = vec
        if abs(dx2) >= abs(dy2):
            if abs(dx2) < 1e-9:
                raise ConversionError(f"calibration probe along +{axis} collapsed")
            mapping[axis] = ("X", 1.0 if dx2 >= 0 else -1.0)
        else:
            if abs(dy2) < 1e-9:
                raise ConversionError(f"calibration probe along +{axis} collapsed")
            mapping[axis] = ("Y", 1.0 if dy2 >= 0 else -1.0)
    if len(mapping) != 2:
        raise ConversionError(f"expected two planar axes, got {sorted(mapping)}")
    if {m[0] for m in mapping.values()} != {"X", "Y"}:
        raise ConversionError(f"calibration axes are not orthogonal: {mapping}")
    return mapping


def _reorient_entity_coords(
    entities: str, mapping: dict[str, tuple[str, float]], target: tuple[str, float, str, float]
) -> tuple[list[float], list[float]]:
    """Extract reoriented (right, up) coordinates from a view's entities.

    Each LINE endpoint ``(x2, y2)`` is re-expressed in model axes via the
    inverse of ``mapping`` - e.g. raw ``X2 = -Z`` means ``Z = -X2`` - and read
    back through ``target`` (``(right_axis, right_sign, up_axis, up_sign)``).
    The raw mapping is a pure signed permutation, so this is an exact axis
    swap with sign flips: no shear, no resampling.
    """
    inv: dict[str, tuple[str, float]] = {}
    for model_axis, (drawing_axis, sign) in mapping.items():
        inv[drawing_axis] = (model_axis, sign)
    right_axis, right_sign, up_axis, up_sign = target
    rights: list[float] = []
    ups: list[float] = []
    lines = entities.splitlines()
    pending_x: float | None = None
    # Each LINE contributes endpoints as sequential (10, 20) then (11, 21)
    # pairs; extrusion codes 12/13 carry the plane's constant depth and pass
    # through untouched by the callers that rewrite coordinates.
    for i in range(0, len(lines) - 1, 2):
        code, value = lines[i].strip(), lines[i + 1]
        if code in _X_CODES:
            try:
                pending_x = float(value)
            except ValueError:
                pending_x = None
        elif code in _Y_CODES and pending_x is not None:
            try:
                y2 = float(value)
            except ValueError:
                pending_x = None
                continue
            x2 = pending_x
            model = {"X": 0.0, "Y": 0.0, "Z": 0.0}
            model[inv["X"][0]] = inv["X"][1] * x2
            model[inv["Y"][0]] = inv["Y"][1] * y2
            rights.append(right_sign * model[right_axis])
            ups.append(up_sign * model[up_axis])
            pending_x = None
    if not rights:
        raise ConversionError("projected view contains no coordinates")
    return rights, ups


def _transform_entities(
    entities: str,
    mapping: dict[str, tuple[str, float]],
    target: tuple[str, float, str, float],
    layer: str,
    dx: float,
    dy: float,
) -> str:
    """Reorient every LINE endpoint, retag its layer, and translate it.

    The (10, 20) and (11, 21) endpoint pairs of each LINE are reoriented
    together - both ends through the same inverse-mapping-then-target read -
    so segments stay rigid. Only those four codes are rewritten; every other
    code and value passes through untouched, except the ``sheet_layer`` tag
    (group code 8), which becomes ``layer``.
    """
    inv: dict[str, tuple[str, float]] = {}
    for model_axis, (drawing_axis, sign) in mapping.items():
        inv[drawing_axis] = (model_axis, sign)
    right_axis, right_sign, up_axis, up_sign = target
    out: list[str] = []
    lines = entities.splitlines()
    pending_x: tuple[str, float] | None = None
    for i in range(0, len(lines) - 1, 2):
        code, value = lines[i], lines[i + 1]
        stripped = code.strip()
        if stripped in _X_CODES:
            if pending_x is not None:
                out += [pending_x[0], repr(pending_x[1])]
                pending_x = None
            try:
                pending_x = (code, float(value))
            except ValueError:
                out += [code, value]
        elif stripped in _Y_CODES and pending_x is not None:
            code_x, x2 = pending_x
            try:
                y2 = float(value)
            except ValueError:
                out += [code_x, repr(x2), code, value]
                pending_x = None
                continue
            model = {"X": 0.0, "Y": 0.0, "Z": 0.0}
            model[inv["X"][0]] = inv["X"][1] * x2
            model[inv["Y"][0]] = inv["Y"][1] * y2
            out += [code_x, repr(right_sign * model[right_axis] + dx)]
            out += [code, repr(up_sign * model[up_axis] + dy)]
            pending_x = None
        else:
            if pending_x is not None:
                out += [pending_x[0], repr(pending_x[1])]
                pending_x = None
            if stripped == "8":
                out += [code, layer]
            else:
                out += [code, value]
    if pending_x is not None:
        out += [pending_x[0], repr(pending_x[1])]
    # Re-add the trailing newline each source line carried.
    return "\n".join(out) + "\n"


def assemble_dxf(
    view_entities: dict[str, str],
    view_calibs: dict[str, dict[str, list[float] | None]],
    gap: float = 40.0,
    model_bbox: dict[str, list[float]] | None = None,
    dimensions: bool = True,
    part_name: str | None = None,
) -> str:
    """Combine per-view projections into one first-angle DXF document.

    ``view_entities`` maps a view name to its bare ``LINE`` entity block and
    ``view_calibs`` maps the same name to its kernel probe landings. Each
    view is reoriented into its :data:`TARGET_FRAME` standard frame,
    normalised to the origin, then laid out first-angle: the front view
    anchors the sheet, top sits below it sharing the width axis, and side
    sits left of it sharing the height axis. Named layers ``<view>`` are
    declared in a LAYER table so AutoCAD shows them without a repair prompt.
    When ``dimensions`` is true and ``model_bbox`` (the kernel-measured ``{axis:
    [lo, hi]}`` extents) is given, overall width + height dimensions are added
    on the shared ``dimensions`` layer - width below each view, height on its
    outer flank.

    Views absent from both inputs (a caller requesting only a subset) leave
    the remaining anchors at the origin: no front means top/side start at
    (0, 0); no side leaves front/top stacked; no top leaves front/side
    side by side. When ``part_name`` is truthy a standard sheet border,
    title block and large part label are added on the ``title`` layer;
    every lettering height (dimension text included) scales from the
    sheet's own extent.
    """
    for name in view_entities:
        if name not in view_calibs:
            raise ConversionError(f"no calibration for view {name!r}")
        if name not in TARGET_FRAME:
            raise ConversionError(f"no target frame for view {name!r}")
    mappings: dict[str, dict[str, tuple[str, float]]] = {}
    rights: dict[str, list[float]] = {}
    ups: dict[str, list[float]] = {}
    for name, entities in view_entities.items():
        mappings[name] = calib_to_mapping(view_calibs[name])
        rights[name], ups[name] = _reorient_entity_coords(
            entities, mappings[name], TARGET_FRAME[name]
        )
    widths = {n: max(rights[n]) - min(rights[n]) for n in view_entities}
    heights = {n: max(ups[n]) - min(ups[n]) for n in view_entities}
    has_front = "front" in view_entities
    # First-angle gutter: the front view's width dimension rides in the
    # band between the front and top views, so the gap grows until its
    # lettering clears the top view. The loop converges - a larger gap
    # only grows the sheet, and so the lettering, by a bounded fraction.
    if dimensions and model_bbox is not None:
        for _ in range(6):
            th = _auto_text_height(_sheet_extent(widths, heights, gap))
            needed = _DIM_OFFSET + 1.5 * th + 8.0
            if needed <= gap:
                break
            gap = needed
    origins = {
        "front": (0.0, 0.0),
        # First angle: the top view hangs below the front view (its top
        # edge one gap below the front view's bottom edge) and the
        # right-side view stands left of it (its right edge one gap
        # left of the front view's left edge).
        "top": (0.0, -(gap + heights.get("top", 0.0)) if has_front else 0.0),
        "side": (-(gap + widths.get("side", 0.0)) if has_front else 0.0, 0.0),
    }
    blocks: list[str] = []
    layer_names: list[str] = []
    placed: dict[str, tuple[float, float, float, float]] = {}
    for name, entities in view_entities.items():
        ox, oy = origins[name]
        dx = ox - min(rights[name])
        dy = oy - min(ups[name])
        blocks.append(
            _transform_entities(entities, mappings[name], TARGET_FRAME[name], name, dx, dy)
        )
        layer_names.append(name)
        placed[name] = (
            ox,
            oy,
            ox + (max(rights[name]) - min(rights[name])),
            oy + (max(ups[name]) - min(ups[name])),
        )
    # Sheet extent drives every text height: lettering stays proportional
    # whether the sheet is a 55 mm leg or the whole chair.
    if placed:
        content = (
            min(b[0] for b in placed.values()),
            min(b[1] for b in placed.values()),
            max(b[2] for b in placed.values()),
            max(b[3] for b in placed.values()),
        )
    else:
        content = (0.0, 0.0, 1.0, 1.0)
    sheet_w = max(content[2] - content[0], content[3] - content[1])
    text_height = _auto_text_height(sheet_w)
    dim_pad = 0.0
    if dimensions and model_bbox is not None:
        dim_block = "".join(
            _view_dimensions(name, placed[name], model_bbox, text_height)
            for name in view_entities
            if name in _DIM_PLAN
        )
        if dim_block:
            layer_names.append(DIM_LAYER)
        blocks.append(dim_block)
        dim_pad = _DIM_OFFSET + 2.8 * text_height
    if part_name:
        blocks.append(_title_block(part_name, content, dim_pad, sheet_w))
        layer_names.append(TITLE_LAYER)
    return _wrap_dxf("".join(blocks), layer_names)


def _tables_section(layer_names: list[str]) -> str:
    """One TABLES section: the STANDARD text style plus the view layers.

    TEXT entities reference their style by name (group code 7);
    declaring STANDARD keeps strict importers from failing to
    resolve it.
    """
    out = [
        "0", "SECTION", "2", "TABLES",
        "0", "TABLE", "2", "STYLE", "70", "1",
        "0", "STYLE", "2", "STANDARD", "70", "0",
        "40", "0.0", "41", "1.0", "42", "0.0", "3", "txt.shx", "4", "",
        "0", "ENDTAB",
        "0", "TABLE", "2", "LAYER", "70", str(len(layer_names)),
    ]
    for name in layer_names:
        out += ["0", "LAYER", "2", name, "70", "0", "62", "7", "6", "CONTINUOUS"]
    out += ["0", "ENDTAB", "0", "ENDSEC"]
    return "\n".join(out) + "\n"


#: Layer carrying the sheet frame, title block and part label.
TITLE_LAYER = "title"

#: Suffix marking the shared auto-dimension overlay.
DIM_LAYER = "dimensions"

#: Number formatting for dimension text: millimetres, one decimal, ISO-style
#: decimal point so values survive any locale AutoCAD runs under.
_DIM_PRECISION = 1

#: Gap (mm) between a view's outline and its dimension lines, the overshoot
#: of witness lines past the dimension line, and the half-size of the arrow
#: barbs - all relative to drawing units (mm). Dimension text height is NOT
#: fixed: :func:`_auto_text_height` scales it from the sheet's own extent.
_DIM_OFFSET = 25.0
_DIM_OVERSHOOT = 6.0
_DIM_ARROW = 8.0
#: Fallback TEXT height (mm) used when no sheet extent is known yet.
_DIM_TEXT_HEIGHT = 12.0
#: Lettering scale: ~1.2% of the sheet width - the standard 3.5-5 mm text of
#: ISO 3098 once a drawing sheet is plotted to A3/A2 - floored so even a
#: small part still gets readable numbers.
_TEXT_FRAC = 0.012
_MIN_TEXT_HEIGHT = 3.5
#: Title-block proportions, as fractions of the sheet width.
_TITLE_MARGIN_FRAC = 0.03
_TITLE_LABEL_FRAC = 0.035
_TITLE_FIELD_FRAC = 0.018
_TITLE_ROWS = 5


def _fmt_dim(value: float) -> str:
    """Format a millimetre dimension value with one decimal, no locale."""
    return "{:.{}f}".format(value, _DIM_PRECISION)


def _auto_text_height(sheet_width: float) -> float:
    """Lettering height (drawing mm) derived from the sheet's own extent."""
    if sheet_width <= 0:
        return _DIM_TEXT_HEIGHT
    return max(_MIN_TEXT_HEIGHT, _TEXT_FRAC * sheet_width)


def _sheet_extent(widths: dict[str, float], heights: dict[str, float], gap: float) -> float:
    """Estimated sheet extent (the longer axis) for a given view gap."""
    col_w = max(widths.get("front", 0.0), widths.get("top", 0.0))
    sheet_w = widths.get("side", 0.0) + gap + col_w
    sheet_h = heights.get("front", 0.0) + gap + heights.get("top", 0.0)
    return max(sheet_w, sheet_h)


def _dxf_line(layer: str, x1: float, y1: float, x2: float, y2: float) -> str:
    """One LINE entity on ``layer`` between two drawing points."""
    return (
        f"0\nLINE\n8\n{layer}\n"
        + f"10\n{repr(x1)}\n20\n{repr(y1)}\n30\n0.0\n"
        + f"11\n{repr(x2)}\n21\n{repr(y2)}\n31\n0.0\n"
    )


def _dxf_text(layer: str, x: float, y: float, text: str, height: float = _DIM_TEXT_HEIGHT) -> str:
    """One middle-centred TEXT entity.

    The justification codes 72/73 select centre/middle alignment,
    which the DXF spec reads from the *second* alignment point
    (11/21/31) - so that point is emitted alongside the first
    (10/20). Viewers honouring the spec centre the text on
    ``(x, y)``; omitting the second point makes strict readers
    centre on the origin instead, which is how dimension numbers
    vanish from a sheet.
    """
    return (
        f"0\nTEXT\n8\n{layer}\n7\nSTANDARD\n"
        + f"10\n{repr(x)}\n20\n{repr(y)}\n30\n0.0\n"
        + f"40\n{repr(height)}\n1\n{text}\n"
        + "72\n1\n73\n2\n"
        + f"11\n{repr(x)}\n21\n{repr(y)}\n31\n0.0\n"
    )


def _linear_dim(
    layer: str,
    fixed: float,
    start: float,
    end: float,
    value: float,
    horizontal: bool,
    side: int,
    text_height: float = _DIM_TEXT_HEIGHT,
) -> str:
    """One overall linear dimension: witness lines, dimension line, arrows, text.

    ``fixed`` is the drawing coordinate of the measured edge (the view's
    outline); ``start``/``end`` span the measured interval along the other
    axis; ``value`` is the dimension text (measured from the kernel's 3D
    bbox, never estimated from drawing pixels). ``side`` is +1 for the
    positive side of the view, -1 for the negative side. Arrowheads are
    small filled barbs drawn as short diagonal LINEs, so no SOLID entities
    or linetype tables are needed.
    """
    off = side * _DIM_OFFSET
    over = side * _DIM_OVERSHOOT
    pos = fixed + off
    parts: list[str] = []
    if horizontal:
        parts.append(_dxf_line(layer, start, fixed - over, start, pos + over))
        parts.append(_dxf_line(layer, end, fixed - over, end, pos + over))
        parts.append(_dxf_line(layer, start, pos, end, pos))
        for tip_x, sgn in ((start, 1.0), (end, -1.0)):
            parts.append(_dxf_line(layer, tip_x, pos, tip_x + sgn * _DIM_ARROW, pos + _DIM_ARROW / 3))
            parts.append(_dxf_line(layer, tip_x, pos, tip_x + sgn * _DIM_ARROW, pos - _DIM_ARROW / 3))
        parts.append(_dxf_text(layer, (start + end) / 2, pos + side * text_height, _fmt_dim(value), text_height))
    else:
        parts.append(_dxf_line(layer, fixed - over, start, pos + over, start))
        parts.append(_dxf_line(layer, fixed - over, end, pos + over, end))
        parts.append(_dxf_line(layer, pos, start, pos, end))
        for tip_y, sgn in ((start, 1.0), (end, -1.0)):
            parts.append(_dxf_line(layer, pos, tip_y, pos + _DIM_ARROW / 3, tip_y + sgn * _DIM_ARROW))
            parts.append(_dxf_line(layer, pos, tip_y, pos - _DIM_ARROW / 3, tip_y + sgn * _DIM_ARROW))
        parts.append(_dxf_text(layer, pos + side * text_height, (start + end) / 2, _fmt_dim(value), text_height))
    return "".join(parts)


#: Overall dimensions drawn per view: (which view bbox axis is measured,
#: whether its dimension line runs horizontally, which side it sits on).
#: Width dimensions sit below their view; heights sit on the outer flank so
#: they never sit inside an outline. First-angle layout: the side view
#: stands left of the front view, so the front height rides the right
#: flank and the side height the left one.
_DIM_PLAN = {
    "front": (("X", True, -1), ("Z", False, 1)),
    "top": (("X", True, -1), ("Y", False, 1)),
    "side": (("Y", True, -1), ("Z", False, -1)),
}


def _view_dimensions(
    view: str,
    bbox: tuple[float, float, float, float],
    model_bbox: dict[str, list[float]],
    text_height: float = _DIM_TEXT_HEIGHT,
) -> str:
    """Overall width + height dimensions for one placed view.

    Witness lines attach to ``bbox`` (the view's reoriented, laid-out outline
    in drawing coordinates) while the text ``value`` is the true model extent
    from the kernel-measured ``model_bbox`` - so the numbers are honest even
    when a view subset is requested or the projection drops an axis. Height
    dimensions anchor on the flank ``side`` names (left of the view for
    side < 0, right of it for side > 0) so they never sit inside an outline.
    """
    min_x, min_y, max_x, max_y = bbox
    parts: list[str] = []
    for model_axis, horizontal, side in _DIM_PLAN[view]:
        lo, hi = model_bbox[model_axis]
        if horizontal:
            parts.append(_linear_dim(DIM_LAYER, min_y, min_x, max_x, hi - lo, True, side, text_height))
        else:
            fixed_x = min_x if side < 0 else max_x
            parts.append(_linear_dim(DIM_LAYER, fixed_x, min_y, max_y, hi - lo, False, side, text_height))
    return "".join(parts)


def _title_block(
    part_name: str,
    content: tuple[float, float, float, float],
    dim_pad: float,
    sheet_w: float,
) -> str:
    """Standard drawing-sheet furniture: border, part label, title block.

    The border frames the placed views (plus dimension clearance); the title
    block sits in the lower-right corner below the content and carries the
    part name, units/scale, projection convention and source file; the part
    name is also repeated large above the sheet. All lettering heights are
    fractions of ``sheet_w``, so the block scales with the drawing.
    """
    cx0, cy0, cx1, cy1 = content
    margin = _TITLE_MARGIN_FRAC * sheet_w
    label_h = _TITLE_LABEL_FRAC * sheet_w
    field_h = _TITLE_FIELD_FRAC * sheet_w
    row_h = field_h * 1.9
    block_h = _TITLE_ROWS * row_h
    block_w = 0.34 * sheet_w
    max_chars = max(8, int(block_w / (0.62 * field_h))) if field_h > 0 else 8
    fx0 = cx0 - dim_pad - margin
    fx1 = cx1 + dim_pad + margin
    fy0 = cy0 - dim_pad - margin - block_h
    fy1 = cy1 + dim_pad + margin + 2.0 * label_h
    parts: list[str] = []
    # Border around the whole sheet.
    parts += [
        _dxf_line(TITLE_LAYER, fx0, fy0, fx1, fy0),
        _dxf_line(TITLE_LAYER, fx1, fy0, fx1, fy1),
        _dxf_line(TITLE_LAYER, fx1, fy1, fx0, fy1),
        _dxf_line(TITLE_LAYER, fx0, fy1, fx0, fy0),
    ]
    # Title block box in the lower-right corner, with row separators.
    bx0 = fx1 - block_w
    parts += [
        _dxf_line(TITLE_LAYER, bx0, fy0, bx0, fy0 + block_h),
        _dxf_line(TITLE_LAYER, bx0, fy0 + block_h, fx1, fy0 + block_h),
    ]
    for row in range(1, _TITLE_ROWS):
        y = fy0 + block_h - row_h * row
        parts.append(_dxf_line(TITLE_LAYER, bx0, y, fx1, y))
    rows = [
        part_name.upper()[:max_chars],
        "MDIE ENGINEERING DRAWING"[:max_chars],
        "UNITS: MM   SCALE: 1:1"[:max_chars],
        "PROJECTION: FIRST ANGLE"[:max_chars],
        f"SOURCE: {part_name.upper()}.STEP"[:max_chars],
    ]
    for idx, row_text in enumerate(rows[:_TITLE_ROWS]):
        y = fy0 + block_h - row_h * (idx + 0.5)
        parts.append(_dxf_text(TITLE_LAYER, bx0 + block_w / 2, y, row_text, field_h))
    # Large part label above the views, left-aligned inside the border.
    label = part_name.upper()
    label_w = 0.62 * label_h * max(len(label), 1)
    parts.append(
        _dxf_text(TITLE_LAYER, fx0 + margin + label_w / 2, fy1 - margin - label_h, label, label_h)
    )
    return "".join(parts)


def _wrap_dxf(entities: str, layer_names: list[str]) -> str:
    """Wrap bare entity text in a minimal standalone DXF (AC1009, mm)."""
    header = (
        "0\nSECTION\n2\nHEADER\n9\n$ACADVER\n1\nAC1009\n"
        "9\n$INSUNITS\n70\n4\n0\nENDSEC\n"
    )
    return (
        header
        + _tables_section(layer_names)
        + "0\nSECTION\n2\nENTITIES\n"
        + entities
        + "0\nENDSEC\n0\nEOF\n"
    )


def step_to_dxf(
    step_path: str | Path,
    output_path: str | Path,
    timeout: int = 300,
    views: tuple[str, ...] = tuple(VIEWS),
    dimensions: bool = True,
    part_name: str | None = None,
) -> Path:
    """Project a STEP assembly into a single first-angle DXF for AutoCAD.

    ``output_path`` is the DXF to write; its front/top/side views are
    reoriented upright via in-kernel calibration probes and laid out
    first-angle (top below front sharing the width axis, the
    right-side view left of front sharing the height axis), each on its own layer. Unless ``dimensions`` is
    false, overall width + height dimensions measured from the kernel's 3D
    bounding box are added on a shared ``dimensions`` layer. A standard
    title block and part label are drawn on the ``title`` layer;
    ``part_name`` defaults to the STEP file's stem (pass ``""`` to suppress
    the block). Returns ``output_path``. Raises :class:`ConversionError` when FreeCAD's console
    binary is missing, the projection fails, or the call exceeds ``timeout``.
    """
    src = Path(step_path)
    if not src.exists():
        raise ConversionError(f"input not found: {src}")
    if src.suffix.lower() not in (".step", ".stp"):
        raise ConversionError(f"expected a STEP file, got {src.name}")

    kernel = find_kernel()
    if not kernel:
        raise ConversionError(
            "STEP -> DXF needs a geometry kernel. Install FreeCAD "
            "(its console binary FreeCADCmd.exe) and make sure it is on PATH."
        )

    dst = Path(output_path)
    dst.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "_step_to_dxf.py"
        script.write_text(_KERNEL_SCRIPT, encoding="utf-8")
        env = {
            **os.environ,
            "MDIE_SRC": str(src.resolve()),
            "MDIE_DST_DIR": tmp,
            "MDIE_VIEWS": json.dumps(list(views)),
        }
        try:
            proc = subprocess.run(
                [str(kernel), str(script)],
                capture_output=True,
                text=True,
                env=env,
                timeout=timeout,
                creationflags=_NO_WINDOW,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ConversionError(
                f"FreeCAD did not finish within {timeout}s"
            ) from exc

        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()
            detail = tail[-1] if tail else "no output"
            raise ConversionError(f"FreeCAD projection failed: {detail}")

        staged = Path(tmp)
        view_entities: dict[str, str] = {}
        view_calibs: dict[str, dict[str, list[float] | None]] = {}
        missing = [v for v in views if not (staged / f"{v}.entities").exists()]
        if missing:
            raise ConversionError(
                f"FreeCAD produced no geometry for view(s): {', '.join(missing)}"
            )
        missing_calib = [v for v in views if not (staged / f"{v}.calib").exists()]
        if missing_calib:
            raise ConversionError(
                f"FreeCAD produced no calibration for view(s): {', '.join(missing_calib)}"
            )
        for v in views:
            view_entities[v] = (staged / f"{v}.entities").read_text(encoding="utf-8")
            view_calibs[v] = json.loads((staged / f"{v}.calib").read_text(encoding="utf-8"))
        model_file = staged / "model.json"
        if model_file.exists():
            model_bbox: dict[str, list[float]] | None = json.loads(
                model_file.read_text(encoding="utf-8")
            )
        else:
            model_bbox = None

    dst.write_text(
        assemble_dxf(
            view_entities,
            view_calibs,
            model_bbox=model_bbox,
            dimensions=dimensions,
            part_name=src.stem if part_name is None else part_name,
        ),
        encoding="utf-8",
    )
    return dst


def step_parts_to_dxf(
    parts_dir: str | Path,
    output_dir: str | Path | None = None,
    timeout: int = 300,
    dimensions: bool = True,
) -> list[Path]:
    """Project every part STEP in a folder to its own dimensioned DXF.

    ``parts_dir`` holds one ``*.step`` per assembly instance (e.g. the
    ``parts/`` folder the chair exporter writes). Each file goes through
    :func:`step_to_dxf` unchanged - first-angle views, kernel-measured overall
    dimensions - and lands as ``<stem>.dxf`` in ``output_dir`` (default:
    a ``diagrams/`` sibling of ``parts_dir``). Returns the written paths in
    STEP filename order. Raises :class:`ConversionError` when the folder
    holds no STEP files.
    """
    src_dir = Path(parts_dir)
    steps = sorted([*src_dir.glob("*.step"), *src_dir.glob("*.stp")])
    if not steps:
        raise ConversionError(f"no STEP files found in {src_dir}")
    out_dir = Path(output_dir) if output_dir else src_dir.parent / "diagrams"
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for step in steps:
        written.append(step_to_dxf(step, out_dir / f"{step.stem}.dxf", timeout=timeout, dimensions=dimensions))
    return written


# ------------------------------------------------------------------ DXF -> PDF
#
# PyMuPDF draws the sheet directly - no intermediate raster - so
# the PDF stays vector-zoomable. Only the LINE and TEXT entities
# MDIE emits are read; sheet geometry is unit-true (1 unit = 1 mm),
# so the smallest A-series sheet that fits at 1:1 is chosen,
# landscape for wide sheets, and DXF's Y-up axis is flipped to
# the PDF page's Y-down.

#: A-series sheet sizes (portrait, mm), smallest first.
_A_SHEETS_MM = (
    (210.0, 297.0),
    (297.0, 420.0),
    (420.0, 594.0),
    (594.0, 841.0),
    (841.0, 1189.0),
)

#: Drawing millimetres -> PDF points.
_MM_TO_PT = 72.0 / 25.4


def _parse_dxf_pairs(text: str) -> list[tuple[str, str]]:
    """Split a DXF stream into (group code, value) pairs."""
    lines = text.splitlines()
    return [(lines[i].strip(), lines[i + 1].strip()) for i in range(0, len(lines) - 1, 2)]


def _dxf_entities(
    text: str,
) -> tuple[
    list[tuple[str, float, float, float, float]],
    list[tuple[str, float, float, float, str]],
]:
    """Read the LINE and TEXT entities out of a DXF stream.

    Returns ``(lines, texts)`` - each line as ``(layer, x1, y1,
    x2, y2)`` and each text as ``(layer, x, y, height, value)``.
    Malformed entities are skipped rather than failing the sheet.
    """
    lines: list[tuple[str, float, float, float, float]] = []
    texts: list[tuple[str, float, float, float, str]] = []
    entity: dict[str, str] = {}

    def flush() -> None:
        kind = entity.get("0")
        try:
            if kind == "LINE":
                lines.append(
                    (
                        entity.get("8", ""),
                        float(entity["10"]),
                        float(entity["20"]),
                        float(entity["11"]),
                        float(entity["21"]),
                    )
                )
            elif kind == "TEXT":
                texts.append(
                    (
                        entity.get("8", ""),
                        float(entity["10"]),
                        float(entity["20"]),
                        float(entity["40"]),
                        entity.get("1", ""),
                    )
                )
        except (KeyError, ValueError):
            pass

    for code, value in _parse_dxf_pairs(text):
        if code == "0":
            flush()
            entity = {"0": value}
        else:
            entity[code] = value
    flush()
    return lines, texts


def dxf_to_pdf(src: Path, dst: Path) -> Path:
    """Render a DXF sheet as a vector PDF, true to drawing units.

    LINE and TEXT entities are drawn straight into PyMuPDF, so the
    PDF zooms without rasterising. The smallest A-series sheet that
    fits the drawing at 1:1 is chosen (landscape for wide sheets);
    anything larger fits A0 at a reduced scale. DXF's Y-up
    coordinates are flipped to the page's Y-down. Returns ``dst``.
    Raises :class:`ConversionError` when the sheet holds no geometry
    or PyMuPDF is not installed.
    """
    try:
        import fitz
    except ImportError as exc:
        raise ConversionError("DXF -> PDF needs PyMuPDF (import fitz)") from exc

    lines, texts = _dxf_entities(src.read_text(encoding="utf-8"))
    if not lines and not texts:
        raise ConversionError(f"no LINE or TEXT entities in {src.name}")

    # Content box: geometry plus lettering extents (glyph widths
    # approximated from the text height, centred on the insertion
    # point - the justification _dxf_text emits).
    x0 = y0 = float("inf")
    x1 = y1 = float("-inf")
    for _, ax, ay, bx, by in lines:
        x0, x1 = min(x0, ax, bx), max(x1, ax, bx)
        y0, y1 = min(y0, ay, by), max(y1, ay, by)
    for _, x, y, h, value in texts:
        w = 0.56 * h * max(len(value), 1)
        x0, x1 = min(x0, x - w / 2), max(x1, x + w / 2)
        y0, y1 = min(y0, y - h / 2), max(y1, y + h / 2)
    content_w = x1 - x0
    content_h = y1 - y0
    if content_w <= 0 or content_h <= 0:
        raise ConversionError(f"degenerate sheet extent in {src.name}")

    # Smallest A-series sheet that fits at 1:1; oversized
    # assemblies fall back to A0 at a reduced scale.
    landscape = content_w > content_h
    scale, sheet_w, sheet_h = 0.0, *_A_SHEETS_MM[0]
    for w_mm, h_mm in _A_SHEETS_MM:
        if landscape:
            w_mm, h_mm = h_mm, w_mm
        fit = min((w_mm - 20.0) / content_w, (h_mm - 20.0) / content_h)
        if fit >= 1.0:
            scale, sheet_w, sheet_h = 1.0, w_mm, h_mm
            break
        if fit > scale:
            scale, sheet_w, sheet_h = fit, w_mm, h_mm

    page_w = sheet_w * _MM_TO_PT
    page_h = sheet_h * _MM_TO_PT
    margin = 10.0 * _MM_TO_PT
    k = scale * _MM_TO_PT  # drawing mm -> page points

    def px(x: float) -> float:
        return margin + (x - x0) * k

    def py(y: float) -> float:
        return page_h - margin - (y - y0) * k

    doc = fitz.open()
    page = doc.new_page(width=page_w, height=page_h)
    shape = page.new_shape()
    for _, ax, ay, bx, by in lines:
        shape.draw_line(fitz.Point(px(ax), py(ay)), fitz.Point(px(bx), py(by)))
    shape.finish(color=(0.0, 0.0, 0.0), width=max(0.25, 0.5 * k))
    shape.commit()
    for _, x, y, h, value in texts:
        size = h * k
        if not value or size < 0.5:
            continue
        width = fitz.get_text_length(value, fontname="helv", fontsize=size)
        # Middle-centred: the baseline sits ~0.35 em below centre.
        page.insert_text(
            fitz.Point(px(x) - width / 2, py(y) + 0.35 * size),
            value,
            fontname="helv",
            fontsize=size,
            color=(0.0, 0.0, 0.0),
        )
    dst.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(dst))
    doc.close()
    return dst


def dxfs_to_pdf(srcs: Iterable[Path], dst: Path) -> Path:
    """Merge many DXF sheets into a single multi-page vector PDF."""
    from convert.sheets import merge_pdfs

    with tempfile.TemporaryDirectory() as tmp:
        pages: list[Path] = []
        for src in srcs:
            one = Path(tmp) / f"{Path(src).stem}.pdf"
            dxf_to_pdf(src, one)
            pages.append(one)
        return merge_pdfs(pages, dst)
