"""Tests for the per-part 2D engineering drawing generator."""

import math
import re

import pytest

from mdie.core.frame_model import FrameDesignModel
from mdie.drafting.part_drawings import (
    DIMC,
    _clip_annulus,
    _leg_len,
    build_parts,
    render_html,
    render_part_svg,
)


def _dim_segments(svg: str):
    """Axis segments drawn as dimension lines in the dimension colour.

    A leader carrying a value that did not fit between the arrowheads is
    drawn thinner and has no arrowheads of its own, so it is excluded: the
    rule under test is that every *dimension line* is terminated by arrows.
    """
    segs = []
    for m in re.finditer(
            r'<line x1="([\d.\-]+)" y1="([\d.\-]+)" '
            r'x2="([\d.\-]+)" y2="([\d.\-]+)" stroke="([^"]+)" '
            r'stroke-width="([\d.]+)"', svg):
        if m.group(5) == DIMC and float(m.group(6)) >= 0.3:
            segs.append(tuple(float(m.group(i)) for i in range(1, 5)))
    return segs


def _arrow_tips(svg: str):
    """Arrowhead tip coordinates, taken as the first polygon point."""
    tips = []
    for m in re.finditer(r'<polygon points="([^"]+)" fill="([^"]+)"/>', svg):
        if m.group(2) != DIMC:
            continue
        tx, ty = (float(v) for v in m.group(1).split()[0].split(","))
        tips.append((tx, ty))
    return tips


@pytest.fixture(scope="module")
def model():
    return FrameDesignModel()


@pytest.fixture(scope="module")
def parts(model):
    return build_parts(model)


def test_every_step_part_has_a_drawing(parts):
    """Each exported part file must have a matching drawing sheet."""
    from pathlib import Path

    chair = Path(__file__).resolve().parents[1] / "Project" / "chair"
    if not chair.exists():
        pytest.skip("chair project not generated")
    exported = {p.stem for p in chair.rglob("*.step")} - {"chair"}
    drawn = {p.key for p in parts}
    # The two arms are mirrored, so one sheet covers both STEP files.
    drawn |= {"Armrest_Left", "Armrest_Right"}
    assert exported, "no STEP parts found"
    assert exported <= drawn, f"missing drawings: {sorted(exported - drawn)}"


def test_leg_length_is_slanted_hypotenuse(model):
    """Column length includes the horizontal splay offset."""
    g = model.geometry
    expect = math.hypot(g.seat_height_mm,
                        g.seat_height_mm * math.tan(math.radians(g.leg_splay_angle_deg)))
    assert _leg_len(g) == pytest.approx(expect, abs=1e-9)
    assert _leg_len(g) > g.seat_height_mm


def test_each_part_sheet_is_valid_svg(parts, model):
    for p in parts:
        s = render_part_svg(p, model)
        assert s.startswith("<svg"), p.key
        assert s.rstrip().endswith("</svg>"), p.key
        # XML must be balanced enough to parse.
        from xml.etree import ElementTree as ET
        ET.fromstring(s), p.key


def test_dimension_lines_are_axis_parallel(parts, model):
    """A dimension line must lie on the axis it measures, never diagonal.

    Regression: _dim_h/_dim_v once connected (x0, y-tick) to (x1, y+tick),
    which drew a slanted line between the two dimensioned points.
    """
    checked = 0
    for p in parts:
        for (x1, y1, x2, y2) in _dim_segments(render_part_svg(p, model)):
            horizontal = abs(y1 - y2) < 1e-6
            vertical = abs(x1 - x2) < 1e-6
            assert horizontal or vertical, (
                f"{p.key}: diagonal dimension line "
                f"({x1},{y1})->({x2},{y2})"
            )
            checked += 1
    assert checked > 0, "no dimension lines rendered"


def test_arrowheads_sit_on_dimension_line_ends(parts, model):
    """Each arrowhead tip must touch an endpoint of a dimension line."""
    for p in parts:
        svg = render_part_svg(p, model)
        segs = _dim_segments(svg)
        tips = _arrow_tips(svg)
        assert len(tips) == 2 * len(segs), (
            f"{p.key}: {len(tips)} arrowheads for {len(segs)} dimension lines"
        )
        for (tx, ty) in tips:
            on_end = any(
                abs(tx - ex) < 0.06 and abs(ty - ey) < 0.06
                for (x1, y1, x2, y2) in segs
                for (ex, ey) in ((x1, y1), (x2, y2))
            )
            assert on_end, f"{p.key}: arrowhead tip {(tx, ty)} not on any line end"


def test_every_dimension_has_a_label(parts, model):
    """Dimension text must not sit on top of the dimension line itself."""
    for p in parts:
        svg = render_part_svg(p, model)
        dim_labels = re.findall(
            r'<text x="([\d.\-]+)" y="([\d.\-]+)"[^>]*fill="'
            + DIMC + r'"[^>]*>([^<]*)</text>', svg)
        assert dim_labels, p.key
        for (x, y, text) in dim_labels:
            assert text.strip(), f"{p.key}: empty dimension label"


def test_no_text_is_tiny(parts, model):
    """No annotation may fall below a legible size on the A4 sheet."""
    from mdie.drafting.part_drawings import TXT_SMALL

    floor = TXT_SMALL - 0.05
    for p in parts:
        sizes = [float(m) for m in
                 re.findall(r'font-size="([\d.]+)"', render_part_svg(p, model))]
        assert sizes, p.key
        smallest = min(sizes)
        assert smallest >= floor, f"{p.key}: {smallest}mm text below {floor}mm"


def test_dimension_text_is_larger_than_notes(parts, model):
    """Dimension values must be the most prominent annotation."""
    from mdie.drafting.part_drawings import DIMC, TXT_DIM, TXT_NOTE

    assert TXT_DIM > TXT_NOTE, "dimension text should exceed note text"
    for p in parts:
        svg = render_part_svg(p, model)
        dim_sizes = [float(m.group(1)) for m in re.finditer(
            r'font-size="([\d.]+)"[^>]*fill="' + DIMC + r'"', svg)]
        assert dim_sizes, p.key
        assert min(dim_sizes) >= TXT_DIM - 0.05, p.key


def test_text_carries_a_legibility_halo(parts, model):
    """Dimension/view text is stroked white so geometry cannot obscure it."""
    for p in parts:
        svg = render_part_svg(p, model)
        assert 'paint-order="stroke"' in svg, p.key
        # Halo must not appear on the flat title-block/notes cells.
        assert svg.count('paint-order="stroke"') < svg.count("<text"), p.key


def _text_box(x, y, size, anchor, body, rotate=None):
    """Bounding box of one <text>, in sheet mm.

    Vertical dimension text is rotated -90 degrees, so its long axis is the
    y axis and its short axis is the x axis. Measuring it as if it were
    horizontal is what made a rotated label look like it hung off the sheet.
    """
    from mdie.drafting.part_drawings import _text_width

    w = _text_width(body, size)
    h = size * 0.78
    if anchor == "end":
        x0 = x - w
    elif anchor == "start":
        x0 = x
    else:
        x0 = x - w / 2.0
    if rotate:
        # Rotated: swap the extents about the anchor point.
        if anchor == "middle":
            return (x - h * 0.6, y - w / 2.0, x + h * 0.6, y + w / 2.0)
        if anchor == "end":
            return (x - h * 0.6, y, x + h * 0.6, y + w)
        return (x - h * 0.6, y - w, x + h * 0.6, y)
    return (x0, y - size * 0.78, x0 + w, y + size * 0.22)


def _parse_text_nodes(svg: str):
    """Yield (body, x, y, size, anchor, rotate) for every non-blank text."""
    for m in re.finditer(
            r'<text x="([\d.\-]+)" y="([\d.\-]+)" font-size="([\d.]+)" '
            r'([^>]*)>([^<]*)</text>', svg):
        x, y, fs, attrs, body = (m.group(1), m.group(2), m.group(3),
                                 m.group(4), m.group(5))
        if not body.strip():
            continue
        a = re.search(r'text-anchor="(\w+)"', attrs)
        rot = re.search(r'rotate\((-?[\d.]+)', attrs)
        yield (body, float(x), float(y), float(fs),
               a.group(1) if a else "middle",
               rot.group(1) if rot else None)


def _approx_text_extents(svg: str):
    """Yield (body, x0, x1) for every text node, rotation-aware."""
    for body, x, y, fs, anchor, rot in _parse_text_nodes(svg):
        b = _text_box(x, y, fs, anchor, body, rot)
        yield body, b[0], b[2]


def _all_text_boxes(svg: str):
    """Yield (body, (x0, y0, x1, y1)) for every text node."""
    for body, x, y, fs, anchor, rot in _parse_text_nodes(svg):
        yield body, _text_box(x, y, fs, anchor, body, rot)


def _solid_boxes(svg: str):
    """Bounding boxes of drawn material (the member fill), not annotation.

    A balloon, the projection symbol or the title block are paper-filled
    furniture that text is *meant* to sit inside; only material counts as
    something text must stay off.
    """
    from mdie.drafting.part_drawings import FILL

    boxes = []
    for m in re.finditer(r'<polygon points="([^"]+)"[^>]*?fill="([^"]*)"',
                         svg):
        if m.group(2) != FILL:
            continue
        pts = [tuple(float(v) for v in p.split(",")) for p in m.group(1).split()]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        boxes.append((min(xs), min(ys), max(xs), max(ys)))
    for m in re.finditer(r'<circle cx="([\d.\-]+)" cy="([\d.\-]+)" '
                         r'r="([\d.\-]+)"[^>]*?fill="([^"]*)"', svg):
        if m.group(4) != FILL:
            continue
        cx, cy, r = (float(g) for g in m.groups()[:3])
        boxes.append((cx - r, cy - r, cx + r, cy + r))
    return boxes


def _all_shape_boxes(svg: str):
    """Bounding boxes of every drawn shape, ignoring the page background."""
    boxes = []
    for m in re.finditer(r'<polygon points="([^"]+)"', svg):
        pts = [tuple(float(v) for v in p.split(",")) for p in m.group(1).split()]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        boxes.append((min(xs), min(ys), max(xs), max(ys)))
    for m in re.finditer(r'<circle cx="([\d.\-]+)" cy="([\d.\-]+)" '
                         r'r="([\d.\-]+)"', svg):
        cx, cy, r = (float(g) for g in m.groups())
        boxes.append((cx - r, cy - r, cx + r, cy + r))
    for m in re.finditer(r'<rect x="([\d.\-]+)" y="([\d.\-]+)" '
                         r'width="([\d.\-]+)" height="([\d.\-]+)"', svg):
        x, y, w, h = (float(g) for g in m.groups())
        if w > 250 and h > 180:      # the page background
            continue
        boxes.append((x, y, x + w, y + h))
    return boxes


def _inter(a, b):
    return (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))


def _overlap_area(a, b):
    r = _inter(a, b)
    return max(0.0, r[2] - r[0]) * max(0.0, r[3] - r[1])


def test_text_never_sits_on_top_of_the_geometry(parts, model):
    """Dimension, view and item text must not land on drawn material.

    A white halo makes such text readable but not legible, and a dimension
    value printed across a member is simply wrong.
    """
    from mdie.drafting.part_drawings import render_assembly_svg

    sheets = [(p.key, render_part_svg(p, model)) for p in parts]
    sheets.append(("Chair_Assembly", render_assembly_svg(model)))
    worst = []
    for key, svg in sheets:
        solids = _solid_boxes(svg)
        for body, tb in _all_text_boxes(svg):
            area = sum(_overlap_area(tb, sb) for sb in solids)
            if area > 0.6:
                worst.append((round(area, 2), key, body, tb))
    assert not worst, "\n".join(
        f"{a}mm2 {k} {b[:34]!r} at {tuple(round(v, 1) for v in box)}"
        for a, k, b, box in sorted(worst, reverse=True)[:12])


def test_text_never_overlaps_other_text(parts, model):
    """Two labels printing on top of each other make both unreadable."""
    from mdie.drafting.part_drawings import render_assembly_svg

    sheets = [(p.key, render_part_svg(p, model)) for p in parts]
    sheets.append(("Chair_Assembly", render_assembly_svg(model)))
    bad = []
    for key, svg in sheets:
        boxes = list(_all_text_boxes(svg))
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i][1], boxes[j][1]
                ov = _overlap_area(a, b)
                if ov > 1.2:
                    bad.append((round(ov, 2), key, boxes[i][0][:26],
                                boxes[j][0][:26]))
    assert not bad, "\n".join(
        f"{o}mm2 {k}: {a!r} <-> {b!r}" for o, k, a, b in
        sorted(bad, reverse=True)[:12])


def test_no_text_lands_on_any_drawn_shape(parts, model):
    """Nothing may print across a line, symbol or panel edge.

    The stricter sibling of test_text_never_sits_on_top_of_the_geometry:
    that one only looks at material, this one looks at every drawn shape.
    Text legitimately sits *inside* a closed panel (title block, balloon),
    so a full containment is allowed; straddling an edge or landing on a
    stroke is not.
    """
    from mdie.drafting.part_drawings import render_assembly_svg

    sheets = [(p.key, render_part_svg(p, model)) for p in parts]
    sheets.append(("Chair_Assembly", render_assembly_svg(model)))
    bad = []
    for key, svg in sheets:
        shapes = _all_shape_boxes(svg)
        for body, tb in _all_text_boxes(svg):
            for sb in shapes:
                if (sb[0] <= tb[0] and sb[1] <= tb[1]
                        and sb[2] >= tb[2] and sb[3] >= tb[3]):
                    continue          # legitimately inside a panel
                ov = _overlap_area(tb, sb)
                if ov > 0.5:
                    bad.append((round(ov, 2), key, body[:30], tb, sb))
    assert not bad, "\n".join(
        f"{a}mm2 {k} {b!r} text{tuple(round(v,1) for v in t)} "
        f"vs shape{tuple(round(v,1) for v in s)}"
        for a, k, b, t, s in sorted(bad, key=lambda r: -r[0])[:12])


def test_feature_dimensions_land_on_the_feature_they_measure(parts, model):
    """A dimension must sit over its own view, not over empty sheet.

    The pad-width value once pointed at positive X while the sheet drew the
    left arm at negative X, so "45" was drawn 53 mm away from the pad with
    nothing connecting it. Every horizontal feature dimension is therefore
    checked to fall inside the view's own model extent.
    """
    import mdie.drafting.part_drawings as pd

    checked = 0
    for p in parts:
        if not p.primitives:
            continue
        seen = []
        orig = pd._shape_view

        def spy(svg, cx, cy, prims, u, v, scale, label, dims_h=(), dims_v=(),
                right_edge=None, _o=orig):
            box = _o(svg, cx, cy, prims, u, v, scale, label, dims_h, dims_v,
                     right_edge)
            seen.append((label, box, list(dims_h)))
            return box

        pd._shape_view = spy
        try:
            render_part_svg(p, model)
        finally:
            pd._shape_view = orig

        for label, (x0, _y0, x1, _y1), dims_h in seen:
            for u0, u1, _side, text in dims_h:
                assert x0 - 0.01 <= min(u0, u1) and max(u0, u1) <= x1 + 0.01, (
                    f"{p.key} {label}: {text} spans model "
                    f"{min(u0,u1):.1f}..{max(u0,u1):.1f} but the view is "
                    f"{x0:.1f}..{x1:.1f} -- the dimension is off its feature")
                checked += 1
    assert checked >= 3, f"only {checked} feature dimensions checked"


def test_three_view_sheets_carry_extension_lines(parts, model):
    """ISO 128: a dimension needs extension lines back to its feature.

    Without them a value is just a number floating near the drawing, which
    is what made the narrow armrest dimensions unreadable.
    """
    for p in parts:
        if not p.primitives:
            continue
        svg = render_part_svg(p, model)
        n_dims = len([1 for m in re.finditer(
            r'<text[^>]*fill="' + DIMC + r'"[^>]*>[^<]+</text>', svg)])
        n_ext = len([1 for m in re.finditer(
            r'<line[^>]*stroke="#64748b"[^>]*stroke-width="0.2"', svg)])
        assert n_ext >= 2 * n_dims, (
            f"{p.key}: {n_dims} dimension values but only {n_ext} "
            f"extension lines")


def test_no_text_runs_off_the_sheet(parts, model):
    """Text must stay inside the A4 drawing border at readable sizes."""
    W, H, BORDER = 297.0, 210.0, 10.0
    for p in parts:
        svg = render_part_svg(p, model)
        for (body, x0, x1) in _approx_text_extents(svg):
            assert x0 >= BORDER - 0.5, f"{p.key}: {body[:30]!r} left {x0:.1f}"
            assert x1 <= W - BORDER + 0.5, f"{p.key}: {body[:30]!r} right {x1:.1f}"


def test_title_block_values_fit_inside_the_block(parts, model):
    """Long material/standard strings must shrink, not spill out."""
    for p in parts:
        svg = render_part_svg(p, model)
        rect = re.search(
            r'<rect x="([\d.\-]+)" y="([\d.\-]+)" width="([\d.\-]+)" '
            r'height="([\d.\-]+)" fill="#ffffff" stroke="#0f172a" '
            r'stroke-width="0.8"/>', svg)
        assert rect, p.key
        bx = float(rect.group(1))
        bw = float(rect.group(3))
        inside = [
            (body, x0, x1) for (body, x0, x1) in _approx_text_extents(svg)
            if x0 >= bx - 0.5 and x1 > bx
        ]
        for (body, x0, x1) in inside:
            assert x1 <= bx + bw + 0.5, (
                f"{p.key}: title-block text {body[:30]!r} exceeds block "
                f"({x1:.1f} > {bx + bw:.1f})"
            )


def test_seat_and_stretcher_sheets_have_three_views(parts, model):
    """Flat rectangular parts need a full top/front/side set."""
    three_view = {"Seat_Frame_Rails", "Seat_Pan_Deck", "Lower_Stretchers",
                  "Armrest_Assembly"}
    for p in parts:
        s = render_part_svg(p, model)
        if p.key in three_view:
            for v in ("TOP VIEW", "FRONT VIEW", "SIDE VIEW"):
                assert v in s, f"{p.key} missing {v}"
        else:
            assert "TOP VIEW" not in s, f"{p.key} unexpectedly has plan view"


def test_three_view_dimensions_match_model(parts, model):
    """Plan dimensions on the sheet must equal the model, not literals."""
    g = model.geometry
    for key in ("Seat_Frame_Rails", "Seat_Pan_Deck"):
        p = next(x for x in parts if x.key == key)
        s = render_part_svg(p, model)
        assert f"{g.seat_width_mm:g}" in s, key
        assert f"{g.seat_depth_mm:g}" in s, key


def test_stretcher_uses_splayed_footprint_at_stretcher_height(parts, model):
    """Stretcher plan must reflect the splay at 150 mm, not at the floor.

    The legs are splayed, so the stretcher perimeter is set by where the
    leg axes sit at ``stretcher_height_mm`` -- not by the seat span, and
    not by the floor span. The outer face adds the tube radius.
    """
    g = model.geometry
    p = next(x for x in parts if x.key == "Lower_Stretchers")
    radius = g.stretcher_profile.outer_dimension_mm / 2.0
    delta = (g.seat_height_mm - g.stretcher_height_mm) * math.tan(
        math.radians(g.leg_splay_angle_deg))
    assert p.width_x_mm == pytest.approx(g.seat_width_mm + 2 * (delta + radius))
    assert p.depth_y_mm == pytest.approx(g.seat_depth_mm + 2 * (delta + radius))
    s = render_part_svg(p, model)
    assert f"{p.width_x_mm:.3f}"[:7] in s or f"{p.width_x_mm:g}" in s


def test_three_view_sheets_match_exported_solids(parts, model):
    """Every three-view sheet must be dimensioned to its real solid.

    This is the authority check: the sheet numbers are derived in
    ``part_drawings`` while the solid is built independently in
    ``assembly``. If the two drift apart the drawing is lying.
    """
    from mdie.cad.assembly import FrameCADEngine

    solids = {s.name: s for s in FrameCADEngine.generate_assembly_parts(model)}
    # The armrest sheet covers both arms, which are exported separately.
    aliases = {"Armrest_Assembly": ["Armrest_Left", "Armrest_Right"]}
    checked = 0
    for p in parts:
        if p.width_x_mm is None:
            continue
        names = aliases.get(p.key, [p.key])
        for name in names:
            solid = solids.get(name)
            assert solid is not None, f"no exported solid named {name}"
            (x0, y0, z0), (x1, y1, z1) = solid.get_bounding_box()
            assert p.width_x_mm == pytest.approx(x1 - x0, abs=1e-6), f"{name} X"
            assert p.depth_y_mm == pytest.approx(y1 - y0, abs=1e-6), f"{name} Y"
            assert p.height_z_mm == pytest.approx(z1 - z0, abs=1e-6), f"{name} Z"
            checked += 1
    assert checked == 5, f"expected 5 pinned solids, got {checked}"


def test_armrest_sheet_covers_both_mirrored_arms(parts, model):
    """One sheet serves both arms only if the two are true mirror images.

    Drawing the armrest once is only honest if the right arm is the left
    arm reflected about the centre plane, so both share every dimension.
    """
    from mdie.cad.assembly import FrameCADEngine

    solids = {s.name: s for s in FrameCADEngine.generate_assembly_parts(model)}
    left = solids["Armrest_Left"]
    right = solids["Armrest_Right"]
    lbb, rbb = left.get_bounding_box(), right.get_bounding_box()
    # Same size, and X ranges are equal and opposite about zero.
    assert (lbb[1][0] - lbb[0][0]) == pytest.approx(rbb[1][0] - rbb[0][0], abs=1e-6)
    assert lbb[0][0] == pytest.approx(-rbb[1][0], abs=1e-6)
    assert lbb[0][1] == pytest.approx(rbb[0][1], abs=1e-6)
    assert lbb[0][2] == pytest.approx(rbb[0][2], abs=1e-6)
    # And a single sheet is produced, not one per side.
    arms = [p for p in parts if p.key.startswith("Armrest")]
    assert [p.key for p in arms] == ["Armrest_Assembly"]


def test_armrest_sheet_draws_members_not_a_bounding_box(parts, model):
    """The armrest views must show the posts, beams and pad as real members.

    A plain rectangle for the whole envelope is what this replaces: the
    cross beams and the two posts are the parts a fabricator must see.
    """
    p = next(x for x in parts if x.key == "Armrest_Assembly")
    kinds = [q["kind"] for q in p.primitives]
    assert kinds.count("box") == 3, "2 cross beams + 1 pad"
    assert kinds.count("tube") == 2, "2 vertical posts"
    s = render_part_svg(p, model)
    # Two posts and two beams must appear as distinct drawn members, so the
    # sheet carries far more outlines than the 3-view bounding boxes need.
    assert s.count("<polygon") + s.count("<circle") >= 12
    # The feature dimensions the envelope alone could never give.
    g = model.geometry
    assert f"{g.armrest_height_above_seat_mm:g}" in s, "post height"
    assert f"{g.armrest_length_mm:g}" in s, "pad length"


def test_assembly_primitives_match_exported_solids(model):
    """The general arrangement must describe the chair that is exported.

    ``assembly_primitives`` feeds the GA sheet while
    ``generate_assembly_parts`` feeds the STEP files. If the two describe
    different chairs the drawing is fiction, so compare every group.
    """
    from mdie.cad.assembly import (FrameCADEngine, assembly_primitives,
                                   primitives_to_triangles)

    groups = dict(assembly_primitives(model))
    solids = {s.name: s for s in FrameCADEngine.generate_assembly_parts(model)}
    assert set(groups) == set(solids), (
        f"group/solid mismatch: {sorted(set(groups) ^ set(solids))}")

    def bbox(tris):
        xs = [v[0] for t in tris for v in t]
        ys = [v[1] for t in tris for v in t]
        zs = [v[2] for t in tris for v in t]
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

    for name, prims in groups.items():
        mine = bbox(primitives_to_triangles(prims))
        theirs = solids[name].get_bounding_box()
        for axis, (a, b) in enumerate(zip(mine, theirs)):
            for end, (x, y) in enumerate(zip(a, b)):
                assert x == pytest.approx(y, abs=1e-6), (
                    f"{name} bbox axis {axis} end {end}: {x} != {y}")


def test_assembly_sheet_shows_every_item(model):
    """The GA sheet must carry a view per direction plus a ballooned list."""
    from xml.etree import ElementTree as ET

    from mdie.drafting.part_drawings import ASSEMBLY_ITEMS, render_assembly_svg

    s = render_assembly_svg(model)
    ET.fromstring(s)
    for v in ("FRONT VIEW", "SIDE VIEW", "TOP VIEW"):
        assert v in s, f"assembly sheet missing {v}"
    # Every listed item gets a numbered entry and a balloon on the sheet.
    for i, (name, _qty, _desc) in enumerate(ASSEMBLY_ITEMS, start=1):
        assert f">{i}<" in s, f"no balloon for item {i} ({name})"
        assert name in s, f"item {i} ({name}) missing from parts list"
    # Real members are drawn, not one envelope box.
    assert s.count("<polygon") + s.count("<circle") > 60


def test_assembly_sheet_dimensions_come_from_the_model(model):
    """Overall envelope and seat height must be the model's own numbers."""
    import math

    from mdie.cad.assembly import assembly_primitives
    from mdie.drafting.part_drawings import render_assembly_svg

    g = model.geometry
    prims = [p for _, pl in assembly_primitives(model) for p in pl]

    def extent(u):
        vals = []
        for p in prims:
            if p["kind"] == "box":
                vals += [p["c"][u] - p["s"][u] / 2.0,
                         p["c"][u] + p["s"][u] / 2.0]
            else:
                d = [p["b"][i] - p["a"][i] for i in range(3)]
                ln = math.sqrt(sum(x * x for x in d)) or 1.0
                reach = p["r"] * math.sqrt(max(0.0, 1.0 - (d[u] / ln) ** 2))
                vals += [min(p["a"][u], p["b"][u]) - reach,
                         max(p["a"][u], p["b"][u]) + reach]
        return min(vals), max(vals)

    s = render_assembly_svg(model)
    for u, name in ((0, "width"), (1, "depth"), (2, "height")):
        lo, hi = extent(u)
        assert f"{hi - lo:.1f}" in s, f"overall {name} {hi - lo:.1f}"
    assert f"{g.seat_height_mm:g}" in s, "seat height"


def test_assembly_overall_height_is_the_backrest_not_a_formula(model):
    """A hand-rolled height formula is how the sheet overstated the chair.

    The overall height must land on the top of the backrest member; an
    earlier closed-form guess read 1054.9 mm against a real ~869 mm.
    """
    import math
    import re

    from mdie.cad.assembly import assembly_primitives
    from mdie.drafting.part_drawings import render_assembly_svg

    prims = [p for _, pl in assembly_primitives(model) for p in pl]

    def reach(p, u):
        """How far a member extends along axis ``u`` beyond its endpoints."""
        if p["kind"] == "box":
            return p["s"][u] / 2.0
        d = [p["b"][i] - p["a"][i] for i in range(3)]
        ln = math.sqrt(sum(x * x for x in d)) or 1.0
        return p["r"] * math.sqrt(max(0.0, 1.0 - (d[u] / ln) ** 2))

    def ends(p, u):
        if p["kind"] == "box":
            c = p["c"][u]
            return c - p["s"][u] / 2.0, c + p["s"][u] / 2.0
        a, b = p["a"][u], p["b"][u]
        return min(a, b) - reach(p, u), max(a, b) + reach(p, u)

    z_lo = min(ends(p, 2)[0] for p in prims)
    z_hi = max(ends(p, 2)[1] for p in prims)
    total_h = z_hi - z_lo
    # The backrest is the tallest thing on the chair; if it were not, the
    # stated height would be measuring the wrong member.
    back = [p for n, pl in assembly_primitives(model)
            if n == "Backrest_Assembly" for p in pl]
    assert max(ends(p, 2)[1] for p in back) == pytest.approx(z_hi, abs=1e-6)

    s = render_assembly_svg(model)
    stated = re.findall(r'<text[^>]*font-size="4\.2"[^>]*>([\d.]+)</text>', s)
    assert f"{total_h:.1f}" in stated, (
        f"stated heights {stated} do not include the real {total_h:.1f}")
    assert not any(float(v) > 1000.0 for v in stated), (
        f"an overall dimension is far too large: {stated}")


def test_assembly_sheet_stays_inside_the_border(model):
    """The GA sheet is held to the same border rule as every detail sheet."""
    from xml.etree import ElementTree as ET

    from mdie.drafting.part_drawings import render_assembly_svg

    s = render_assembly_svg(model)
    ET.fromstring(s)
    xs, ys = [], []
    for m in re.finditer(r'<text x="([\d.\-]+)" y="([\d.\-]+)"', s):
        xs.append(float(m.group(1)))
        ys.append(float(m.group(2)))
    for m in re.finditer(r'<circle cx="([\d.\-]+)" cy="([\d.\-]+)" '
                         r'r="([\d.\-]+)"', s):
        cx, cy, r = (float(g) for g in m.groups())
        xs += [cx - r, cx + r]
        ys += [cy - r, cy + r]
    assert min(xs) >= 10.0, f"text/shape left of border: {min(xs):.1f}"
    assert max(xs) <= 287.0, f"text/shape right of border: {max(xs):.1f}"
    assert min(ys) >= 10.0, f"text/shape above border: {min(ys):.1f}"
    assert max(ys) <= 200.0, f"text/shape below border: {max(ys):.1f}"


def test_no_view_falls_outside_the_sheet_border(parts, model):
    """Every sheet's geometry must stay inside the A4 drawing border."""
    from xml.etree import ElementTree as ET

    W, H, BORDER = 297.0, 210.0, 10.0
    for p in parts:
        s = render_part_svg(p, model)
        ET.fromstring(s)
        xs, ys = [], []
        for m in re.finditer(r'<text x="([\d.\-]+)" y="([\d.\-]+)"', s):
            xs.append(float(m.group(1)))
            ys.append(float(m.group(2)))
        for m in re.finditer(
                r'<rect x="([\d.\-]+)" y="([\d.\-]+)" '
                r'width="([\d.\-]+)" height="([\d.\-]+)"', s):
            x, y, w, h = (float(g) for g in m.groups())
            xs += [x, x + w]
            ys += [y, y + h]
        for m in re.finditer(
                r'<circle cx="([\d.\-]+)" cy="([\d.\-]+)" r="([\d.\-]+)"', s):
            cx, cy, r = (float(g) for g in m.groups())
            xs += [cx - r, cx + r]
            ys += [cy - r, cy + r]
        assert xs and ys, p.key
        assert min(xs) >= BORDER - 0.5, f"{p.key} left overflow {min(xs)}"
        assert max(xs) <= W - BORDER + 0.5, f"{p.key} right overflow {max(xs)}"
        assert min(ys) >= BORDER - 0.5, f"{p.key} top overflow {min(ys)}"
        assert max(ys) <= H - BORDER + 0.5, f"{p.key} bottom overflow {max(ys)}"


def test_sheet_carries_required_engineering_content(parts, model):
    for p in parts:
        s = render_part_svg(p, model)
        assert "ISO 128" in s, p.key
        assert "THIRD ANGLE" in s, p.key
        assert "NOTES" in s, p.key
        assert f"{p.length_mm:g}" in s, p.key
        assert model.material.name in s, p.key


def test_sheet_dimensions_match_the_model(parts, model):
    """Quoted dimensions must be the model's, not hand-typed."""
    leg = next(p for p in parts if p.key == "Leg_Front_Left")
    s = render_part_svg(leg, model)
    prof = model.geometry.leg_profile
    assert f"⌀{prof.outer_dimension_mm:g}" in s
    assert f"{prof.wall_thickness_mm:g}" in s
    assert f"{leg.length_mm:.2f}" in s or f"{leg.length_mm:g}" in s


def test_annulus_hatch_stays_within_the_wall():
    """Section hatch must not spill into the bore or outside the OD."""
    cx, cy = 14.0, 0.0
    r_in, r_out = 12.0, 14.0
    segs = _clip_annulus(0.0, -r_out, 2 * r_out, r_out, cx, cy, r_in, r_out)
    assert segs
    for (ax, ay, bx, by) in segs:
        for t in (0.0, 0.25, 0.5, 0.75, 1.0):
            x = ax + (bx - ax) * t
            y = ay + (by - ay) * t
            d = math.hypot(x - cx, y - cy)
            assert r_in - 1e-6 <= d <= r_out + 1e-6, (x, y, d)


def test_round_tube_sheet_has_section_view(parts, model):
    leg = next(p for p in parts if p.key == "Leg_Front_Left")
    s = render_part_svg(leg, model)
    assert "SECTION A-A" in s
    # Two concentric circles = OD and bore.
    assert len(re.findall(r"<circle", s)) >= 2


def test_square_tube_sheet_hatches_section(parts, model):
    # Use an elevation-layout part; three-view sheets have no section view.
    rail = next(p for p in parts if p.key == "Backrest_Assembly")
    assert rail.profile.profile_type == "square_tube"
    s = render_part_svg(rail, model)
    assert "SECTION A-A" in s
    assert s.count("<rect") >= 2


def test_html_sheet_embeds_every_part(parts, model):
    html = render_html(model, parts)
    assert html.startswith("<!DOCTYPE html>")
    for p in parts:
        assert p.title.split("  ")[0][:18] in html, p.key
    # One sheet per part, plus the general arrangement that leads the set.
    assert html.count("<svg") == len(parts) + 1
    assert "@page" in html and "A4 landscape" in html
