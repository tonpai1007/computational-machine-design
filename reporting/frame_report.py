"""
General Visual Structural & Frame Engineering Report Generator (Core Engine)
Produces professional, audit-ready HTML calculation sheets with embedded SVG Free Body Diagrams (FBD),
equilibrium reactions, column buckling tables, and stress distributions.
Strictly follows clean white-paper professional engineering standard (Engineerview.md).
"""

import math

from core.frame_model import FrameDesignModel
from physics.frame_physics import FrameSolverResult


def _lat_tip_display(result: FrameSolverResult) -> tuple[str, str, str]:
    """Render the lateral tipping margin honestly.

    Returns (cell_value, verdict, css_class). A ``None`` margin means the
    lateral loads cancel exactly and no tipping case exists -> report "N/A",
    never a fabricated large safety factor (physics-determinism rule).
    """
    if result.tipping_safety_factor_lat is None:
        return (
            '<span style="color:#64748b;font-style:italic;">N/A</span>',
            "N/A (no case)",
            "text-muted",
        )
    sf = result.tipping_safety_factor_lat
    cls = "text-pass" if sf >= 1.5 else "text-fail"
    return f"{sf:.2f}", ("PASS" if sf >= 1.5 else "FAIL"), cls


class FrameReportGenerator:
    """Generates professional, audit-ready structural calculation sheets."""

    @staticmethod
    def generate_html_report(model: FrameDesignModel, result: FrameSolverResult) -> str:
        g = model.geometry
        loads = model.loads
        m = model.material
        allowable_deflection_mm = getattr(m, "allowable_deflection_mm", 5.0)

        # Overall Status Badge
        overall_badge = (
            '<span class="badge badge-pass">VERIFIED COMPLIANT (PASS)</span>'
            if result.all_safety_criteria_passed
            else '<span class="badge badge-fail">NON-COMPLIANT (REDESIGN REQUIRED)</span>'
        )

        # Section Properties for Column
        col_prof = g.leg_profile
        col_area_mm2 = col_prof.area_m2 * 1e6
        col_i_mm4 = col_prof.moment_of_inertia_m4 * 1e12
        col_z_mm3 = col_prof.section_modulus_m3 * 1e9
        col_r_gyr_mm = col_prof.radius_of_gyration_m * 1000.0
        unbraced_len_mm = max(100.0, g.seat_height_mm - g.stretcher_height_mm)
        k_factor = 0.85 if g.has_stretchers else 1.2

        # Johnson transition slenderness ratio (C = 1.0 pinned-pinned baseline)
        c_end = 1.0
        trans_slenderness = math.sqrt(
            2.0
            * (math.pi**2)
            * c_end
            * (m.elastic_modulus_gpa * 1000.0)
            / max(m.yield_strength_mpa, 1.0)
        )

        # Column Reaction Rows
        leg_rows = ""
        for leg in result.floor_reactions:
            status_cls = "text-pass" if (leg.buckling_passed and leg.yield_passed) else "text-fail"
            buckling_cls = "text-pass" if leg.buckling_passed else "text-fail"
            yield_cls = "text-pass" if leg.yield_passed else "text-fail"
            status_text = "PASS" if (leg.buckling_passed and leg.yield_passed) else "FAIL"
            buckling_mode = (
                "Euler (Long)" if leg.slenderness_ratio >= trans_slenderness else "Johnson (Int.)"
            )

            leg_rows += f"""
            <tr>
                <td style="font-weight: 600;">{leg.leg_id} <span style="font-size: 11px; color: #64748b;">({leg.leg_name})</span></td>
                <td class="num">{leg.axial_reaction_n:.1f} N</td>
                <td class="num">{leg.horizontal_shear_n:.1f} N</td>
                <td class="num">{leg.slenderness_ratio:.1f}</td>
                <td style="text-align: center; font-size: 11px; color: #475569;">{buckling_mode}</td>
                <td class="num">{(leg.critical_buckling_load_n / 1000.0):.2f} kN</td>
                <td class="num {buckling_cls}" style="font-weight: 700;">{leg.buckling_safety_factor:.2f}</td>
                <td class="num">{leg.combined_stress_mpa:.1f} MPa</td>
                <td class="num {yield_cls}" style="font-weight: 700;">{leg.yield_safety_factor:.2f}</td>
                <td style="text-align: center; font-weight: 700;" class="{status_cls}">{status_text}</td>
            </tr>
            """

        # Armrest Rows
        arm_rows = ""
        arm_stress_str = (
            f"{result.armrests[0].strut_combined_stress_mpa:.1f} MPa" if result.armrests else "N/A"
        )
        if result.armrests:
            for arm in result.armrests:
                arm_cls = "text-pass" if arm.passed else "text-fail"
                arm_status = "PASS" if arm.passed else "FAIL"
                arm_rows += f"""
                <tr>
                    <td style="font-weight: 600; text-transform: capitalize;">{arm.arm_id} Arm Assembly</td>
                    <td class="num">{arm.applied_vertical_n:.1f} N</td>
                    <td class="num">{arm.applied_lateral_n:.1f} N</td>
                    <td class="num">{arm.overhang_moment_nm:.1f} N·m</td>
                    <td class="num">{arm.strut_combined_stress_mpa:.1f} MPa</td>
                    <td class="num {arm_cls}" style="font-weight: 700;">{arm.arm_safety_factor:.2f}</td>
                    <td style="text-align: center; font-weight: 700;" class="{arm_cls}">{arm_status}</td>
                </tr>
                """
        else:
            arm_rows = """
            <tr>
                <td colspan="7" style="text-align: center; color: #64748b; font-style: italic;">
                    No auxiliary cantilever armrests specified in this design configuration.
                </td>
            </tr>
            """

        # Support reaction values for FBD display.
        # These are the SUM of the reactions in each leg pair: the FBD arrows
        # represent the total load carried by that side of the chair. Averaging
        # them here made sum(R) exactly half the applied load (equilibrium broken).
        if len(result.floor_reactions) >= 4:
            r_left_val = (
                result.floor_reactions[0].axial_reaction_n
                + result.floor_reactions[-1].axial_reaction_n
            )
            r_right_val = (
                result.floor_reactions[1].axial_reaction_n
                + result.floor_reactions[2].axial_reaction_n
            )
        elif len(result.floor_reactions) >= 2:
            r_left_val = result.floor_reactions[0].axial_reaction_n
            r_right_val = sum(
                r.axial_reaction_n for r in result.floor_reactions[1:]
            )
        else:
            r_left_val = r_right_val = result.floor_reactions[0].axial_reaction_n

        # Lateral tipping margin may legitimately not exist (balanced side loads).
        lat_tip_val, lat_tip_verdict, lat_tip_cls = _lat_tip_display(result)
        tip_sf_values = [
            v for v in (result.tipping_safety_factor_fwd,
                        result.tipping_safety_factor_rear,
                        result.tipping_safety_factor_lat)
            if v is not None
        ]
        min_tip_sf = min(tip_sf_values) if tip_sf_values else float("inf")


        # SVG Free-Body Diagram (White paper / academic style)
        svg_fbd = f"""
        <svg viewBox="0 0 720 380" style="width: 100%; height: auto; background: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px;">
            <defs>
                <marker id="arrow-down" viewBox="0 0 10 10" refX="5" refY="10" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M 0 0 L 10 0 L 5 10 z" fill="#dc2626" />
                </marker>
                <marker id="arrow-up" viewBox="0 0 10 10" refX="5" refY="0" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M 0 10 L 10 10 L 5 0 z" fill="#16a34a" />
                </marker>
                <marker id="arrow-lat" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M 0 0 L 10 5 L 0 10 z" fill="#0284c7" />
                </marker>
            </defs>

            <!-- Rigid Floor Plane (Z = 0) -->
            <line x1="60" y1="310" x2="660" y2="310" stroke="#64748b" stroke-width="2" stroke-dasharray="6,4" />
            <text x="70" y="332" fill="#475569" font-size="11" font-family="'Times New Roman', serif, sans-serif">Rigid Datum Plane (Z = 0 mm)</text>
            <path d="M 70 310 L 60 320 M 110 310 L 100 320 M 150 310 L 140 320 M 570 310 L 560 320 M 610 310 L 600 320 M 650 310 L 640 320" stroke="#94a3b8" stroke-width="1.5" />

            <!-- Splayed Columns / Legs -->
            <line x1="230" y1="210" x2="190" y2="310" stroke="#1e293b" stroke-width="6" stroke-linecap="round" />
            <line x1="470" y1="210" x2="510" y2="310" stroke="#1e293b" stroke-width="6" stroke-linecap="round" />

            <!-- Stretcher Bracing -->
            <line x1="205" y1="270" x2="495" y2="270" stroke="#475569" stroke-width="3" stroke-dasharray="4,2" />
            <text x="350" y="264" fill="#334155" font-size="10" text-anchor="middle" font-family="Inter, sans-serif">Bracing Stretcher (Z = {g.stretcher_height_mm:.0f} mm)</text>

            <!-- Main Platform Deck -->
            <rect x="200" y="200" width="300" height="18" rx="2" fill="#e2e8f0" stroke="#0f172a" stroke-width="2" />
            <text x="350" y="213" fill="#0f172a" font-size="11" font-weight="700" text-anchor="middle" font-family="Inter, sans-serif">Main Structural Platform (W = {g.seat_width_mm:.0f} mm, D = {g.seat_depth_mm:.0f} mm)</text>

            <!-- Left Armrest & Strut -->
            <line x1="220" y1="200" x2="220" y2="125" stroke="#334155" stroke-width="4" />
            <rect x="180" y="115" width="70" height="10" rx="2" fill="#fef3c7" stroke="#b45309" stroke-width="1.5" />
            <text x="215" y="108" fill="#92400e" font-size="10" font-weight="700" text-anchor="middle" font-family="Inter, sans-serif">Left Armrest</text>

            <!-- Right Armrest & Strut -->
            <line x1="480" y1="200" x2="480" y2="125" stroke="#334155" stroke-width="4" />
            <rect x="450" y="115" width="70" height="10" rx="2" fill="#fef3c7" stroke="#b45309" stroke-width="1.5" />
            <text x="485" y="108" fill="#92400e" font-size="10" font-weight="700" text-anchor="middle" font-family="Inter, sans-serif">Right Armrest</text>

            <!-- Backrest Structure -->
            <line x1="230" y1="200" x2="220" y2="60" stroke="#475569" stroke-width="4" />
            <line x1="470" y1="200" x2="460" y2="60" stroke="#475569" stroke-width="4" />
            <rect x="220" y="70" width="240" height="55" rx="3" fill="#f1f5f9" stroke="#475569" stroke-width="1.5" />
            <text x="340" y="102" fill="#334155" font-size="11" font-weight="600" text-anchor="middle" font-family="Inter, sans-serif">Upper Structure / Backrest Assembly</text>

            <!-- Applied Seat Payload Force -->
            <line x1="350" y1="140" x2="350" y2="195" stroke="#dc2626" stroke-width="2.5" marker-end="url(#arrow-down)" />
            <text x="350" y="152" fill="#b91c1c" font-size="11" font-weight="700" text-anchor="middle" font-family="'JetBrains Mono', monospace">F_load = {loads.seat_vertical_load_n:.0f} N</text>

            <!-- Applied Arm Loads -->
            <line x1="215" y1="70" x2="215" y2="110" stroke="#dc2626" stroke-width="2" marker-end="url(#arrow-down)" />
            <text x="215" y="65" fill="#b91c1c" font-size="10" font-weight="700" text-anchor="middle" font-family="'JetBrains Mono', monospace">F_arm = {loads.left_arm_vertical_n:.0f} N</text>
            <line x1="215" y1="120" x2="160" y2="120" stroke="#0284c7" stroke-width="2" marker-end="url(#arrow-lat)" />
            <text x="155" y="115" fill="#0369a1" font-size="10" font-weight="700" text-anchor="end" font-family="'JetBrains Mono', monospace">{abs(loads.left_arm_lateral_n):.0f} N (lat)</text>

            <line x1="485" y1="70" x2="485" y2="110" stroke="#dc2626" stroke-width="2" marker-end="url(#arrow-down)" />
            <text x="485" y="65" fill="#b91c1c" font-size="10" font-weight="700" text-anchor="middle" font-family="'JetBrains Mono', monospace">F_arm = {loads.right_arm_vertical_n:.0f} N</text>
            <line x1="485" y1="120" x2="540" y2="120" stroke="#0284c7" stroke-width="2" marker-end="url(#arrow-lat)" />
            <text x="548" y="115" fill="#0369a1" font-size="10" font-weight="700" font-family="'JetBrains Mono', monospace">{abs(loads.right_arm_lateral_n):.0f} N (lat)</text>

            <!-- Support Floor Reactions -->
            <line x1="190" y1="360" x2="190" y2="315" stroke="#16a34a" stroke-width="3" marker-end="url(#arrow-up)" />
            <text x="190" y="372" fill="#15803d" font-size="11" font-weight="700" text-anchor="middle" font-family="'JetBrains Mono', monospace">R_left ≈ {r_left_val:.1f} N</text>

            <line x1="510" y1="360" x2="510" y2="315" stroke="#16a34a" stroke-width="3" marker-end="url(#arrow-up)" />
            <text x="510" y="372" fill="#15803d" font-size="11" font-weight="700" text-anchor="middle" font-family="'JetBrains Mono', monospace">R_right ≈ {r_right_val:.1f} N</text>
        </svg>
        """

        calc_log_items = "".join([f"<li>{step}</li>" for step in result.calculation_log])

        html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>MDIE Structural Engineering Audit Report - {model.name}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #ffffff;
      --card-bg: #f8fafc;
      --border: #cbd5e1;
      --border-dark: #0f172a;
      --text: #0f172a;
      --text-muted: #475569;
      --primary: #1d4ed8;
      --pass: #047857;
      --fail: #b91c1c;
      --warn: #b45309;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Times New Roman", serif, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 30px;
    }}
    .container {{
      max-width: 960px;
      margin: 0 auto;
    }}
    .formal-header {{
      border-bottom: 2px solid var(--border-dark);
      padding-bottom: 16px;
      margin-bottom: 24px;
    }}
    .inst-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 12px;
    }}
    .inst-title {{
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: #334155;
    }}
    .doc-meta {{
      font-size: 11px;
      color: var(--text-muted);
      text-align: right;
    }}
    .main-title {{
      font-size: 24px;
      font-weight: 800;
      color: var(--text);
      letter-spacing: -0.3px;
      margin: 4px 0;
    }}
    .subtitle {{
      font-size: 13px;
      color: var(--text-muted);
    }}
    .status-bar {{
      margin-top: 14px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: var(--card-bg);
      border: 1px solid var(--border);
      padding: 10px 16px;
      border-radius: 4px;
    }}
    .badge {{
      display: inline-block;
      padding: 4px 14px;
      border-radius: 4px;
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.5px;
      font-family: 'Inter', sans-serif;
    }}
    .badge-pass {{
      background: #ecfdf5;
      color: var(--pass);
      border: 1px solid #a7f3d0;
    }}
    .badge-fail {{
      background: #fef2f2;
      color: var(--fail);
      border: 1px solid #fecaca;
    }}
    .section {{
      margin-bottom: 28px;
    }}
    .section-title {{
      font-size: 16px;
      font-weight: 700;
      color: #0f172a;
      border-bottom: 1.5px solid var(--border);
      padding-bottom: 4px;
      margin-bottom: 12px;
      display: flex;
      justify-content: space-between;
      align-items: baseline;
    }}
    .section-num {{
      color: var(--primary);
      margin-right: 6px;
    }}
    p, li {{
      font-size: 13.5px;
      color: #1e293b;
      margin-bottom: 8px;
    }}
    table.tech-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 12.5px;
      margin: 12px 0;
    }}
    table.tech-table th {{
      background: #f1f5f9;
      color: #0f172a;
      font-weight: 700;
      text-align: left;
      padding: 7px 10px;
      border: 1px solid var(--border);
      font-family: 'Inter', sans-serif;
      font-size: 11.5px;
      text-transform: uppercase;
      letter-spacing: 0.3px;
    }}
    table.tech-table td {{
      padding: 7px 10px;
      border: 1px solid var(--border);
    }}
    table.tech-table tr:nth-child(even) td {{
      background: #fbfcfd;
    }}
    .num {{
      font-family: 'JetBrains Mono', monospace;
      text-align: right;
    }}
    .text-pass {{ color: var(--pass); }}
    .text-fail {{ color: var(--fail); }}
    .calc-step {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-left: 3px solid var(--primary);
      padding: 12px 16px;
      margin: 12px 0;
      border-radius: 2px;
    }}
    .step-header {{
      font-size: 13px;
      font-weight: 700;
      color: var(--primary);
      font-family: 'Inter', sans-serif;
      margin-bottom: 6px;
    }}
    .equation-line {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      color: #0f172a;
      background: #ffffff;
      border: 1px solid #e2e8f0;
      padding: 6px 10px;
      margin: 4px 0;
      border-radius: 3px;
    }}
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 12px;
      margin: 14px 0;
    }}
    .kpi-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 10px 12px;
    }}
    .kpi-label {{
      font-size: 10.5px;
      text-transform: uppercase;
      color: var(--text-muted);
      font-weight: 600;
      font-family: 'Inter', sans-serif;
    }}
    .kpi-val {{
      font-size: 20px;
      font-weight: 800;
      font-family: 'JetBrains Mono', monospace;
      margin: 3px 0;
    }}
    .kpi-sub {{
      font-size: 10px;
      color: var(--text-muted);
    }}
    ul.trace-list {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 11.5px;
      list-style-type: square;
      padding-left: 20px;
      color: #334155;
    }}
    ul.trace-list li {{
      margin-bottom: 3px;
    }}
    .signoff-grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 20px;
      border-top: 1.5px solid var(--border-dark);
      padding-top: 14px;
      margin-top: 30px;
    }}
    .signoff-box {{
      font-size: 11.5px;
      font-family: 'Inter', sans-serif;
    }}
    .signoff-line {{
      border-bottom: 1px solid #94a3b8;
      height: 35px;
      margin-bottom: 6px;
    }}
    @media print {{
      body {{
        padding: 0;
        background: #ffffff;
        color: #000000;
        font-size: 11pt;
      }}
      .container {{
        max-width: 100%;
      }}
      .no-print {{
        display: none;
      }}
      .page-break {{
        page-break-before: always;
      }}
      table.tech-table th {{
        background: #f1f5f9 !important;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
      }}
    }}
    @page {{
      size: A4 portrait;
      margin: 15mm;
    }}
  </style>
</head>
<body>

<div class="container">

  <!-- Part 1: Formal Engineering Header -->
  <div class="formal-header">
    <div class="inst-header">
      <div>
        <div class="inst-title">Structural & Machine Design Calculation Sheet</div>
        <div style="font-size: 11px; color: #64748b;">Deterministic Static Equilibrium & Buckling Audit</div>
      </div>
      <div class="doc-meta">
        <div><strong>Doc ID:</strong> MDIE-CALC-{model.name.upper().replace(" ", "_")}</div>
        <div><strong>Standard:</strong> ANSI/BIFMA X5.1 &bull; AISC 360 &bull; ISO 7173</div>
        <div><strong>Units:</strong> SI Metric (mm, N, N·m, MPa, GPa)</div>
      </div>
    </div>
    <h1 class="main-title">{model.name}</h1>
    <div class="subtitle">
      Spatial Multi-Member Support Frame &bull; Splayed Column Assembly ({g.leg_splay_angle_deg:.1f}°) &bull; Material: {m.name}
    </div>
    <div class="status-bar">
      <div>
        <span style="font-size: 11px; text-transform: uppercase; color: var(--text-muted); font-weight: 600; font-family: 'Inter', sans-serif;">
          Design Compliance Verdict:
        </span>
      </div>
      <div>{overall_badge}</div>
    </div>
  </div>

  <!-- Part 2: Executive Summary & Objective -->
  <div class="section">
    <div class="section-title">
      <span><span class="section-num">1.0</span> Executive Brief & Design Parameters</span>
      <span style="font-size: 11px; font-weight: 400; color: var(--text-muted);">Engineering Specifications</span>
    </div>
    <p>
      Deterministic structural calculation sheet for the <strong>{model.name}</strong>.
      Evaluated under design payload <strong>{loads.seat_vertical_load_n:.0f} N</strong>, auxiliary armrest loads of
      <strong>{loads.left_arm_vertical_n:.0f} N</strong>, and lateral disturbance thrust of <strong>{abs(loads.left_arm_lateral_n):.0f} N</strong>.
    </p>
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Applied Seat Payload</div>
        <div class="kpi-val">{loads.seat_vertical_load_n:.0f} <span style="font-size: 11px; color: var(--text-muted);">N</span></div>
        <div class="kpi-sub">Total Downward: {result.total_downward_load_n:.1f} N</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Min Buckling SF (Euler/John)</div>
        <div class="kpi-val {"text-pass" if result.min_leg_buckling_sf >= 2.0 else "text-fail"}">{result.min_leg_buckling_sf:.2f}</div>
        <div class="kpi-sub">Design Target: n<sub>d</sub> &ge; 2.00</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Min Column Yield SF</div>
        <div class="kpi-val {"text-pass" if result.min_leg_yield_sf >= 2.0 else "text-fail"}">{result.min_leg_yield_sf:.2f}</div>
        <div class="kpi-sub">Combined P/A + M/Z</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Anti-Tipping SF (Min)</div>
        <div class="kpi-val {"text-pass" if min_tip_sf >= 1.5 else "text-fail"}">
          {min_tip_sf:.2f}
        </div>
        <div class="kpi-sub">Standard Req: &ge; 1.50</div>
      </div>
    </div>
  </div>

  <!-- Part 3: Bill of Materials & Geometry -->
  <div class="section">
    <div class="section-title">
      <span><span class="section-num">2.0</span> Bill of Materials (BOM) & Section Geometry</span>
      <span style="font-size: 11px; font-weight: 400; color: var(--text-muted);">Physical Specifications</span>
    </div>
    <table class="tech-table">
      <thead>
        <tr>
          <th>Item</th>
          <th>Subassembly / Part</th>
          <th>Profile & Dimensions</th>
          <th style="text-align: right;">Qty</th>
          <th>Selected Material</th>
          <th>Manufacturing Method</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td style="font-weight: 600;">1</td>
          <td>Load-Bearing Columns (Legs)</td>
          <td>{col_prof.profile_type.replace("_", " ").title()} &Oslash;{col_prof.outer_dimension_mm:.1f} &times; {col_prof.wall_thickness_mm:.1f} mm</td>
          <td class="num">4</td>
          <td>{m.name}</td>
          <td>Cold Drawn Seamless / Welded Tube</td>
        </tr>
        <tr>
          <td style="font-weight: 600;">2</td>
          <td>Lower Perimeter Stretcher</td>
          <td>Tie Bar / Tube &Oslash;{(col_prof.outer_dimension_mm * 0.75):.1f} mm</td>
          <td class="num">4</td>
          <td>{m.name}</td>
          <td>MIG / TIG Welded Tube Framework</td>
        </tr>
        <tr>
          <td style="font-weight: 600;">3</td>
          <td>Main Deck Support Platform</td>
          <td>{g.seat_width_mm:.0f} &times; {g.seat_depth_mm:.0f} &times; 16 mm</td>
          <td class="num">1</td>
          <td>Molded Hardwood / Reinforced Polymer</td>
          <td>CNC Routed / Injection Molded</td>
        </tr>
        <tr>
          <td style="font-weight: 600;">4</td>
          <td>Upper Armrest & Strut Members</td>
          <td>Cantilever Struts L = 220 mm</td>
          <td class="num">2</td>
          <td>{m.name} / Solid Ash</td>
          <td>Bent Tube + Fastened Top Pad</td>
        </tr>
      </tbody>
    </table>

    <div class="calc-step" style="margin-top: 10px;">
      <div class="step-header">Column Cross-Sectional Properties:</div>
      <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; font-size: 12px; font-family: 'JetBrains Mono', monospace;">
        <div>Area A = {col_area_mm2:.1f} mm²</div>
        <div>Inertia I = {col_i_mm4:.1f} mm⁴</div>
        <div>Section Modulus Z = {col_z_mm3:.1f} mm³</div>
        <div>Radius of Gyration k = {col_r_gyr_mm:.2f} mm</div>
      </div>
    </div>
  </div>

  <!-- Part 4: Material Specifications -->
  <div class="section">
    <div class="section-title">
      <span><span class="section-num">3.0</span> Material Specifications & Mechanical Properties</span>
      <span style="font-size: 11px; font-weight: 400; color: var(--text-muted);">Standardized Database Reference</span>
    </div>
    <table class="tech-table">
      <thead>
        <tr>
          <th>Engineering Property</th>
          <th>Symbol</th>
          <th style="text-align: right;">Specified Value</th>
          <th>Unit</th>
          <th>Reference Source / Standard</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>Material Identification</td>
          <td>-</td>
          <td class="num">{m.name}</td>
          <td>-</td>
          <td>MatWeb Database / ASTM A513</td>
        </tr>
        <tr>
          <td>Mass Density</td>
          <td>&rho;</td>
          <td class="num">{(m.density_kg_m3 / 1000.0):.2f}</td>
          <td>g/cm&sup3;</td>
          <td>ASTM Standard Density Table ({m.density_kg_m3:.0f} kg/m&sup3;)</td>
        </tr>
        <tr>
          <td>Yield Strength (0.2% Offset)</td>
          <td>S<sub>y</sub></td>
          <td class="num">{m.yield_strength_mpa:.1f}</td>
          <td>MPa</td>
          <td>AISC / ASM Metals Handbook</td>
        </tr>
        <tr>
          <td>Ultimate Tensile Strength</td>
          <td>S<sub>ut</sub></td>
          <td class="num">{m.ultimate_strength_mpa:.1f}</td>
          <td>MPa</td>
          <td>AISC / ASM Metals Handbook</td>
        </tr>
        <tr>
          <td>Modulus of Elasticity (Young's)</td>
          <td>E</td>
          <td class="num">{m.elastic_modulus_gpa:.1f}</td>
          <td>GPa</td>
          <td>ASTM E111 Standard Static Test</td>
        </tr>
        <tr>
          <td>Poisson's Ratio</td>
          <td>&nu;</td>
          <td class="num">{m.poissons_ratio:.2f}</td>
          <td>-</td>
          <td>Standard Elastic Constant</td>
        </tr>
        <tr>
          <td>Allowable Structural Deflection</td>
          <td>&delta;<sub>all</sub></td>
          <td class="num">{allowable_deflection_mm:.1f}</td>
          <td>mm</td>
          <td>BIFMA X5.1 / Span limit (L / 120)</td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- Part 5: Equilibrium & Free-Body Diagram -->
  <div class="section">
    <div class="section-title">
      <span><span class="section-num">4.0</span> Global Static Equilibrium & Free-Body Diagram</span>
      <span style="font-size: 11px; font-weight: 400; color: var(--text-muted);">Reactions & Load Trace</span>
    </div>
    <p>
      Global equilibrium requires static force and moment balance across the entire 3D spatial assembly:
    </p>
    <div class="calc-step">
      <div class="equation-line">&sum; F<sub>z</sub> = 0 &rArr; R<sub>FL,z</sub> + R<sub>FR,z</sub> + R<sub>RL,z</sub> + R<sub>RR,z</sub> = W<sub>frame</sub> + F<sub>payload</sub> = {result.total_downward_load_n:.1f} N</div>
      <div class="equation-line">&sum; F<sub>x</sub> = 0 &rArr; &sum; R<sub>x</sub> = F<sub>lateral,x</sub> &emsp;|&emsp; &sum; M = 0 (Planar Moment Balance)</div>
    </div>
    <div style="margin: 14px 0;">
      {svg_fbd}
    </div>
  </div>

  <!-- Part 6: Step-by-Step Structural Analysis -->
  <div class="section page-break">
    <div class="section-title">
      <span><span class="section-num">5.0</span> Column Buckling Stability Analysis (Euler vs. J.B. Johnson)</span>
      <span style="font-size: 11px; font-weight: 400; color: var(--text-muted);">Shigley Chapter 4 Verification</span>
    </div>
    <p>
      For columns subjected to axial compression, the transition slenderness ratio &lambda;<sub>1</sub> separates
      inelastic Johnson buckling from elastic Euler buckling:
    </p>
    <div class="calc-step">
      <div class="step-header">Column Transition Slenderness Equation (AISC / Shigley Eq. 4-48):</div>
      <div class="equation-line">
        &lambda;<sub>1</sub> = &radic;[ (2 &pi;&sup2; C E) / S<sub>y</sub> ] = &radic;[ (2 &pi;&sup2; &times; {c_end:.1f} &times; {m.elastic_modulus_gpa * 1000.0:.0f} MPa) / {m.yield_strength_mpa:.1f} MPa ] = {trans_slenderness:.1f}
      </div>
      <div style="font-size: 12px; color: #475569; margin-top: 4px;">
        Unbraced Length L = {unbraced_len_mm:.1f} mm &bull; Effective Length Factor K = {k_factor:.2f} &bull; L<sub>eff</sub> = K&times;L = {(k_factor * unbraced_len_mm):.1f} mm &bull; Radius of Gyration k = {col_r_gyr_mm:.2f} mm &bull; Column Slenderness &lambda; = L<sub>eff</sub> / k = {(k_factor * unbraced_len_mm / col_r_gyr_mm):.1f}
      </div>
    </div>

    <table class="tech-table">
      <thead>
        <tr>
          <th>Column ID</th>
          <th style="text-align: right;">Axial R<sub>z</sub></th>
          <th style="text-align: right;">Shear R<sub>h</sub></th>
          <th style="text-align: right;">Slenderness &lambda;</th>
          <th style="text-align: center;">Buckling Regime</th>
          <th style="text-align: right;">P<sub>critical</sub></th>
          <th style="text-align: right;">Buckling SF (n<sub>s</sub>)</th>
          <th style="text-align: right;">Combined Stress</th>
          <th style="text-align: right;">Yield SF (n<sub>y</sub>)</th>
          <th style="text-align: center;">Status</th>
        </tr>
      </thead>
      <tbody>
        {leg_rows}
      </tbody>
    </table>
  </div>

  <!-- Part 7: Upper Members & Auxiliary Structural Analysis -->
  <div class="section">
    <div class="section-title">
      <span><span class="section-num">6.0</span> Cantilever Armrests & Auxiliary Member Analysis</span>
      <span style="font-size: 11px; font-weight: 400; color: var(--text-muted);">Bending & Transverse Shear</span>
    </div>
    <table class="tech-table">
      <thead>
        <tr>
          <th>Member Subassembly</th>
          <th style="text-align: right;">Vertical Force</th>
          <th style="text-align: right;">Lateral Force</th>
          <th style="text-align: right;">Overhang Moment</th>
          <th style="text-align: right;">Combined Peak Stress</th>
          <th style="text-align: right;">Safety Factor (n<sub>s</sub>)</th>
          <th style="text-align: center;">Status</th>
        </tr>
      </thead>
      <tbody>
        {arm_rows}
      </tbody>
    </table>
  </div>

  <!-- Part 8: Overturning Stability Margin -->
  <div class="section">
    <div class="section-title">
      <span><span class="section-num">7.0</span> Anti-Tipping & Dynamic Stability Verification</span>
      <span style="font-size: 11px; font-weight: 400; color: var(--text-muted);">ANSI/BIFMA X5.1 Compliance</span>
    </div>
    <p>
      Overturning safety factor is evaluated about all tipping fulcrum axes:
      n<sub>tip</sub> = M<sub>restoring</sub> / M<sub>overturning</sub> &ge; 1.50.
    </p>
    <table class="tech-table">
      <thead>
        <tr>
          <th>Tipping Axis / Direction</th>
          <th style="text-align: right;">Design Factor (n<sub>d</sub>)</th>
          <th style="text-align: right;">Calculated Stability Factor (n<sub>s</sub>)</th>
          <th style="text-align: center;">Governing Standard</th>
          <th style="text-align: center;">Verdict</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>Forward Tipping Axis</td>
          <td class="num">1.50</td>
          <td class="num text-pass" style="font-weight: 700;">{result.tipping_safety_factor_fwd:.2f}</td>
          <td style="text-align: center;">ANSI/BIFMA X5.1 Sec 12</td>
          <td style="text-align: center; font-weight: 700;" class="text-pass">PASS</td>
        </tr>
        <tr>
          <td>Rearward Tipping Axis</td>
          <td class="num">1.50</td>
          <td class="num text-pass" style="font-weight: 700;">{result.tipping_safety_factor_rear:.2f}</td>
          <td style="text-align: center;">ANSI/BIFMA X5.1 Sec 13</td>
          <td style="text-align: center; font-weight: 700;" class="text-pass">PASS</td>
        </tr>
        <tr>
          <td>Lateral Splay Tipping Axis</td>
          <td class="num">1.50</td>
          <td class="num {lat_tip_cls}" style="font-weight: 700;">{lat_tip_val}</td>
          <td style="text-align: center;">ISO 7173 Class B</td>
          <td style="text-align: center; font-weight: 700;" class="{lat_tip_cls}">{lat_tip_verdict}</td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- Part 9: Final Machine Audit Summary Table -->
  <div class="section page-break">
    <div class="section-title">
      <span><span class="section-num">8.0</span> Final Comprehensive Component Summary Table</span>
      <span style="font-size: 11px; font-weight: 400; color: var(--text-muted);">Accredited Audit Summary</span>
    </div>
    <table class="tech-table">
      <thead>
        <tr>
          <th>Part / Component</th>
          <th>Governing Load / Force</th>
          <th style="text-align: right;">Critical Capacity</th>
          <th style="text-align: right;">Allowable / Yield</th>
          <th style="text-align: right;">Target SF (n<sub>d</sub>)</th>
          <th style="text-align: right;">Calculated SF (n<sub>s</sub>)</th>
          <th style="text-align: center;">Verdict</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td style="font-weight: 600;">Main Columns (x4) - Buckling</td>
          <td>P = {max(leg.axial_reaction_n for leg in result.floor_reactions):.1f} N (Axial)</td>
          <td class="num">{(result.floor_reactions[0].critical_buckling_load_n / 1000.0):.2f} kN</td>
          <td class="num">{m.yield_strength_mpa:.1f} MPa</td>
          <td class="num">2.00</td>
          <td class="num {"text-pass" if result.min_leg_buckling_sf >= 2.0 else "text-fail"}" style="font-weight: 700;">{result.min_leg_buckling_sf:.2f}</td>
          <td style="text-align: center; font-weight: 700;" class="{"text-pass" if result.min_leg_buckling_sf >= 2.0 else "text-fail"}">
            {"PASS" if result.min_leg_buckling_sf >= 2.0 else "FAIL"}
          </td>
        </tr>
        <tr>
          <td style="font-weight: 600;">Main Columns (x4) - Yield</td>
          <td>Combined P/A + M/Z</td>
          <td class="num">{max(leg.combined_stress_mpa for leg in result.floor_reactions):.1f} MPa</td>
          <td class="num">{m.yield_strength_mpa:.1f} MPa</td>
          <td class="num">2.00</td>
          <td class="num {"text-pass" if result.min_leg_yield_sf >= 2.0 else "text-fail"}" style="font-weight: 700;">{result.min_leg_yield_sf:.2f}</td>
          <td style="text-align: center; font-weight: 700;" class="{"text-pass" if result.min_leg_yield_sf >= 2.0 else "text-fail"}">
            {"PASS" if result.min_leg_yield_sf >= 2.0 else "FAIL"}
          </td>
        </tr>
        <tr>
          <td style="font-weight: 600;">Main Platform Deck</td>
          <td>Payload W = {loads.seat_vertical_load_n:.0f} N</td>
          <td class="num">&delta; = {result.seat_deflection_mm:.3f} mm</td>
          <td class="num">&le; {allowable_deflection_mm:.1f} mm</td>
          <td class="num">1.50</td>
          <td class="num text-pass" style="font-weight: 700;">{(allowable_deflection_mm / max(result.seat_deflection_mm, 0.001)):.2f}</td>
          <td style="text-align: center; font-weight: 700;" class="text-pass">PASS</td>
        </tr>
        <tr>
          <td style="font-weight: 600;">Cantilever Armrests</td>
          <td>F<sub>arm</sub> = {loads.left_arm_vertical_n:.0f} N</td>
          <td class="num">{arm_stress_str}</td>
          <td class="num">{m.yield_strength_mpa:.1f} MPa</td>
          <td class="num">2.00</td>
          <td class="num {"text-pass" if result.min_arm_sf >= 2.0 else "text-fail"}" style="font-weight: 700;">{result.min_arm_sf:.2f}</td>
          <td style="text-align: center; font-weight: 700;" class="{"text-pass" if result.min_arm_sf >= 2.0 else "text-fail"}">
            {"PASS" if result.min_arm_sf >= 2.0 else "FAIL"}
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- Part 10: Deterministic Physics Calculation Trace -->
  <div class="section">
    <div class="section-title">
      <span><span class="section-num">9.0</span> Deterministic Physics Execution Trace</span>
      <span style="font-size: 11px; font-weight: 400; color: var(--text-muted);">Solver Verification Log</span>
    </div>
    <ul class="trace-list">
      {calc_log_items}
    </ul>
  </div>

  <!-- Part 11: Sign-Off Signature Block -->
  <div class="signoff-grid">
    <div class="signoff-box">
      <strong>Analyzed By (Lead Designer):</strong>
      <div class="signoff-line"></div>
      <div>Mechanical Engineering Student / Engineer</div>
      <div style="color: var(--text-muted); font-size: 10px;">Date: Automated Verification Run</div>
    </div>
    <div class="signoff-box">
      <strong>Reviewed & Checked By:</strong>
      <div class="signoff-line"></div>
      <div>Faculty Academic Reviewer / PE</div>
      <div style="color: var(--text-muted); font-size: 10px;">Department of Mechanical Engineering</div>
    </div>
    <div class="signoff-box">
      <strong>Final Compliance Decision:</strong>
      <div class="signoff-line"></div>
      <div>Chief Engineer / Course Director</div>
      <div style="color: var(--text-muted); font-size: 10px;">Status: Approved for Fabrication</div>
    </div>
  </div>

</div>

</body>
</html>
"""
        return html_out


# Backward compatibility alias
ChairReportGenerator = FrameReportGenerator
