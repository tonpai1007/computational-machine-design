---
description: "Mechanical Engineering Academic & Professional Report Standard: Governs document presentation, dual-tier reporting (Core Calculation Sheet vs. University Assignment Dossier), and mathematical rigor for all MDIE deliverables."
globs: ["reporting/**", "drafting/**", "Project/**"]
---

# Mechanical Engineering Academic & Professional Report Standard (Engineerview)

This standard defines the mandatory document structure, visual presentation, and mathematical rigor for all computational engineering deliverables produced by the Machine Design Intelligence Engine (MDIE). It is grounded directly in accredited university Mechanical Engineering course project requirements (Year 3 Machine Design, ME311) and industrial design calculation dossiers.

---

## 1. Visual & Presentation Philosophy: Engineering Document, Not a SaaS Dashboard

> **A mechanical engineering calculation report is engineered for peer review, academic defense, and physical archival printing.**

### 1.1 White-Paper / Print-First Directives
- **Base Background:** Strictly pure white (`#ffffff`) or clean light engineering paper tone (`#f8fafc`).
- **Typography & Ink:** High-contrast dark ink (`#0f172a` or `#111827`). Headings in dark slate (`#0f172a`), muted text in neutral gray (`#475569`).
- **Prohibited Aesthetics:** No dark-mode canvas (`#0b0f19`, `#020617`), glowing neon badge cards, rounded pastel widgets, or SaaS/cryptocurrency dashboard themes.
- **Print & PDF Standard:**
  - Standard CSS print styling (`@media print`) must be included on every report.
  - Page configuration: `@page { size: A4 portrait; margin: 18mm 15mm 18mm 15mm; }`.
  - Major sections and drawing appendices must enforce clean page breaks (`page-break-before: always;`).

---

## 2. Dual-Tier Deliverable Architecture

MDIE maintains a clean separation between **Practitioner Calculation Sheets** (Core) and **Course Assignment Dossiers** (Academic Engine):

```
                       MDIE Report System
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
    [Tier 1: Core Engine]               [Tier 2: Academic Engine]
  Professional Calculation Sheet       University Assignment Dossier
  (e.g., chair_report.html)            (e.g., academic_assignment_report.html)
  ─────────────────────────────        ───────────────────────────────────────
  • Fast, lightweight, modular         • Complete course term project
  • White-paper engineering sheet      • Official Thai/English cover page
  • FBD, equilibrium, buckling         • Table of Contents (สารบัญ)
  • Master audit & sign-off            • 3D solid render preview
  • No student/course homework data    • 3D FEA direct stiffness summary
                                       • Manufacturing, welding & tolerances
                                       • Academic grading sign-off block
```

### 2.1 Tier 1: Core Professional Calculation Sheet (`<part>_report.html`)
- **Target Audience:** Design engineers, stress analysts, and regulatory auditors.
- **Scope:** Fast, focused, deterministic calculation sheet verifying static equilibrium, maximum stresses, Euler/Johnson column buckling, and component safety factors.
- **Constraints:** Strictly omit student IDs, academic group numbers, and university cover sheets. Focus purely on the machine component.

### 2.2 Tier 2: University Assignment Project Dossier (`academic_assignment_report.html`)
- **Target Audience:** Academic course instructors, laboratory directors, and university review committees.
- **Scope:** A complete, standalone Machine Design term project report formatted to Thai engineering curriculum standards (e.g. KMITL, Chulalongkorn, KMUTT).
- **Mandatory Academic Elements:**
  1. **Official Assignment Cover Sheet (หน้าปกรายงาน):** University header, faculty/department, course number (01016311 / ME 311), project title, group number, student author names & IDs, advisor block, submission date, and formal compliance verdict.
  2. **Table of Contents (สารบัญ):** Chapter-by-chapter index with dotted leader lines and page numbers.
  3. **3D Parametric CAD Render:** High-resolution render of the solid assembly (`preview.png`).
  4. **3D Direct Stiffness FEA Section:** Summary of spatial beam-column FEA (active DOFs, peak Von Mises stresses, maximum nodal deflection).
  5. **Industrial Production Plan:** Cold sawing, CNC mandrel tube bending, AWS D1.1 structural welding, electrostatic powder coating, and ISO 2768-m tolerances.
  6. **Academic Review Sign-Off:** 3-column signature block for Student Lead, Faculty Reviewer, and Committee Chair.

---

## 3. Mandatory Component Calculation Template (Step-by-Step Rigor)

Every critical load-bearing machine component (shafts, columns, beams, plates, cylinders, gears, fasteners) must present calculations in this textbook-proven sequence:

### Step 1: Component Dimensions & Section Geometry
- Callouts for physical dimensions: Length $L$, width $b$, height $h$, outside diameter $D_o$, inside diameter $D_i$, wall thickness $t$.
- Cross-sectional properties explicitly calculated:
  - Cross-Sectional Area: $A = \frac{\pi}{4}(D_o^2 - D_i^2)$ or $b \cdot h$
  - Moment of Inertia: $I = \frac{\pi}{64}(D_o^4 - D_i^4)$ or $\frac{b h^3}{12}$
  - Section Modulus: $Z = \frac{I}{c}$ where $c = \frac{D_o}{2}$ or $\frac{h}{2}$
  - Radius of Gyration: $k = \sqrt{\frac{I}{A}}$

### Step 2: Certified Material Specifications Table
Every component must cite its specific material properties with database source references:

| Property | Symbol | Value | Unit | Reference Standard |
| :--- | :---: | :---: | :---: | :--- |
| Material Grade | - | AISI 1018 / 6061-T6 / SS 304 | - | MatWeb Database / ASTM A513 |
| Mass Density | $\rho$ | 7.87 / 2.70 / 8.00 | $g/cm^3$ | Standard Density Table |
| Yield Strength | $S_y$ | ... | $MPa$ | AISC / ASM Metals Handbook |
| Ultimate Tensile Strength | $S_{ut}$ | ... | $MPa$ | AISC / ASM Metals Handbook |
| Modulus of Elasticity | $E$ | 205 / 69 / 193 | $GPa$ | ASTM E111 Static Test |
| Poisson's Ratio | $\nu$ | 0.29 / 0.33 / 0.29 | - | Standard Elastic Constant |

### Step 3: Static Equilibrium & Free-Body Diagram (FBD)
- Planar and spatial equilibrium balance:
  $$\sum F_x = 0, \quad \sum F_y = 0, \quad \sum F_z = 0, \quad \sum M = 0$$
- Clear vector Free-Body Diagram rendered as vector SVG on pure white paper (`#ffffff`) with:
  - Red arrows (`#dc2626`) for applied loads and service payloads.
  - Green arrows (`#16a34a`) for reaction forces at datum planes.
  - Blue curved arrows (`#2563eb`) for torques and overturning moments.
  - Dimension extension lines and callout text in clean dark slate.

### Step 4: Stress Analysis (Normal, Shear & Combined)
- Bending Stress: $\sigma_b = \frac{M \cdot c}{I} = \frac{M}{Z}$
- Torsional Shear: $\tau = \frac{T \cdot r}{J}$
- Transverse / Direct Shear: $\tau = \frac{V \cdot Q}{I \cdot b}$ or $\frac{3V}{2A}$
- Principal Stresses: $\sigma_{1,2} = \frac{\sigma}{2} \pm \sqrt{\left(\frac{\sigma}{2}\right)^2 + \tau^2}$
- Von Mises Equivalent Stress: $\sigma_{vm} = \sqrt{\sigma^2 + 3\tau^2}$

### Step 5: Fatigue & Marin Endurance Limit (Shigley Chapter 6)
- Unmodified endurance limit: $S_e' = 0.5 S_{ut}$ (for $S_{ut} \le 1400\text{ MPa}$).
- Marin modification factors explicitly computed:
  - Surface factor: $k_a = a S_{ut}^b$
  - Size factor: $k_b$
  - Load factor: $k_c$ (Bending $1.0$, Axial $0.85$, Torsion $0.59$)
  - Temperature factor: $k_d$
  - Reliability factor: $k_e = 1 - 0.08 Z_a$ ($95\%$ reliability $Z_a = 1.645 \rightarrow k_e = 0.868$)
  - Miscellaneous factor: $k_f$
- Modified Endurance Limit: $S_e = k_a k_b k_c k_d k_e k_f S_e'$
- High-Cycle Life: Basquin slope $b = -\frac{1}{3}\log\left(\frac{f S_{ut}}{S_e}\right)$, $S_f = a N^b$.

### Step 6: Column Buckling Stability (Euler vs. J.B. Johnson)
- Column slenderness ratio: $\lambda = \frac{L_{eff}}{k}$
- Column transition slenderness: $\lambda_1 = \left(\frac{L}{k}\right)_1 = \sqrt{\frac{2\pi^2 C E}{S_y}}$
- Explicit regime classification:
  - If $\lambda \ge \lambda_1 \rightarrow$ **Long Column (Euler elastic buckling):**
    $$P_{cr} = \frac{C \pi^2 E A}{(L/k)^2}$$
  - If $\lambda < \lambda_1 \rightarrow$ **Intermediate Column (J.B. Johnson parabolic buckling):**
    $$P_{cr} = A \left[ S_y - \frac{1}{C E}\left(\frac{S_y (L/k)}{2\pi}\right)^2 \right]$$

### Step 7: Safety Factor & Compliance Verdict
- Calculated Factor of Safety:
  $$n_s = \frac{\text{Loss-of-Function Load (Critical Strength)}}{\text{Maximum Working Load}}$$
- Explicit comparison against target Design Factor $n_d$:
  - If $n_s \ge n_d \rightarrow$ **PASS (VERIFIED COMPLIANT)**
  - If $n_s < n_d \rightarrow$ **FAIL (NON-COMPLIANT / REDESIGN REQUIRED)**

---

## 4. Master Component Audit Table

At the conclusion of the report, present a complete tabular audit across all analyzed components:

| Part / Component | Governing Load / Force | Critical Capacity ($P_{cr}$ or $S_y$) | Allowable Stress Limit | Target SF ($n_d$) | Calculated SF ($n_s$) | Verdict |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| Frame Columns (x4) - Buckling | $P = 748.9\text{ N}$ (Axial) | $P_{cr} = 58.33\text{ kN}$ | $S_y = 370.0\text{ MPa}$ | 2.00 | 77.89 | **PASS** |
| Frame Columns (x4) - Yield | Combined $P/A + M/Z$ | $\sigma_{max} = 9.8\text{ MPa}$ | $S_y = 370.0\text{ MPa}$ | 2.00 | 37.83 | **PASS** |
| Main Platform Deck | $W = 1,300\text{ N}$ (Payload) | $\delta_{max} = 0.45\text{ mm}$ | $\delta_{all} \le 5.0\text{ mm}$ | 1.50 | 11.19 | **PASS** |
| Cantilever Armrests | $F_{arm} = 450\text{ N}, M = 27\text{ N}\cdot\text{m}$ | $\sigma_{strut} = 40.8\text{ MPa}$ | $S_y = 370.0\text{ MPa}$ | 2.00 | 9.06 | **PASS** |
| Anti-Tipping Stability | Forward Overturning Axis | $M_{restoring} / M_{overturn}$ | $n_{tip} \ge 1.50$ | 1.50 | 3.33 | **PASS** |

---

## 5. Technical 2D Engineering Drawings (Blueprints)
- Must be attached or embedded as an ISO 128 / ANSI Y14.5 compliant drawing sheet.
- Must include a standard engineering title block (Drawn, Checked, Approved, Scale, Sheet No., Material, Tolerances).
- Must include dimensioned orthographic projections (front, side, top) and section views where internal cavities/holes exist.
