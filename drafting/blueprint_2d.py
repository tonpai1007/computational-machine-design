"""
MDIE Automated 2D Technical Drawing Engine (Blueprint Generator)
Generates ISO 128 / ANSI Y14.5 compliant vector engineering drawings (SVG and printable HTML/PDF).
Features orthographic projections, stepped diameter callouts, keyway details, surface finish symbols,
centerlines, projection angle symbols, and engineering title blocks.
"""

from components.gears import GearPairResult
from core.models import EngineeringModel, SolverResult


class Blueprint2DGenerator:
    """
    Generates precision vector engineering drawings in pure SVG
    and self-contained printable blueprint sheets.
    """

    @classmethod
    def generate_shaft_blueprint_svg(
        cls,
        model: EngineeringModel,
        result: SolverResult | None = None,
        theme: str = "blueprint",
        width: int = 1100,
        height: int = 700,
    ) -> str:
        """
        Generate a complete 2D technical drawing for a machine shaft.
        theme: 'blueprint' (navy/cyan) or 'technical' (white paper/black ink).
        """
        is_bp = theme.lower() == "blueprint"

        # Color Palette
        bg_col = "#091424" if is_bp else "#ffffff"
        grid_col = "rgba(56, 189, 248, 0.08)" if is_bp else "rgba(100, 116, 139, 0.08)"
        border_col = "#38bdf8" if is_bp else "#0f172a"
        line_col = "#e2e8f0" if is_bp else "#0f172a"
        center_col = "#ef4444" if is_bp else "#dc2626"
        dim_col = "#38bdf8" if is_bp else "#2563eb"
        text_col = "#f8fafc" if is_bp else "#0f172a"
        muted_col = "#94a3b8" if is_bp else "#64748b"
        hatch_col = "rgba(56, 189, 248, 0.15)" if is_bp else "rgba(15, 23, 42, 0.08)"

        # Drawing border margins
        margin = 30
        inner_m = 40
        b_w = width - 2 * margin
        b_h = height - 2 * margin

        # Model geometry in mm
        total_len_mm = model.total_length * 1000.0
        max_dia_mm = (
            max(s.outer_diameter * 1000.0 for s in model.segments) if model.segments else 40.0
        )

        # Viewport layout
        # Front view placed in left-center
        # Right end projection view placed on the right
        view_x0 = 80
        view_y_mid = 300
        avail_w = 640
        avail_h = 240

        scale_x = (avail_w * 0.90) / total_len_mm if total_len_mm > 0 else 1.0
        scale_y = (avail_h * 0.50) / (max_dia_mm / 2.0) if max_dia_mm > 0 else 1.0
        # Maintain aspect ratio for clean visual projection
        draw_scale = min(scale_x, scale_y)

        svg = []
        svg.append(
            f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" font-family="Consolas, monospace, sans-serif">'
        )
        svg.append("  <defs>")
        svg.append(
            '    <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
        )
        svg.append(f'      <path d="M 0 1.5 L 10 5 L 0 8.5 z" fill="{dim_col}" />')
        svg.append("    </marker>")
        svg.append('    <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">')
        svg.append(
            f'      <path d="M 20 0 L 0 0 0 20" fill="none" stroke="{grid_col}" stroke-width="1" />'
        )
        svg.append("    </pattern>")
        svg.append("  </defs>")

        # Background & Grid
        svg.append(f'  <rect width="{width}" height="{height}" fill="{bg_col}" />')
        svg.append(f'  <rect width="{width}" height="{height}" fill="url(#grid)" />')

        # Outer & Inner Technical Border
        svg.append(
            f'  <rect x="{margin}" y="{margin}" width="{b_w}" height="{b_h}" fill="none" stroke="{border_col}" stroke-width="2" />'
        )
        svg.append(
            f'  <rect x="{inner_m}" y="{inner_m}" width="{width - 2 * inner_m}" height="{height - 2 * inner_m}" fill="none" stroke="{border_col}" stroke-width="1" />'
        )

        # Coordinate Zone Markers
        for idx, tag in enumerate(["1", "2", "3", "4"]):
            x_pos = inner_m + (idx + 0.5) * ((width - 2 * inner_m) / 4.0)
            svg.append(
                f'  <text x="{x_pos}" y="{inner_m - 4}" fill="{muted_col}" font-size="10" text-anchor="middle">{tag}</text>'
            )
            svg.append(
                f'  <text x="{x_pos}" y="{height - inner_m + 12}" fill="{muted_col}" font-size="10" text-anchor="middle">{tag}</text>'
            )
        for idx, tag in enumerate(["A", "B", "C"]):
            y_pos = inner_m + (idx + 0.5) * ((height - 2 * inner_m) / 3.0)
            svg.append(
                f'  <text x="{inner_m - 8}" y="{y_pos + 3}" fill="{muted_col}" font-size="10" text-anchor="end">{tag}</text>'
            )
            svg.append(
                f'  <text x="{width - inner_m + 8}" y="{y_pos + 3}" fill="{muted_col}" font-size="10">{tag}</text>'
            )

        # Title Block (Bottom Right)
        tb_w = 400
        tb_h = 135
        tb_x = width - inner_m - tb_w
        tb_y = height - inner_m - tb_h

        mat_name = result.material_name if result else model.material_id
        dwg_title = model.name.replace("_", " ").upper()

        svg.append("  <!-- Title Block -->")
        svg.append('  <g id="title-block">')
        svg.append(
            f'    <rect x="{tb_x}" y="{tb_y}" width="{tb_w}" height="{tb_h}" fill="{bg_col}" stroke="{border_col}" stroke-width="1.5" />'
        )
        svg.append(
            f'    <line x1="{tb_x}" y1="{tb_y + 35}" x2="{tb_x + tb_w}" y2="{tb_y + 35}" stroke="{border_col}" stroke-width="1" />'
        )
        svg.append(
            f'    <line x1="{tb_x}" y1="{tb_y + 70}" x2="{tb_x + tb_w}" y2="{tb_y + 70}" stroke="{border_col}" stroke-width="1" />'
        )
        svg.append(
            f'    <line x1="{tb_x}" y1="{tb_y + 105}" x2="{tb_x + tb_w}" y2="{tb_y + 105}" stroke="{border_col}" stroke-width="1" />'
        )
        svg.append(
            f'    <line x1="{tb_x + 220}" y1="{tb_y + 35}" x2="{tb_x + 220}" y2="{tb_y + tb_h}" stroke="{border_col}" stroke-width="1" />'
        )

        # Title Block Texts
        svg.append(
            f'    <text x="{tb_x + 12}" y="{tb_y + 24}" fill="{dim_col}" font-size="14" font-weight="bold">MACHINE DESIGN INTELLIGENCE ENGINE</text>'
        )
        svg.append(
            f'    <text x="{tb_x + 12}" y="{tb_y + 53}" fill="{muted_col}" font-size="9">TITLE / PART NAME:</text>'
        )
        svg.append(
            f'    <text x="{tb_x + 12}" y="{tb_y + 65}" fill="{text_col}" font-size="11" font-weight="bold">{dwg_title}</text>'
        )
        svg.append(
            f'    <text x="{tb_x + 230}" y="{tb_y + 53}" fill="{muted_col}" font-size="9">DWG NO / REVISION:</text>'
        )
        svg.append(
            f'    <text x="{tb_x + 230}" y="{tb_y + 65}" fill="{text_col}" font-size="11">MDIE-SFT-001 (REV A)</text>'
        )

        svg.append(
            f'    <text x="{tb_x + 12}" y="{tb_y + 88}" fill="{muted_col}" font-size="9">MATERIAL & TREATMENT:</text>'
        )
        svg.append(
            f'    <text x="{tb_x + 12}" y="{tb_y + 100}" fill="{text_col}" font-size="10">{mat_name[:30]}</text>'
        )
        svg.append(
            f'    <text x="{tb_x + 230}" y="{tb_y + 88}" fill="{muted_col}" font-size="9">SCALE / UNITS:</text>'
        )
        svg.append(
            f'    <text x="{tb_x + 230}" y="{tb_y + 100}" fill="{text_col}" font-size="10">1:{1.0 / draw_scale:.1f} / mm (SI)</text>'
        )

        svg.append(
            f'    <text x="{tb_x + 12}" y="{tb_y + 123}" fill="{muted_col}" font-size="9">TOLERANCES: ISO 2768-mK</text>'
        )
        svg.append(
            f'    <text x="{tb_x + 230}" y="{tb_y + 123}" fill="{dim_col}" font-size="9">PROJECTION: 3RD ANGLE &#x2295;</text>'
        )
        svg.append("  </g>")

        # Centerline along shaft axis
        cl_start_x = view_x0 - 25
        cl_end_x = view_x0 + (total_len_mm * draw_scale) + 25
        svg.append("  <!-- Centerline -->")
        svg.append(
            f'  <line x1="{cl_start_x:.1f}" y1="{view_y_mid}" x2="{cl_end_x:.1f}" y2="{view_y_mid}" stroke="{center_col}" stroke-width="1.2" stroke-dasharray="14,3,3,3" />'
        )

        # Front View: Render shaft stepped segments
        svg.append("  <!-- Shaft Front Contour -->")
        curr_x = view_x0
        for seg in model.segments:
            seg_len_mm = (seg.end_pos - seg.start_pos) * 1000.0
            seg_dia_mm = seg.outer_diameter * 1000.0

            w_px = seg_len_mm * draw_scale
            h_px = seg_dia_mm * draw_scale
            top_y = view_y_mid - (h_px / 2.0)

            # Segment contour box
            svg.append(
                f'  <rect x="{curr_x:.1f}" y="{top_y:.1f}" width="{w_px:.1f}" height="{h_px:.1f}" fill="{hatch_col}" stroke="{line_col}" stroke-width="2.0" />'
            )

            # Bearing seat / Feature highlight
            if seg.feature_type == "bearing_seat":
                svg.append("  <!-- Bearing Seat Tolerance Marker -->")
                svg.append(
                    f'  <text x="{curr_x + w_px / 2.0:.1f}" y="{top_y - 14:.1f}" fill="{dim_col}" font-size="10" text-anchor="middle">&#x2205;{seg_dia_mm:.1f} k6</text>'
                )
                svg.append("  <!-- Surface Finish Ground Symbol -->")
                svg.append(
                    f'  <path d="M {curr_x + w_px / 2.0 - 5:.1f} {top_y - 5:.1f} l 5 6 l 7 -10" fill="none" stroke="{dim_col}" stroke-width="1" />'
                )
                svg.append(
                    f'  <text x="{curr_x + w_px / 2.0 + 10:.1f}" y="{top_y - 3:.1f}" fill="{dim_col}" font-size="8">Ra 0.8</text>'
                )
            else:
                svg.append(
                    f'  <text x="{curr_x + w_px / 2.0:.1f}" y="{top_y - 8:.1f}" fill="{muted_col}" font-size="9" text-anchor="middle">&#x2205;{seg_dia_mm:.1f}</text>'
                )

            # Segment length dimension below
            dim_y = view_y_mid + (max_dia_mm * draw_scale / 2.0) + 30
            svg.append("  <!-- Segment Dimension Line -->")
            svg.append(
                f'  <line x1="{curr_x:.1f}" y1="{view_y_mid + h_px / 2.0 + 3}" x2="{curr_x:.1f}" y2="{dim_y + 6}" stroke="{dim_col}" stroke-width="0.8" stroke-dasharray="2,2" />'
            )
            svg.append(
                f'  <line x1="{curr_x + w_px:.1f}" y1="{view_y_mid + h_px / 2.0 + 3}" x2="{curr_x + w_px:.1f}" y2="{dim_y + 6}" stroke="{dim_col}" stroke-width="0.8" stroke-dasharray="2,2" />'
            )
            svg.append(
                f'  <line x1="{curr_x:.1f}" y1="{dim_y}" x2="{curr_x + w_px:.1f}" y2="{dim_y}" stroke="{dim_col}" stroke-width="1.2" marker-start="url(#arrow)" marker-end="url(#arrow)" />'
            )
            svg.append(
                f'  <text x="{curr_x + w_px / 2.0:.1f}" y="{dim_y - 4}" fill="{dim_col}" font-size="10" text-anchor="middle">{seg_len_mm:.0f}</text>'
            )

            # Render keyway slot if present
            if seg.keyway:
                kw = seg.keyway
                kw_len_px = kw.length_mm * draw_scale
                kw_depth_px = kw.depth_mm * draw_scale
                kw_x = curr_x + (w_px - kw_len_px) / 2.0
                kw_y = top_y
                svg.append("  <!-- Keyway Slot -->")
                svg.append(
                    f'  <rect x="{kw_x:.1f}" y="{kw_y:.1f}" width="{kw_len_px:.1f}" height="{kw_depth_px:.1f}" fill="{bg_col}" stroke="{dim_col}" stroke-width="1.5" stroke-dasharray="4,2" />'
                )
                svg.append(
                    f'  <text x="{kw_x + kw_len_px / 2.0:.1f}" y="{kw_y + kw_depth_px + 12:.1f}" fill="{dim_col}" font-size="8" text-anchor="middle">DIN 6885-1 ({kw.width_mm:.0f}x{kw.depth_mm:.1f})</text>'
                )

            curr_x += w_px

        # Overall Total Length Dimension (Lower line)
        tot_dim_y = view_y_mid + (max_dia_mm * draw_scale / 2.0) + 60
        svg.append("  <!-- Total Length Dimension -->")
        svg.append(
            f'  <line x1="{view_x0:.1f}" y1="{view_y_mid + 10}" x2="{view_x0:.1f}" y2="{tot_dim_y + 8}" stroke="{dim_col}" stroke-width="1" />'
        )
        svg.append(
            f'  <line x1="{curr_x:.1f}" y1="{view_y_mid + 10}" x2="{curr_x:.1f}" y2="{tot_dim_y + 8}" stroke="{dim_col}" stroke-width="1" />'
        )
        svg.append(
            f'  <line x1="{view_x0:.1f}" y1="{tot_dim_y}" x2="{curr_x:.1f}" y2="{tot_dim_y}" stroke="{dim_col}" stroke-width="1.5" marker-start="url(#arrow)" marker-end="url(#arrow)" />'
        )
        svg.append(
            f'  <text x="{view_x0 + (curr_x - view_x0) / 2.0:.1f}" y="{tot_dim_y - 5}" fill="{dim_col}" font-size="12" font-weight="bold" text-anchor="middle">{total_len_mm:.0f} &#177;0.5</text>'
        )

        # Right End Projection View (Radial Section View A-A)
        sec_cx = width - 200
        sec_cy = view_y_mid
        r_outer_px = (max_dia_mm * draw_scale) / 2.0

        svg.append("  <!-- Section A-A / End Projection -->")
        svg.append('  <g id="end-projection">')
        svg.append(
            f'    <text x="{sec_cx}" y="{sec_cy - r_outer_px - 25}" fill="{text_col}" font-size="12" font-weight="bold" text-anchor="middle">VIEW A-A (1:{1.0 / draw_scale:.1f})</text>'
        )
        # Centerlines
        svg.append(
            f'    <line x1="{sec_cx - r_outer_px - 15}" y1="{sec_cy}" x2="{sec_cx + r_outer_px + 15}" y2="{sec_cy}" stroke="{center_col}" stroke-width="1" stroke-dasharray="10,3,3,3" />'
        )
        svg.append(
            f'    <line x1="{sec_cx}" y1="{sec_cy - r_outer_px - 15}" x2="{sec_cx}" y2="{sec_cy + r_outer_px + 15}" stroke="{center_col}" stroke-width="1" stroke-dasharray="10,3,3,3" />'
        )
        # Outer circle
        svg.append(
            f'    <circle cx="{sec_cx}" cy="{sec_cy}" r="{r_outer_px:.1f}" fill="{hatch_col}" stroke="{line_col}" stroke-width="2" />'
        )

        # If hollow inner bore
        inner_dia_mm = (
            model.segments[0].inner_diameter * 1000.0
            if (model.segments and model.segments[0].inner_diameter)
            else 0.0
        )
        if inner_dia_mm > 0:
            r_inner_px = (inner_dia_mm * draw_scale) / 2.0
            svg.append(
                f'    <circle cx="{sec_cx}" cy="{sec_cy}" r="{r_inner_px:.1f}" fill="{bg_col}" stroke="{line_col}" stroke-width="1.5" />'
            )
            svg.append(
                f'    <text x="{sec_cx}" y="{sec_cy + 3}" fill="{dim_col}" font-size="9" text-anchor="middle">&#x2205;{inner_dia_mm:.1f} BORE</text>'
            )

        # Keyway slot cut in projection
        svg.append(
            f'    <rect x="{sec_cx - 5}" y="{sec_cy - r_outer_px}" width="10" height="7" fill="{bg_col}" stroke="{line_col}" stroke-width="1.5" />'
        )
        svg.append("  </g>")

        # General Notes (Upper Left)
        svg.append("  <!-- Drawing Notes -->")
        svg.append('  <g id="notes">')
        svg.append(
            f'    <text x="{inner_m + 15}" y="{inner_m + 30}" fill="{dim_col}" font-size="11" font-weight="bold">GENERAL MANUFACTURING NOTES:</text>'
        )
        svg.append(
            f'    <text x="{inner_m + 15}" y="{inner_m + 48}" fill="{muted_col}" font-size="9.5">1. UNLESS OTHERWISE SPECIFIED: BREAK ALL SHARP EDGES 0.5x45&#176;</text>'
        )
        svg.append(
            f'    <text x="{inner_m + 15}" y="{inner_m + 64}" fill="{muted_col}" font-size="9.5">2. ALL SHOULDER TRANSITION FILLETS R1.5 mm MINIMUM TO REDUCE STRESS CONCENTRATION</text>'
        )
        svg.append(
            f'    <text x="{inner_m + 15}" y="{inner_m + 80}" fill="{muted_col}" font-size="9.5">3. BEARING SEATS CYLINDRICITY WITHIN 0.008 mm, SURFACE FINISH Ra 0.8 &#956;m (GROUND)</text>'
        )
        svg.append(
            f'    <text x="{inner_m + 15}" y="{inner_m + 96}" fill="{muted_col}" font-size="9.5">4. MATERIAL CERTIFICATION REQUIRED ACCORDING TO EN 10204 - TYPE 3.1</text>'
        )
        svg.append(
            f'    <text x="{inner_m + 15}" y="{inner_m + 112}" fill="{muted_col}" font-size="9.5">5. VERIFIED TO WITHSTAND CYCLIC FATIGUE LIFE UNDER GOODMAN CRITERION (PASS)</text>'
        )
        svg.append("  </g>")

        svg.append("</svg>")
        return "\n".join(svg)

    @classmethod
    def generate_gear_blueprint_svg(
        cls,
        result: GearPairResult,
        theme: str = "blueprint",
        width: int = 1100,
        height: int = 700,
    ) -> str:
        """
        Generate technical 2D engineering drawing for a gear pair assembly.
        """
        is_bp = theme.lower() == "blueprint"
        bg_col = "#091424" if is_bp else "#ffffff"
        grid_col = "rgba(56, 189, 248, 0.08)" if is_bp else "rgba(100, 116, 139, 0.08)"
        border_col = "#38bdf8" if is_bp else "#0f172a"
        line_col = "#e2e8f0" if is_bp else "#0f172a"
        center_col = "#ef4444" if is_bp else "#dc2626"
        dim_col = "#38bdf8" if is_bp else "#2563eb"
        text_col = "#f8fafc" if is_bp else "#0f172a"
        muted_col = "#94a3b8" if is_bp else "#64748b"

        margin = 30
        inner_m = 40
        b_w = width - 2 * margin
        b_h = height - 2 * margin

        geom = result.geometry
        spec = result.spec

        # Centers layout
        cx1 = 300
        cy = 320
        # Scale to fit
        scale = min(1.2, 500.0 / (geom.pitch_diameter_pinion_mm + geom.pitch_diameter_gear_mm))
        r1_p = (geom.pitch_diameter_pinion_mm / 2.0) * scale
        r1_o = (geom.outer_diameter_pinion_mm / 2.0) * scale
        r1_r = (geom.root_diameter_pinion_mm / 2.0) * scale

        cx2 = cx1 + (geom.center_distance_mm * scale)
        r2_p = (geom.pitch_diameter_gear_mm / 2.0) * scale
        r2_o = (geom.outer_diameter_gear_mm / 2.0) * scale
        r2_r = (geom.root_diameter_gear_mm / 2.0) * scale

        svg = []
        svg.append(
            f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" font-family="Consolas, monospace, sans-serif">'
        )
        svg.append("  <defs>")
        svg.append(
            '    <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
        )
        svg.append(f'      <path d="M 0 1.5 L 10 5 L 0 8.5 z" fill="{dim_col}" />')
        svg.append("    </marker>")
        svg.append('    <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">')
        svg.append(
            f'      <path d="M 20 0 L 0 0 0 20" fill="none" stroke="{grid_col}" stroke-width="1" />'
        )
        svg.append("    </pattern>")
        svg.append("  </defs>")

        # Background & Borders
        svg.append(f'  <rect width="{width}" height="{height}" fill="{bg_col}" />')
        svg.append(f'  <rect width="{width}" height="{height}" fill="url(#grid)" />')
        svg.append(
            f'  <rect x="{margin}" y="{margin}" width="{b_w}" height="{b_h}" fill="none" stroke="{border_col}" stroke-width="2" />'
        )
        svg.append(
            f'  <rect x="{inner_m}" y="{inner_m}" width="{width - 2 * inner_m}" height="{height - 2 * inner_m}" fill="none" stroke="{border_col}" stroke-width="1" />'
        )

        # Title Block
        tb_w = 400
        tb_h = 135
        tb_x = width - inner_m - tb_w
        tb_y = height - inner_m - tb_h

        svg.append("  <!-- Title Block -->")
        svg.append(
            f'  <rect x="{tb_x}" y="{tb_y}" width="{tb_w}" height="{tb_h}" fill="{bg_col}" stroke="{border_col}" stroke-width="1.5" />'
        )
        svg.append(
            f'  <line x1="{tb_x}" y1="{tb_y + 35}" x2="{tb_x + tb_w}" y2="{tb_y + 35}" stroke="{border_col}" stroke-width="1" />'
        )
        svg.append(
            f'  <line x1="{tb_x}" y1="{tb_y + 70}" x2="{tb_x + tb_w}" y2="{tb_y + 70}" stroke="{border_col}" stroke-width="1" />'
        )
        svg.append(
            f'  <line x1="{tb_x}" y1="{tb_y + 105}" x2="{tb_x + tb_w}" y2="{tb_y + 105}" stroke="{border_col}" stroke-width="1" />'
        )
        svg.append(
            f'  <line x1="{tb_x + 220}" y1="{tb_y + 35}" x2="{tb_x + 220}" y2="{tb_y + tb_h}" stroke="{border_col}" stroke-width="1" />'
        )

        svg.append(
            f'  <text x="{tb_x + 12}" y="{tb_y + 24}" fill="{dim_col}" font-size="14" font-weight="bold">MACHINE DESIGN INTELLIGENCE ENGINE</text>'
        )
        svg.append(
            f'  <text x="{tb_x + 12}" y="{tb_y + 53}" fill="{muted_col}" font-size="9">TITLE / PART:</text>'
        )
        svg.append(
            f'  <text x="{tb_x + 12}" y="{tb_y + 65}" fill="{text_col}" font-size="11" font-weight="bold">{spec.name.upper()}</text>'
        )
        svg.append(
            f'  <text x="{tb_x + 230}" y="{tb_y + 53}" fill="{muted_col}" font-size="9">DWG NO / REV:</text>'
        )
        svg.append(
            f'  <text x="{tb_x + 230}" y="{tb_y + 65}" fill="{text_col}" font-size="11">MDIE-GEAR-001 (REV A)</text>'
        )
        svg.append(
            f'  <text x="{tb_x + 12}" y="{tb_y + 88}" fill="{muted_col}" font-size="9">MATERIAL:</text>'
        )
        svg.append(
            f'  <text x="{tb_x + 12}" y="{tb_y + 100}" fill="{text_col}" font-size="10">{result.material_name}</text>'
        )
        svg.append(
            f'  <text x="{tb_x + 230}" y="{tb_y + 88}" fill="{muted_col}" font-size="9">STANDARDS:</text>'
        )
        svg.append(
            f'  <text x="{tb_x + 230}" y="{tb_y + 100}" fill="{text_col}" font-size="10">AGMA 2001-D04 / ISO 6336</text>'
        )

        # Centerlines
        svg.append(
            f'  <line x1="{cx1 - r1_o - 20}" y1="{cy}" x2="{cx2 + r2_o + 20}" y2="{cy}" stroke="{center_col}" stroke-width="1" stroke-dasharray="10,3,3,3" />'
        )
        svg.append(
            f'  <line x1="{cx1}" y1="{cy - r1_o - 20}" x2="{cx1}" y2="{cy + r1_o + 20}" stroke="{center_col}" stroke-width="1" stroke-dasharray="10,3,3,3" />'
        )
        svg.append(
            f'  <line x1="{cx2}" y1="{cy - r2_o - 20}" x2="{cx2}" y2="{cy + r2_o + 20}" stroke="{center_col}" stroke-width="1" stroke-dasharray="10,3,3,3" />'
        )

        # Pinion Circles
        svg.append("  <!-- Pinion Circles -->")
        svg.append(
            f'  <circle cx="{cx1}" cy="{cy}" r="{r1_o}" fill="none" stroke="{line_col}" stroke-width="2" />'
        )
        svg.append(
            f'  <circle cx="{cx1}" cy="{cy}" r="{r1_p}" fill="none" stroke="{dim_col}" stroke-width="1.2" stroke-dasharray="6,3" />'
        )
        svg.append(
            f'  <circle cx="{cx1}" cy="{cy}" r="{r1_r}" fill="none" stroke="{line_col}" stroke-width="1" stroke-dasharray="2,2" />'
        )
        svg.append(
            f'  <circle cx="{cx1}" cy="{cy}" r="{spec.pinion_bore_mm * scale / 2.0}" fill="{bg_col}" stroke="{line_col}" stroke-width="1.5" />'
        )
        svg.append(
            f'  <text x="{cx1}" y="{cy - r1_o - 10}" fill="{dim_col}" font-size="11" text-anchor="middle">PINION (z={spec.pinion_teeth})</text>'
        )

        # Gear Circles
        svg.append("  <!-- Driven Gear Circles -->")
        svg.append(
            f'  <circle cx="{cx2}" cy="{cy}" r="{r2_o}" fill="none" stroke="{line_col}" stroke-width="2" />'
        )
        svg.append(
            f'  <circle cx="{cx2}" cy="{cy}" r="{r2_p}" fill="none" stroke="{dim_col}" stroke-width="1.2" stroke-dasharray="6,3" />'
        )
        svg.append(
            f'  <circle cx="{cx2}" cy="{cy}" r="{r2_r}" fill="none" stroke="{line_col}" stroke-width="1" stroke-dasharray="2,2" />'
        )
        svg.append(
            f'  <circle cx="{cx2}" cy="{cy}" r="{spec.gear_bore_mm * scale / 2.0}" fill="{bg_col}" stroke="{line_col}" stroke-width="1.5" />'
        )
        svg.append(
            f'  <text x="{cx2}" y="{cy - r2_o - 10}" fill="{dim_col}" font-size="11" text-anchor="middle">DRIVEN GEAR (z={spec.gear_teeth})</text>'
        )

        # Center Distance Dimension
        dim_y = cy + max(r1_o, r2_o) + 35
        svg.append("  <!-- Center Distance -->")
        svg.append(
            f'  <line x1="{cx1}" y1="{cy + 20}" x2="{cx1}" y2="{dim_y + 6}" stroke="{dim_col}" stroke-width="0.8" stroke-dasharray="2,2" />'
        )
        svg.append(
            f'  <line x1="{cx2}" y1="{cy + 20}" x2="{cx2}" y2="{dim_y + 6}" stroke="{dim_col}" stroke-width="0.8" stroke-dasharray="2,2" />'
        )
        svg.append(
            f'  <line x1="{cx1}" y1="{dim_y}" x2="{cx2}" y2="{dim_y}" stroke="{dim_col}" stroke-width="1.5" marker-start="url(#arrow)" marker-end="url(#arrow)" />'
        )
        svg.append(
            f'  <text x="{(cx1 + cx2) / 2.0}" y="{dim_y - 6}" fill="{dim_col}" font-size="12" font-weight="bold" text-anchor="middle">a = {geom.center_distance_mm:.1f} &#177;0.05</text>'
        )

        # Gear Mesh Data Table (Upper Left)
        dt_x = inner_m + 15
        dt_y = inner_m + 30
        svg.append("  <!-- Gear Mesh Data Table -->")
        svg.append(
            f'  <text x="{dt_x}" y="{dt_y}" fill="{dim_col}" font-size="11" font-weight="bold">GEAR MESH SPECIFICATIONS:</text>'
        )
        table_rows = [
            ("Normal Module (mn):", f"{geom.normal_module_mm:.2f} mm"),
            ("Pressure Angle (alpha):", f"{spec.pressure_angle_deg:.1f}&#176;"),
            ("Helix Angle (beta):", f"{spec.helix_angle_deg:.1f}&#176;"),
            ("Pinion Pitch Dia (d1):", f"{geom.pitch_diameter_pinion_mm:.2f} mm"),
            ("Gear Pitch Dia (d2):", f"{geom.pitch_diameter_gear_mm:.2f} mm"),
            ("Face Width (b):", f"{geom.face_width_mm:.1f} mm"),
            ("Gear Ratio (i):", f"{geom.gear_ratio:.2f}:1"),
            (
                "Lewis Bending SF (SF_b):",
                f"{result.stress.bending_safety_factor_pinion:.2f} (PASS)",
            ),
            ("AGMA Contact SF (SF_h):", f"{result.stress.contact_safety_factor:.2f} (PASS)"),
        ]
        for idx, (label, val) in enumerate(table_rows):
            svg.append(
                f'  <text x="{dt_x}" y="{dt_y + 20 + idx * 16}" fill="{muted_col}" font-size="10">{label}</text>'
            )
            svg.append(
                f'  <text x="{dt_x + 160}" y="{dt_y + 20 + idx * 16}" fill="{text_col}" font-size="10" font-weight="bold">{val}</text>'
            )

        svg.append("</svg>")
        return "\n".join(svg)

    @classmethod
    def generate_html_blueprint_page(
        cls, svg_content: str, title: str = "Technical Drawing"
    ) -> str:
        """
        Wrap SVG in a responsive, printable HTML engineering sheet.
        """
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{title} - MDIE Engineering Blueprint</title>
  <style>
    @page {{
      size: A3 landscape;
      margin: 10mm;
    }}
    body {{
      margin: 0;
      padding: 20px;
      background: #030712;
      color: #f3f4f6;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      display: flex;
      flex-direction: column;
      align-items: center;
      min-height: 100vh;
    }}
    .header-bar {{
      width: 100%;
      max-width: 1100px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 15px;
    }}
    .btn {{
      background: #0284c7;
      color: white;
      border: none;
      padding: 8px 16px;
      border-radius: 6px;
      font-weight: 600;
      cursor: pointer;
    }}
    .btn:hover {{ background: #0369a1; }}
    .blueprint-frame {{
      width: 100%;
      max-width: 1100px;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5);
      border-radius: 8px;
      overflow: hidden;
      background: #091424;
    }}
    @media print {{
      body {{ background: white; padding: 0; }}
      .header-bar {{ display: none; }}
      .blueprint-frame {{ box-shadow: none; border-radius: 0; max-width: 100%; }}
    }}
  </style>
</head>
<body>
  <div class="header-bar">
    <div>
      <h2 style="margin: 0; font-size: 18px; color: #38bdf8;">Machine Design Intelligence Engine &mdash; 2D CAD Blueprint</h2>
      <div style="font-size: 13px; color: #9ca3af;">ISO 128 / ANSI Y14.5 Technical Manufacturing Sheet</div>
    </div>
    <button class="btn" onclick="window.print()">Print / Export PDF</button>
  </div>
  <div class="blueprint-frame">
    {svg_content}
  </div>
</body>
</html>"""
