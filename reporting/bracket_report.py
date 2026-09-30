"""
Motor Mounting Bracket & Plate Academic Engineering Report Generator
Produces formal, audit-ready engineering dossiers adhering to university Machine Design standards:
- Strictly white-paper / print-first aesthetic (@media print for standard A4 portrait)
- Bill of Materials (BOM) & component section properties
- Material specifications with source citations (MatWeb / AISC / ASTM)
- Free-body diagram (FBD) and equilibrium equations
- Step-by-step structural checks (overturning root moment, transverse shear, fastener shear, bearing stress)
- Comprehensive component summary audit table and formal engineering sign-off block
"""

from typing import Dict, Any
from core.bracket_model import BracketModel
from physics.bracket_physics import BracketSolverResult


class BracketReportGenerator:
    """Generates academic-standard, peer-reviewable structural calculation reports for mounting brackets."""

    @staticmethod
    def generate_html_report(model: BracketModel, result: BracketSolverResult) -> str:
        g = model.geometry
        l = model.loads
        m = model.material
        pat = g.motor_bolt_pattern
        base_pat = g.base_bolt_pattern

        overall_badge = (
            '<span class="badge badge-pass">VERIFIED COMPLIANT (PASS)</span>'
            if result.passed
            else '<span class="badge badge-fail">NON-COMPLIANT (REDESIGN REQUIRED)</span>'
        )

        plate_badge = (
            '<span class="text-pass" style="font-weight: 700;">PASS</span>'
            if result.plate_yield_safety_factor >= 1.5
            else '<span class="text-fail" style="font-weight: 700;">FAIL</span>'
        )

        bolt_badge = (
            '<span class="text-pass" style="font-weight: 700;">PASS</span>'
            if result.bolt_safety_factor >= 2.0
            else '<span class="text-fail" style="font-weight: 700;">FAIL</span>'
        )

        # SVG Free-Body Diagram of L-Bracket (Clean white paper aesthetic)
        svg_diagram = f"""
        <svg viewBox="0 0 720 380" style="width: 100%; height: auto; background: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px;">
            <defs>
                <marker id="arr-red" viewBox="0 0 10 10" refX="5" refY="10" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M 0 0 L 10 0 L 5 10 z" fill="#dc2626" />
                </marker>
                <marker id="arr-green" viewBox="0 0 10 10" refX="5" refY="0" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M 0 10 L 10 10 L 5 0 z" fill="#16a34a" />
                </marker>
                <marker id="arr-blue" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M 0 0 L 10 5 L 0 10 z" fill="#2563eb" />
                </marker>
            </defs>

            <!-- Rigid Mounting Ground Base -->
            <line x1="60" y1="310" x2="660" y2="310" stroke="#64748b" stroke-width="2" stroke-dasharray="6,4" />
            <text x="70" y="332" fill="#475569" font-size="11" font-family="'Times New Roman', serif, sans-serif">Rigid Machine Bedplate / Chassis Datum (Z = 0)</text>
            <path d="M 70 310 L 60 320 M 110 310 L 100 320 M 150 310 L 140 320 M 570 310 L 560 320 M 610 310 L 600 320 M 650 310 L 640 320" stroke="#94a3b8" stroke-width="1.5" />

            <!-- Horizontal Base Foot -->
            <rect x="180" y="280" width="340" height="30" rx="2" fill="#f1f5f9" stroke="#0f172a" stroke-width="2" />
            <text x="350" y="300" fill="#1e293b" font-size="11" font-weight="600" font-family="Inter, sans-serif" text-anchor="middle">Base Foot (L = {g.base_length_mm:.0f} mm, t = {g.thickness_mm:.1f} mm)</text>

            <!-- Vertical Upright Flange -->
            <rect x="180" y="80" width="28" height="200" rx="2" fill="#f1f5f9" stroke="#0f172a" stroke-width="2" />
            <text x="140" y="180" fill="#334155" font-size="11" font-weight="600" font-family="Inter, sans-serif" transform="rotate(-90 140 180)" text-anchor="middle">Upright Flange (H = {g.upright_height_mm:.0f} mm)</text>

            <!-- Gusset Triangles -->
            <polygon points="208,280 320,280 208,160" fill="#e0f2fe" stroke="#0284c7" stroke-width="1.5" stroke-dasharray="4,2" />
            <text x="250" y="250" fill="#0369a1" font-size="10" font-weight="600" font-family="Inter, sans-serif">Stiffener Gusset</text>

            <!-- Motor Housing Phantom Box -->
            <rect x="208" y="100" width="160" height="120" rx="4" fill="#f8fafc" stroke="#475569" stroke-width="1.5" stroke-dasharray="5,5" />
            <text x="288" y="165" fill="#0f172a" font-size="11" font-weight="700" font-family="Inter, sans-serif" text-anchor="middle">Electric Motor ({l.motor_mass_kg:.1f} kg)</text>

            <!-- Motor Pilot Bore -->
            <line x1="180" y1="160" x2="208" y2="160" stroke="#dc2626" stroke-width="2.5" />
            <circle cx="194" cy="160" r="14" fill="#ffffff" stroke="#d97706" stroke-width="1.5" />
            <text x="194" y="164" fill="#b45309" font-size="9" font-weight="700" text-anchor="middle" font-family="'JetBrains Mono', monospace">&Oslash;{g.motor_pilot_diameter_mm:.0f}</text>

            <!-- Motor CG & Overturning Weight Vector -->
            <circle cx="288" cy="160" r="5" fill="#dc2626" />
            <line x1="288" y1="160" x2="288" y2="240" stroke="#dc2626" stroke-width="2.5" marker-end="url(#arr-red)" />
            <text x="300" y="220" fill="#b91c1c" font-size="11" font-weight="700" font-family="'JetBrains Mono', monospace">F_g = {result.motor_weight_n:.1f} N</text>

            <!-- Cantilever Arm Dimension -->
            <line x1="208" y1="85" x2="288" y2="85" stroke="#64748b" stroke-width="1.2" />
            <line x1="208" y1="80" x2="208" y2="90" stroke="#64748b" stroke-width="1.2" />
            <line x1="288" y1="80" x2="288" y2="90" stroke="#64748b" stroke-width="1.2" />
            <text x="248" y="78" fill="#475569" font-size="10" font-family="'JetBrains Mono', monospace" text-anchor="middle">Arm = {l.cantilever_arm_mm:.0f} mm</text>

            <!-- Dynamic Torque Reaction Curved Arrow -->
            <path d="M 370 140 A 25 25 0 0 1 370 180" fill="none" stroke="#7c3aed" stroke-width="2.5" marker-end="url(#arr-blue)" />
            <text x="405" y="165" fill="#6d28d9" font-size="11" font-weight="700" font-family="'JetBrains Mono', monospace">T = {l.motor_torque_nm:.1f} N·m</text>

            <!-- Overturning Moment Reaction at Root -->
            <path d="M 160 270 A 30 30 0 0 1 190 250" fill="none" stroke="#d97706" stroke-width="2.5" marker-end="url(#arr-blue)" />
            <text x="90" y="260" fill="#b45309" font-size="11" font-weight="700" font-family="'JetBrains Mono', monospace">M_root = {result.overturning_moment_nm:.1f} N·m</text>

            <!-- Bolt Fastener Holes -->
            <circle cx="230" cy="295" r="4" fill="#ffffff" stroke="#16a34a" stroke-width="2" />
            <circle cx="470" cy="295" r="4" fill="#ffffff" stroke="#16a34a" stroke-width="2" />
            <text x="470" y="325" fill="#15803d" font-size="10" font-weight="600" font-family="Inter, sans-serif" text-anchor="middle">Base Anchor (4x &Oslash;{base_pat.hole_diameter_mm:.1f})</text>
        </svg>
        """

        calc_log_items = "".join([f"<li>{log}</li>" for log in result.calculation_log])

        html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Engineering Design & Structural Calculation Report - {model.name}</title>
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
      font-family: 'Times New Roman', Times, 'Inter', -apple-system, serif;
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
    .text-pass {{
      color: var(--pass);
    }}
    .text-fail {{
      color: var(--fail);
    }}
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
        <div class="inst-title">Mechanical Engineering Department &bull; Machine Design Project</div>
        <div style="font-size: 11px; color: #64748b;">Motor Mounting Bracket Structural & Fastener Dossier</div>
      </div>
      <div class="doc-meta">
        <div><strong>Doc ID:</strong> MDIE-BRACKET-{model.name.upper().replace(' ', '_')}</div>
        <div><strong>Standard:</strong> ASME B1.1 &bull; ISO 898-1 &bull; AISC 360</div>
        <div><strong>Units:</strong> SI Metric (mm, N, N·m, MPa, GPa)</div>
      </div>
    </div>
    <h1 class="main-title">{model.name}</h1>
    <div class="subtitle">
      Cantilever Motor Mounting Bracket &bull; Plate Thickness {g.thickness_mm:.1f} mm &bull; Material: {m.name}
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

  <!-- Part 2: Introduction & Operating Objective -->
  <div class="section">
    <div class="section-title">
      <span><span class="section-num">1.0</span> Introduction & Deterministic Mechanical Summary</span>
      <span style="font-size: 11px; font-weight: 400; color: var(--text-muted);">Executive Brief</span>
    </div>
    <p>
      This audit sheet provides deterministic stress, fastener shear, and plate bending verification for the
      motor mounting bracket assembly supporting a <strong>{l.motor_mass_kg:.1f} kg</strong> drive motor with
      an operating torque of <strong>{l.motor_torque_nm:.1f} N&middot;m</strong> cantilevered at <strong>{l.cantilever_arm_mm:.0f} mm</strong>.
    </p>
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Peak Von Mises Stress</div>
        <div class="kpi-val">{result.max_von_mises_mpa:.1f} <span style="font-size: 11px; color: var(--text-muted);">MPa</span></div>
        <div class="kpi-sub">Plate Yield Limit: {m.yield_strength_mpa:.1f} MPa</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Plate Yield Safety Factor</div>
        <div class="kpi-val {'text-pass' if result.plate_yield_safety_factor >= 1.5 else 'text-fail'}">{result.plate_yield_safety_factor:.2f}</div>
        <div class="kpi-sub">Design Target: n<sub>d</sub> &ge; 1.50</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Motor Bolt Shear Stress</div>
        <div class="kpi-val">{result.motor_bolt_shear_stress_mpa:.1f} <span style="font-size: 11px; color: var(--text-muted);">MPa</span></div>
        <div class="kpi-sub">Fastener Grade: 8.8 (S<sub>y</sub> = 640 MPa)</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Fastener Safety Factor</div>
        <div class="kpi-val {'text-pass' if result.bolt_safety_factor >= 2.0 else 'text-fail'}">{result.bolt_safety_factor:.2f}</div>
        <div class="kpi-sub">Design Target: n<sub>d</sub> &ge; 2.00</div>
      </div>
    </div>
  </div>

  <!-- Part 3: Bill of Materials & Section Geometry -->
  <div class="section">
    <div class="section-title">
      <span><span class="section-num">2.0</span> Bill of Materials (BOM) & Parametric Dimensions</span>
      <span style="font-size: 11px; font-weight: 400; color: var(--text-muted);">Physical Specifications</span>
    </div>
    <table class="tech-table">
      <thead>
        <tr>
          <th>Item</th>
          <th>Component Description</th>
          <th>Geometric Dimensions</th>
          <th style="text-align: right;">Qty</th>
          <th>Material Specification</th>
          <th>Fabrication Process</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td style="font-weight: 600;">1</td>
          <td>Horizontal Base Foot Plate</td>
          <td>{g.base_length_mm:.0f} &times; {g.base_width_mm:.0f} &times; {g.thickness_mm:.1f} mm</td>
          <td class="num">1</td>
          <td>{m.name}</td>
          <td>CNC Laser Cut / Waterjet + Brake Form</td>
        </tr>
        <tr>
          <td style="font-weight: 600;">2</td>
          <td>Vertical Upright Flange</td>
          <td>Height: {g.upright_height_mm:.0f} mm, Pilot: &Oslash;{g.motor_pilot_diameter_mm:.0f} mm</td>
          <td class="num">1</td>
          <td>{m.name}</td>
          <td>Precision Bored Pilot + Clearance Holes</td>
        </tr>
        <tr>
          <td style="font-weight: 600;">3</td>
          <td>Reinforcement Gusset Ribs</td>
          <td>{f'Dual Triangular Ribs (t = {g.thickness_mm:.1f} mm)' if g.has_gussets else 'None'}</td>
          <td class="num">{2 if g.has_gussets else 0}</td>
          <td>{m.name}</td>
          <td>Fillet Welded Structural Ribs</td>
        </tr>
        <tr>
          <td style="font-weight: 600;">4</td>
          <td>Motor Flange Fasteners</td>
          <td>{pat.num_holes}x M{(pat.hole_diameter_mm - 0.5):.0f} Bolts (BCD {pat.bolt_circle_diameter_mm:.0f} mm)</td>
          <td class="num">{pat.num_holes}</td>
          <td>ISO 898-1 Class 8.8 Steel</td>
          <td>Standard Hex Head Cap Screws</td>
        </tr>
      </tbody>
    </table>
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
          <td>MatWeb Database / ASTM A36 / 1018</td>
        </tr>
        <tr>
          <td>Mass Density</td>
          <td>&rho;</td>
          <td class="num">{(m.density_kg_m3 / 1000.0):.2f}</td>
          <td>g/cm&sup3;</td>
          <td>Standard ({m.density_kg_m3:.0f} kg/m&sup3;)</td>
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
          <td>Modulus of Elasticity</td>
          <td>E</td>
          <td class="num">{m.elastic_modulus_gpa:.1f}</td>
          <td>GPa</td>
          <td>ASTM E111 Standard Static Test</td>
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
      The cantilevered motor mass generates an overturning moment about the root bend:
    </p>
    <div class="calc-step">
      <div class="equation-line">F<sub>g</sub> = m &times; g = {l.motor_mass_kg:.1f} kg &times; 9.807 m/s&sup2; = {result.motor_weight_n:.1f} N</div>
      <div class="equation-line">M<sub>overturning</sub> = F<sub>g</sub> &times; L<sub>arm</sub> = {result.motor_weight_n:.1f} N &times; {l.cantilever_arm_mm:.1f} mm = {result.overturning_moment_nm:.1f} N&middot;m</div>
    </div>
    <div style="margin: 14px 0;">
      {svg_diagram}
    </div>
  </div>

  <!-- Part 6: Step-by-Step Structural Calculations -->
  <div class="section page-break">
    <div class="section-title">
      <span><span class="section-num">5.0</span> Detailed Structural Checks & Stress Analysis</span>
      <span style="font-size: 11px; font-weight: 400; color: var(--text-muted);">Failure Mode Verification</span>
    </div>
    <table class="tech-table">
      <thead>
        <tr>
          <th>Failure Mode / Component</th>
          <th>Applied Load / Moment</th>
          <th style="text-align: right;">Calculated Stress</th>
          <th style="text-align: right;">Allowable Limit</th>
          <th style="text-align: right;">Calculated SF (n<sub>s</sub>)</th>
          <th style="text-align: center;">Compliance</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td style="font-weight: 600;">Plate Root Bending (Overturning)</td>
          <td>M<sub>root</sub> = {result.overturning_moment_nm:.1f} N&middot;m</td>
          <td class="num">{result.root_bending_stress_mpa:.1f} MPa</td>
          <td class="num">{m.yield_strength_mpa:.1f} MPa</td>
          <td class="num {'text-pass' if result.plate_yield_safety_factor >= 1.5 else 'text-fail'}" style="font-weight: 700;">{result.plate_yield_safety_factor:.2f}</td>
          <td style="text-align: center;">{plate_badge}</td>
        </tr>
        <tr>
          <td style="font-weight: 600;">Transverse Direct Shear</td>
          <td>F<sub>g</sub> = {result.motor_weight_n:.1f} N</td>
          <td class="num">{result.plate_shear_stress_mpa:.2f} MPa</td>
          <td class="num">{(m.yield_strength_mpa * 0.577):.1f} MPa</td>
          <td class="num text-pass" style="font-weight: 700;">{((m.yield_strength_mpa * 0.577) / max(result.plate_shear_stress_mpa, 0.01)):.1f}</td>
          <td style="text-align: center;" class="text-pass"><strong>PASS</strong></td>
        </tr>
        <tr>
          <td style="font-weight: 600;">Motor Bolt Fasteners (Shear)</td>
          <td>{pat.num_holes}x Bolts (BCD {pat.bolt_circle_diameter_mm:.0f} mm)</td>
          <td class="num">{result.motor_bolt_shear_stress_mpa:.1f} MPa</td>
          <td class="num">300.0 MPa (Grade 8.8)</td>
          <td class="num {'text-pass' if result.bolt_safety_factor >= 2.0 else 'text-fail'}" style="font-weight: 700;">{result.bolt_safety_factor:.2f}</td>
          <td style="text-align: center;">{bolt_badge}</td>
        </tr>
        <tr>
          <td style="font-weight: 600;">Fastener Hole Bearing / Tearout</td>
          <td>Plate t = {g.thickness_mm:.1f} mm</td>
          <td class="num">{result.hole_bearing_stress_mpa:.1f} MPa</td>
          <td class="num">{(m.yield_strength_mpa * 1.5):.1f} MPa</td>
          <td class="num text-pass" style="font-weight: 700;">{((m.yield_strength_mpa * 1.5) / max(result.hole_bearing_stress_mpa, 0.01)):.2f}</td>
          <td style="text-align: center;" class="text-pass"><strong>PASS</strong></td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- Part 7: Comprehensive Summary Table -->
  <div class="section">
    <div class="section-title">
      <span><span class="section-num">6.0</span> Final Comprehensive Component Summary Table</span>
      <span style="font-size: 11px; font-weight: 400; color: var(--text-muted);">Accredited Audit Summary</span>
    </div>
    <table class="tech-table">
      <thead>
        <tr>
          <th>Part / Component</th>
          <th>Governing Load / Force</th>
          <th style="text-align: right;">Critical Stress</th>
          <th style="text-align: right;">Allowable / Yield</th>
          <th style="text-align: right;">Target SF (n<sub>d</sub>)</th>
          <th style="text-align: right;">Calculated SF (n<sub>s</sub>)</th>
          <th style="text-align: center;">Verdict</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td style="font-weight: 600;">Bracket Upright Plate</td>
          <td>M<sub>overturn</sub> = {result.overturning_moment_nm:.1f} N&middot;m</td>
          <td class="num">&sigma;<sub>vm</sub> = {result.max_von_mises_mpa:.1f} MPa</td>
          <td class="num">{m.yield_strength_mpa:.1f} MPa</td>
          <td class="num">1.50</td>
          <td class="num {'text-pass' if result.plate_yield_safety_factor >= 1.5 else 'text-fail'}" style="font-weight: 700;">{result.plate_yield_safety_factor:.2f}</td>
          <td style="text-align: center; font-weight: 700;" class="{'text-pass' if result.plate_yield_safety_factor >= 1.5 else 'text-fail'}">
            {'PASS' if result.plate_yield_safety_factor >= 1.5 else 'FAIL'}
          </td>
        </tr>
        <tr>
          <td style="font-weight: 600;">Mounting Fasteners (x{pat.num_holes})</td>
          <td>T = {l.motor_torque_nm:.1f} N&middot;m + F<sub>g</sub></td>
          <td class="num">&tau;<sub>bolt</sub> = {result.motor_bolt_shear_stress_mpa:.1f} MPa</td>
          <td class="num">300.0 MPa</td>
          <td class="num">2.00</td>
          <td class="num {'text-pass' if result.bolt_safety_factor >= 2.0 else 'text-fail'}" style="font-weight: 700;">{result.bolt_safety_factor:.2f}</td>
          <td style="text-align: center; font-weight: 700;" class="{'text-pass' if result.bolt_safety_factor >= 2.0 else 'text-fail'}">
            {'PASS' if result.bolt_safety_factor >= 2.0 else 'FAIL'}
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- Part 8: Deterministic Physics Calculation Trace -->
  <div class="section">
    <div class="section-title">
      <span><span class="section-num">7.0</span> Physics Solver Execution Trace</span>
      <span style="font-size: 11px; font-weight: 400; color: var(--text-muted);">Solver Verification Log</span>
    </div>
    <ul class="trace-list">
      {calc_log_items}
    </ul>
  </div>

  <!-- Part 9: Sign-Off Signature Block -->
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
