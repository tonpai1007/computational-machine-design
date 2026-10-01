"""
MDIE Engineering Report Generator
Generates comprehensive, audit-ready engineering calculation reports in HTML, SVG, and Markdown.
Includes executive compliance summary, equation trace, stress/deflection diagrams, and OpenSCAD CAD scripts.
"""

import html

from ai.critic import DesignCritic
from core.models import EngineeringModel, SolverResult


class ReportGenerator:
    @staticmethod
    def generate_svg_diagram(
        x_vals: list[float],
        y_vals: list[float],
        title: str,
        y_label: str,
        stroke_color: str = "#2563eb",
        fill_color: str = "rgba(37, 99, 235, 0.15)",
        width: int = 680,
        height: int = 180,
    ) -> str:
        """Generate clean, scalable SVG diagram for internal force/moment/stress curves."""
        if not x_vals or not y_vals or len(x_vals) != len(y_vals):
            return f'<div class="diagram-error">No data for {title}</div>'

        padding = 45
        plot_w = width - 2 * padding
        plot_h = height - 2 * padding

        min_x, max_x = min(x_vals), max(x_vals)
        min_y, max_y = min(y_vals), max(y_vals)

        # Ensure 0 line is visible
        min_y = min(min_y, 0.0)
        max_y = max(max_y, 0.0)
        span_y = max_y - min_y
        if span_y < 1e-9:
            span_y = 1.0
        span_x = max_x - min_x
        if span_x < 1e-9:
            span_x = 1.0

        # Mapping functions
        def map_x(x: float) -> float:
            return padding + ((x - min_x) / span_x) * plot_w

        def map_y(y: float) -> float:
            return padding + plot_h - ((y - min_y) / span_y) * plot_h

        zero_y = map_y(0.0)

        # Build path points
        points = []
        for x, y in zip(x_vals, y_vals, strict=True):
            points.append(f"{map_x(x):.1f},{map_y(y):.1f}")
        polyline_pts = " ".join(points)

        # Polygon for fill under curve
        polygon_pts = (
            f"{map_x(min_x):.1f},{zero_y:.1f} " + polyline_pts + f" {map_x(max_x):.1f},{zero_y:.1f}"
        )

        # SVG elements
        svg = [
            f'<svg viewBox="0 0 {width} {height}" class="chart-svg" xmlns="http://www.w3.org/2000/svg">',
            f'  <rect width="{width}" height="{height}" fill="#f8fafc" stroke="#e2e8f0" stroke-width="1" rx="4" />',
            f'  <text x="{padding}" y="22" fill="#0f172a" font-size="12" font-family="sans-serif" font-weight="bold">{html.escape(title)}</text>',
            "  <!-- Zero Baseline -->",
            f'  <line x1="{padding}" y1="{zero_y:.1f}" x2="{width - padding}" y2="{zero_y:.1f}" stroke="#94a3b8" stroke-dasharray="3,3" stroke-width="1" />',
            "  <!-- Y-Axis labels -->",
            f'  <text x="{padding - 8}" y="{map_y(max_y):.1f}" fill="#475569" font-size="10" text-anchor="end">{max_y:.1f}</text>',
            f'  <text x="{padding - 8}" y="{zero_y + 3:.1f}" fill="#475569" font-size="10" text-anchor="end">0.0</text>',
            f'  <text x="{padding - 8}" y="{map_y(min_y):.1f}" fill="#475569" font-size="10" text-anchor="end">{min_y:.1f}</text>',
            "  <!-- Filled Area -->",
            f'  <polygon points="{polygon_pts}" fill="{fill_color}" />',
            "  <!-- Curve Line -->",
            f'  <polyline points="{polyline_pts}" fill="none" stroke="{stroke_color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />',
            "  <!-- X-Axis Labels -->",
            f'  <text x="{padding}" y="{height - 8}" fill="#475569" font-size="10">x = {min_x * 1000:.0f} mm</text>',
            f'  <text x="{width - padding}" y="{height - 8}" fill="#475569" font-size="10" text-anchor="end">x = {max_x * 1000:.0f} mm</text>',
            "</svg>",
        ]
        return "\n".join(svg)

    @classmethod
    def generate_html_report(cls, model: EngineeringModel, result: SolverResult) -> str:
        """Generate comprehensive printable and interactive HTML engineering report."""
        review = DesignCritic.review_design(model, result)
        badge_class = "badge-pass" if result.all_constraints_passed else "badge-fail"
        badge_text = (
            "VERIFIED COMPLIANT (PASS)" if result.all_constraints_passed else "NON-COMPLIANT (FAIL)"
        )

        # SVG charts
        svg_shear = cls.generate_svg_diagram(
            result.x_stations,
            result.shear_force,
            "Shear Force Diagram V(x) [N]",
            "Force (N)",
            stroke_color="#38bdf8",
            fill_color="rgba(56, 189, 248, 0.15)",
        )
        svg_moment = cls.generate_svg_diagram(
            result.x_stations,
            result.bending_moment,
            "Bending Moment Diagram M(x) [N*m]",
            "Moment (N*m)",
            stroke_color="#a855f7",
            fill_color="rgba(168, 85, 247, 0.15)",
        )
        svg_stress = cls.generate_svg_diagram(
            result.x_stations,
            result.von_mises_stress_mpa,
            "Von Mises Stress Distribution σ_vm(x) [MPa]",
            "Stress (MPa)",
            stroke_color="#f43f5e",
            fill_color="rgba(244, 63, 94, 0.15)",
        )
        svg_deflection = cls.generate_svg_diagram(
            result.x_stations,
            result.deflection_mm,
            "Deflection Profile v(x) [mm]",
            "Deflection (mm)",
            stroke_color="#10b981",
            fill_color="rgba(16, 185, 129, 0.15)",
        )

        crit_sec = result.critical_section

        html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>MDIE Engineering Report - {html.escape(model.name)}</title>
  <style>
    :root {{
      --bg: #ffffff;
      --card-bg: #f8fafc;
      --border: #e2e8f0;
      --text: #0f172a;
      --text-muted: #475569;
      --accent: #1d4ed8;
      --pass: #047857;
      --fail: #b91c1c;
      --warn: #b45309;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Times New Roman", serif, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.6;
      margin: 0;
      padding: 35px;
    }}
    .container {{
      max-width: 960px;
      margin: 0 auto;
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 2px solid #0f172a;
      padding-bottom: 15px;
      margin-bottom: 25px;
    }}
    .header h1 {{
      margin: 0;
      font-size: 24px;
      color: #0f172a;
      letter-spacing: -0.3px;
    }}
    .header .subtitle {{
      color: var(--text-muted);
      font-size: 13px;
      margin-top: 4px;
    }}
    .badge {{
      display: inline-block;
      padding: 4px 12px;
      border-radius: 4px;
      font-weight: 700;
      font-size: 12px;
      letter-spacing: 0.5px;
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
    .grid-4 {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 14px;
      margin-bottom: 25px;
    }}
    .card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 14px 16px;
    }}
    .card .kpi-label {{
      font-size: 11px;
      color: var(--text-muted);
      text-transform: uppercase;
      font-weight: 600;
      letter-spacing: 0.5px;
    }}
    .card .kpi-val {{
      font-size: 22px;
      font-weight: 800;
      margin-top: 4px;
      color: #0f172a;
    }}
    .card .kpi-sub {{
      font-size: 11px;
      color: var(--text-muted);
      margin-top: 3px;
    }}
    h2 {{
      font-size: 16px;
      border-bottom: 1.5px solid #0f172a;
      padding-bottom: 6px;
      margin-top: 32px;
      margin-bottom: 14px;
      color: #0f172a;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 20px;
      font-size: 13px;
    }}
    th, td {{
      padding: 8px 12px;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }}
    th {{
      background: #f1f5f9;
      color: #0f172a;
      font-weight: 600;
      border-top: 1px solid var(--border);
    }}
    .chart-container {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 16px;
      margin-bottom: 25px;
    }}
    .chart-svg {{
      width: 100%;
      height: auto;
      border-radius: 4px;
      border: 1px solid var(--border);
      background: #f8fafc;
    }}
    pre.code-block {{
      background: #f8fafc;
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 12px;
      font-family: Consolas, monospace;
      font-size: 11.5px;
      color: #0f172a;
      overflow-x: auto;
      max-height: 320px;
    }}
    .review-box {{
      background: #eff6ff;
      border-left: 4px solid #1d4ed8;
      border-radius: 4px;
      padding: 16px;
      margin-bottom: 25px;
      color: #1e3a8a;
    }}
    @media print {{
      body {{ padding: 0; background: #ffffff; color: #000000; font-size: 12pt; }}
      .container {{ max-width: 100%; }}
      .card {{ border: 1px solid #cbd5e1; }}
      th {{ background: #f1f5f9 !important; color: #000000 !important; }}
      .chart-svg {{ break-inside: avoid; }}
      pre.code-block {{ max-height: none; page-break-inside: avoid; }}
    }}
    .review-box h3 {{
      margin-top: 0;
      color: #a5b4fc;
      font-size: 16px;
    }}
    .actions-list li {{
      margin-bottom: 8px;
    }}
    @media print {{
      body {{ background: #ffffff; color: #000000; }}
      .card, .header, th {{ background: #f8fafc; color: #000000; border-color: #cbd5e1; }}
      .chart-svg {{ border-color: #cbd5e1; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div>
        <h1>Machine Design Intelligence Engine</h1>
        <div class="subtitle">Deterministic Engineering Calculation Sheet &middot; Model: <strong>{
            html.escape(model.name)
        }</strong></div>
      </div>
      <div>
        <span class="badge {badge_class}">{badge_text}</span>
      </div>
    </div>

    <!-- Executive KPI Row -->
    <div class="grid-4">
      <div class="card">
        <div class="kpi-label">Yield Safety Factor</div>
        <div class="kpi-val" style="color: {"#10b981" if result.yield_passed else "#ef4444"};">{
            result.min_yield_safety_factor:.2f}</div>
        <div class="kpi-sub">Constraint: &ge; {model.constraints.min_yield_safety_factor:.2f}</div>
      </div>
      <div class="card">
        <div class="kpi-label">Fatigue SF (Goodman)</div>
        <div class="kpi-val" style="color: {"#10b981" if result.fatigue_passed else "#ef4444"};">{
            result.min_fatigue_safety_factor:.2f}</div>
        <div class="kpi-sub">Life: {
            "Infinite (&gt;10⁷ cycles)"
            if result.is_infinite_life
            else f"{result.fatigue_life_cycles:,.0f} cycles"
        }</div>
      </div>
      <div class="card">
        <div class="kpi-label">Max Deflection</div>
        <div class="kpi-val" style="color: {
            "#10b981" if result.deflection_passed else "#ef4444"
        };">{result.max_deflection_mm:.3f} mm</div>
        <div class="kpi-sub">Tolerance: &le; {model.constraints.max_deflection_mm:.3f} mm</div>
      </div>
      <div class="card">
        <div class="kpi-label">Component Mass</div>
        <div class="kpi-val">{result.total_mass_kg:.3f} kg</div>
        <div class="kpi-sub">Alloy: {html.escape(result.material_name)}</div>
      </div>
    </div>

    <!-- AI Critic & Copilot Review -->
    <div class="review-box">
      <h3>AI Design Review &amp; Root-Cause Analysis</h3>
      <p><strong>Overall Evaluation:</strong> {review["overall_status"]} &mdash; Strength: <strong>{
            review["strength_review"]
        }</strong>, Fatigue: <strong>{review["fatigue_review"]}</strong>, Deflection: <strong>{
            review["deflection_review"]
        }</strong>, Mass: <strong>{review["mass_review"]}</strong>.</p>

      {
            "<h4>Critical Issues:</h4><ul>"
            + "".join(f"<li>{html.escape(iss)}</li>" for iss in review["critical_issues"])
            + "</ul>"
            if review["critical_issues"]
            else ""
        }

      <h4>Recommended Engineering Actions:</h4>
      <ul class="actions-list">
        {"".join(f"<li>{html.escape(r)}</li>" for r in review["recommendations"])}
      </ul>
    </div>

    <!-- Engineering Assumptions Audit Log -->
    <h2>1. Design Inputs &amp; Engineering Assumptions Log</h2>
    <table>
      <thead>
        <tr>
          <th>Parameter</th>
          <th>Value</th>
          <th>Source</th>
          <th>Audit Status</th>
          <th>Engineering Notes</th>
        </tr>
      </thead>
      <tbody>
        {
            "".join(
                f'<tr><td>{html.escape(a.parameter)}</td><td><strong>{html.escape(str(a.value))}</strong></td><td>{html.escape(a.source)}</td><td><span style="color: {"#10b981" if a.status == "CONFIRMED" else "#f59e0b"}; font-weight:600;">{html.escape(a.status)}</span></td><td>{html.escape(a.notes or "")}</td></tr>'
                for a in model.assumptions
            )
        }
      </tbody>
    </table>

    <!-- Material Specifications -->
    <h2>2. Material Mechanical Properties</h2>
    <table>
      <thead>
        <tr>
          <th>Alloy Name</th>
          <th>Yield Strength (S_y)</th>
          <th>Ultimate Strength (S_ut)</th>
          <th>Endurance Limit (S_e)</th>
          <th>Modulus (E)</th>
          <th>Density (&rho;)</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>{html.escape(result.material_name)}</strong></td>
          <td>{result.yield_strength_mpa:.1f} MPa</td>
          <td>{result.ultimate_strength_mpa:.1f} MPa</td>
          <td>{result.endurance_limit_mpa:.1f} MPa</td>
          <td>206.0 GPa</td>
          <td>7,850 kg/m&sup3;</td>
        </tr>
      </tbody>
    </table>

    <!-- Equilibrium & Reactions -->
    <h2>3. Equilibrium &amp; Support Reactions</h2>
    <table>
      <thead>
        <tr>
          <th>Support Location</th>
          <th>Axial Coordinate (x)</th>
          <th>Vertical Reaction Force (R_y)</th>
          <th>Reaction Moment (M_R)</th>
        </tr>
      </thead>
      <tbody>
        {
            "".join(
                f"<tr><td>{html.escape(r.support_name)}</td><td>{r.position * 1000.0:.1f} mm</td><td><strong>{r.reaction_force_n:.2f} N</strong></td><td>{r.reaction_moment_nm:.2f} N&middot;m</td></tr>"
                for r in result.reactions
            )
        }
      </tbody>
    </table>
    <p><strong>Nominal Transmitted Torque:</strong> {result.applied_torque_nm:.2f} N&middot;m</p>

    <!-- Internal Distributions & Diagrams -->
    <h2>4. Internal Loading &amp; Structural Diagrams</h2>
    <div class="chart-container">
      {svg_shear}
      {svg_moment}
      {svg_stress}
      {svg_deflection}
    </div>

    <!-- Critical Section Analysis -->
    <h2>5. Critical Section Analysis (Peak Stress Plane)</h2>
    {
            "<table><thead><tr><th>Station (x)</th><th>Diameter</th><th>Bending Moment</th><th>Bending Stress</th><th>Torque</th><th>Torsional Stress</th><th>Kt (Bending)</th><th>Von Mises &sigma;_vm</th></tr></thead><tbody>"
            + f'<tr><td><strong>{crit_sec.x * 1000.0:.1f} mm</strong></td><td>{crit_sec.outer_diameter * 1000.0:.1f} mm</td><td>{crit_sec.bending_moment:.2f} N&middot;m</td><td>{crit_sec.bending_stress:.2f} MPa</td><td>{crit_sec.torque:.2f} N&middot;m</td><td>{crit_sec.torsional_stress:.2f} MPa</td><td>{crit_sec.kt_bending:.2f}</td><td><strong style="color: #f43f5e;">{crit_sec.effective_von_mises:.2f} MPa</strong></td></tr></tbody></table>'
            if crit_sec
            else "<p>No critical section data.</p>"
        }

    <!-- Standard Machine Components (Bearings & Keyways) -->
    <h2>6. Standard Machine Components: Bearings &amp; Keys</h2>

    <h3>A. SKF Standard Rolling Bearings (ISO 281 L10h Life)</h3>
    {
            "<table><thead><tr><th>Location</th><th>Bearing Designation</th><th>Bore (d)</th><th>Outer (D)</th><th>Width (B)</th><th>Dynamic Capacity (C)</th><th>Equivalent Load (P)</th><th>Rating Life (L10h)</th><th>Suitability</th></tr></thead><tbody>"
            + "".join(
                f'<tr><td>Support @ {b.get("bearing", {}).get("bore_diameter_mm")} mm journal</td><td><strong>{b.get("bearing", {}).get("designation")}</strong></td><td>{b.get("bearing", {}).get("bore_diameter_mm")} mm</td><td>{b.get("bearing", {}).get("outer_diameter_mm")} mm</td><td>{b.get("bearing", {}).get("width_mm")} mm</td><td>{b.get("bearing", {}).get("dynamic_load_c_kn")} kN</td><td>{b.get("radial_load_n", 0):.1f} N</td><td><strong style="color: #38bdf8;">{b.get("l10h_hours", 0):,.0f} hours</strong></td><td><span style="color: {"#10b981" if b.get("status") in ("EXCELLENT", "GOOD") else "#f59e0b"}; font-weight:600;">{b.get("status")}</span></td></tr>'
                for b in result.bearings_selected
            )
            + "</tbody></table>"
            if result.bearings_selected
            else "<p>No bearing data available.</p>"
        }

    <h3>B. Standard Parallel Key &amp; Keyway Verification (DIN 6885-1)</h3>
    {
            f'<table><thead><tr><th>Standard</th><th>Shaft Bore</th><th>Key Section (w &times; h)</th><th>Key Length (L)</th><th>Shear Stress (&tau;)</th><th>Shear SF</th><th>Crush Pressure (&sigma;_c)</th><th>Crush SF</th><th>Status</th></tr></thead><tbody><tr><td>{result.keyway_analysis.get("standard")}</td><td>{result.keyway_analysis.get("shaft_diameter_mm")} mm</td><td>{result.keyway_analysis.get("key_width_mm")}&times;{result.keyway_analysis.get("key_height_mm")} mm</td><td>{result.keyway_analysis.get("key_length_mm")} mm</td><td>{result.keyway_analysis.get("shear_stress_mpa")} MPa</td><td><strong>{result.keyway_analysis.get("shear_safety_factor")}</strong></td><td>{result.keyway_analysis.get("crushing_stress_mpa")} MPa</td><td><strong>{result.keyway_analysis.get("crushing_safety_factor")}</strong></td><td><span style="color: {"#10b981" if result.keyway_analysis.get("passed") else "#ef4444"}; font-weight:600;">{"PASS" if result.keyway_analysis.get("passed") else "FAIL"}</span></td></tr></tbody></table>'
            if result.keyway_analysis
            else "<p>No keyway required for this load condition.</p>"
        }

    <!-- OpenSCAD CAD Code -->
    <h2>7. Parametric OpenSCAD 3D CAD Definition</h2>
    <p>Clean parametric script generated for 3D modeling, CAM, and CNC lathe/machining:</p>
    <pre class="code-block">{html.escape(result.openscad_code)}</pre>

    <!-- Verification Audit Trace -->
    <h2>8. Deterministic Physics Solver Audit Trace</h2>
    <ol>
      {"".join(f"<li>{html.escape(step)}</li>" for step in result.calculation_steps)}
    </ol>

    <footer style="margin-top: 50px; padding-top: 20px; border-top: 1px solid var(--border); color: var(--text-muted); font-size: 11px; text-align: center;">
      Machine Design Intelligence Engine (MDIE) &middot; "AI proposes and reasons. Physics verifies." &middot; Deterministic Ground Truth Authority
    </footer>
  </div>
</body>
</html>
"""
        return html_out

    @classmethod
    def generate_markdown_report(cls, model: EngineeringModel, result: SolverResult) -> str:
        """Generate GitHub-flavored Markdown engineering report."""
        review = DesignCritic.review_design(model, result)
        badge = (
            "✅ PASS - VERIFIED COMPLIANT"
            if result.all_constraints_passed
            else "❌ FAIL - NON-COMPLIANT"
        )

        lines = [
            "# Machine Design Intelligence Engine (MDIE) - Calculation Sheet",
            f"**Model:** {model.name}  ",
            f"**Verification Status:** {badge}  ",
            "**Authority:** Deterministic Physics Engine  ",
            "",
            "## 1. Executive Summary",
            "| Metric | Calculated | Allowable / Limit | Status |",
            "| :--- | :--- | :--- | :--- |",
            f"| **Yield Safety Factor** | {result.min_yield_safety_factor:.2f} | &ge; {model.constraints.min_yield_safety_factor:.2f} | {'PASS' if result.yield_passed else 'FAIL'} |",
            f"| **Fatigue Safety Factor (Goodman)** | {result.min_fatigue_safety_factor:.2f} | &ge; {model.constraints.min_fatigue_safety_factor:.2f} | {'PASS' if result.fatigue_passed else 'FAIL'} |",
            f"| **Maximum Deflection** | {result.max_deflection_mm:.3f} mm | &le; {model.constraints.max_deflection_mm:.3f} mm | {'PASS' if result.deflection_passed else 'FAIL'} |",
            f"| **Component Total Mass** | {result.total_mass_kg:.3f} kg | {f'<= {model.constraints.max_mass_kg} kg' if model.constraints.max_mass_kg else 'Unconstrained'} | {'PASS' if review['mass_review'] == 'PASS' else 'FAIL'} |",
            f"| **Fatigue Life Prediction** | {result.fatigue_life_cycles:,.0f} cycles | Target: {model.constraints.target_life_cycles:,.0f} | {'PASS' if result.fatigue_passed else 'FAIL'} |",
            "",
            "## 2. AI Design Critic Review",
            f"**Overall Status:** {review['overall_status']}  ",
            f"**Primary Stress Contributors:** Bending: {review['stress_breakdown'].get('bending_percentage')}%, Torsion: {review['stress_breakdown'].get('torsion_percentage')}%.  ",
            "",
            "### Recommended Actions:",
        ]
        for r in review["recommendations"]:
            lines.append(f"- {r}")

        lines.extend(
            [
                "",
                "## 3. Engineering Assumptions Log",
                "| Parameter | Value | Source | Status | Notes |",
                "| :--- | :--- | :--- | :--- | :--- |",
            ]
        )
        for a in model.assumptions:
            lines.append(
                f"| {a.parameter} | {a.value} | {a.source} | {a.status} | {a.notes or ''} |"
            )

        lines.extend(
            [
                "",
                "## 4. Support Reactions",
                "| Support | Axial Position | Reaction Force | Reaction Moment |",
                "| :--- | :--- | :--- | :--- |",
            ]
        )
        for r in result.reactions:
            lines.append(
                f"| {r.support_name} | {r.position * 1000.0:.1f} mm | {r.reaction_force_n:.2f} N | {r.reaction_moment_nm:.2f} N*m |"
            )

        lines.extend(
            [
                "",
                "## 5. Parametric OpenSCAD Code",
                "```scad",
                result.openscad_code,
                "```",
                "",
                "## 6. Physics Solver Trace",
            ]
        )
        for step in result.calculation_steps:
            lines.append(f"- {step}")

        return "\n".join(lines)
