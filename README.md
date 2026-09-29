# Machine Design Intelligence Engine (MDIE)

> **An AI-assisted computational engineering platform for machine design, structural analysis, material selection, optimization, OpenSCAD 3D modeling, and verified engineering reports.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Modern%20API-teal.svg)](https://fastapi.tiangolo.com/)
[![OpenSCAD](https://img.shields.io/badge/CAD-OpenSCAD%20Parametric-orange.svg)](https://openscad.org/)
[![Three.js](https://img.shields.io/badge/WebGL-Three.js%203D-black.svg)](https://threejs.org/)
[![Physics Solver](https://img.shields.io/badge/Physics-Deterministic%20Authority-green.svg)]()

---

## 1. Core Principle

> ### **AI proposes and reasons. Physics verifies.**

AI is **never** treated as the source of truth for numerical engineering results. The deterministic physics solver is the sole authority for:

* **Forces & Moments:** Static equilibrium, support reactions, shear force $V(x)$, bending moment $M(x)$
* **Torque & Power:** $P = T \cdot \omega$, internal torque distribution $T(x)$
* **Stress Analysis:** Bending $\sigma = \frac{My}{I}$, torsion $\tau = \frac{Tr}{J}$, transverse shear, combined multiaxial Von Mises $\sigma_{vm} = \sqrt{\sigma_b^2 + 3\tau^2}$, principal stresses $\sigma_1, \sigma_2$
* **Stress Concentrations:** Peterson & Shigley shoulder step fillets ($D/d$, $r/d$), keyways (sled-runner & profile), retaining ring grooves, notch sensitivity $q$, fatigue stress concentration $K_f$
* **Deflection & Slope:** Numerical Euler-Bernoulli integration $\frac{d^2 v}{dx^2} = \frac{M(x)}{E \cdot I(x)}$ along stepped diameter shafts
* **Fatigue Analysis:** Marin endurance modification factors ($k_a, k_b, k_c, k_d, k_e$), modified endurance limit $S_e$, multiaxial Modified Goodman, Gerber, ASME-Elliptic, and Soderberg criteria
* **Lifecycle Prediction:** S-N Basquin curve calculations ($N_f$) and Palmgren-Miner cumulative damage
* **Parametric CAD:** Automatic generation of 3D OpenSCAD (`.scad`) source scripts with WebGL interactive visualizer
* **Engineering Reports:** Audit-ready calculation sheets in interactive HTML, scalable SVG diagrams, and Markdown

---

## 2. Architecture Overview

```text
                  ┌───────────────────────────────┐
                  │          USER / UI            │
                  └───────────────┬───────────────┘
                                  │
                                  ▼
                  ┌───────────────────────────────┐
                  │        AI ORCHESTRATOR        │
                  │   Natural Language Parser     │
                  │   Assumption Audit Manager    │
                  │   Design Critic & Copilot     │
                  └───────────────┬───────────────┘
                                  │
                                  ▼
                  ┌───────────────────────────────┐
                  │       ENGINEERING MODEL       │
                  │   Shaft Segments & Keyways    │
                  │   Supports & Loads            │
                  │   Materials & Constraints     │
                  └───────────────┬───────────────┘
                                  │
                                  ▼
                  ┌───────────────────────────────┐
                  │    DETERMINISTIC PHYSICS      │
                  │   Equilibrium & Reactions     │
                  │   Bending & Torsional Stress  │
                  │   Euler-Bernoulli Deflection  │
                  │   Marin & Goodman Fatigue     │
                  └───────┬───────────────┬───────┘
                          │               │
                          ▼               ▼
    ┌───────────────────────────┐   ┌───────────────────────────┐
    │    OPTIMIZATION ENGINE    │   │      OPENSCAD ENGINE      │
    │   Min Mass / Min Cost     │   │   Parametric .scad Code   │
    │   Standardized Diameters  │   │   Three.js WebGL 3D Mesh  │
    └─────────────┬─────────────┘   └─────────────┬─────────────┘
                  │                               │
                  └───────────────┬───────────────┘
                                  │
                                  ▼
                  ┌───────────────────────────────┐
                  │      VERIFIED DELIVERABLES    │
                  │   Interactive Web Dashboard   │
                  │   Audit Calculation Report    │
                  │   Downloadable OpenSCAD (.scad)
                  └───────────────────────────────┘
```

---

## 3. Quick Start (Terminal CLI)

Type what you want in plain words. The CLI automatically calculates all physics forces and writes the manufactured CAD solid files (`.step`, `.stl`, `.scad`) and HTML calculation reports.

### 3.1 Direct One-Liner Prompts

#### Design a 4-Leg Armchair with 2 Arms:
```bash
python cli.py "design a chair with 4 splayed legs and 2 armrests, steel, 1400 N seat load"
```
* Solves static equilibrium, 4-leg floor reactions, column buckling ($P_{cr}$), and 3D frame FEA (6 DOFs/node).
* Generates `Project/chair/chair.step` (Multi-Body Solid Assembly), `chair.stl`, `chair.scad`, and `chair_report.html`.

#### Design a Stepped Machine Shaft:
```bash
python cli.py "design a stepped shaft 500 mm long, 30 mm bearing seats, power 10 kW at 1500 rpm, with a keyway at center"
```
* Solves transmitted torque, shear force, bending moments, Goodman fatigue, and bearing life.
* Generates `Project/shaft/shaft.step`, `shaft.stl`, `shaft.scad`, `shaft_blueprint.svg`, and `shaft_report.html`.

#### Design a Spur / Helical Gear Transmission (AGMA 2001-D04 / ISO 6336):
```bash
python cli.py "design a spur gear pair for 15 kW at 1500 rpm, steel"
```
* Solves pitch line velocity, tangential/radial/axial forces, Lewis bending stress, and AGMA contact pitting fatigue.
* Generates parametric OpenSCAD 3D solid and 2D technical manufacturing blueprint.

#### Design a Helical Spring (DIN 2089 / Shigley):
```bash
python cli.py "helical compression spring for 200 N force, 3mm wire"
```
* Solves Wahl curvature factor $K_w$, torsional shear stresses, spring rate $k$, solid clash height, and column buckling.

#### Synthesize Custom Mechanisms & Fasteners on the Fly:
```bash
python cli.py "24mm acme lead screw with 8 kN axial load"
python cli.py "bolted joint M16 class 10.9 with 40 kN load"
python cli.py "robotic gripper finger linkage with 120mm span, 150 N clamp force, aluminum 6061"
```

#### Solve 3D Space Frame & Truss FEA:
```bash
python cli.py "solve a 3D space frame tower under 3 kN wind load"
```
* Direct Stiffness Method (12x12 element stiffness, 3D direction cosines, Von Mises stresses).
* Generates `Project/space_frame/space_frame_report.html`.

### 3.2 Interactive Terminal Mode
Simply run without arguments to enter an interactive prompt:
```bash
python cli.py
# MDIE > design a chair with 4 legs and two arms
# MDIE > stepped shaft 600 mm long, 40 mm bearing seats
# MDIE > spur gear pair 20 teeth module 3 with 50 mm face width
```

---

## 4. Key Capabilities

### 4.1 Natural Language $\rightarrow$ Engineering Model
The AI parser extracts structured technical models from conversational queries:
```text
"Design a shaft that transmits 5 kW at 1500 rpm, supports a 200 N radial load at the center, weighs less than 5 kg, safety factor above 2, survives 10 million cycles."
```
Extracted structured model:
* **Power:** $5000\text{ W}$ ($5.0\text{ kW}$)
* **Rotational Speed:** $1500\text{ RPM}$ ($\omega = 157.08\text{ rad/s}$)
* **Nominal Torque:** $T = \frac{P}{\omega} = 31.83\text{ N}\cdot\text{m}$
* **Span & Supports:** Outboard bearings ($x_1 = 40\text{ mm}$, $x_2 = 360\text{ mm}$)
* **Loads:** $200\text{ N}$ point load at $x = 200\text{ mm}$
* **Constraints:** $SF_{yield} \ge 2.0$, $SF_{fatigue} \ge 1.5$, $\delta_{max} \le 1.0\text{ mm}$, $N_f \ge 10^7\text{ cycles}$

### 4.2 Engineering Assumption Manager
Every parameter is tracked with full audit transparency:
* `CONFIRMED`: Explicitly given by user.
* `ASSUMED`: Standard engineering default (e.g. machined finish $k_a$, 99% reliability $k_e = 0.814$).
* `ESTIMATED`: Initial rule-of-thumb estimate.
* `MISSING`: Flagged if essential boundary conditions are undefined.

### 4.3 AI Design Critic & Verification Loop
* Evaluates root causes: decomposes peak Von Mises stress into **Bending %** vs **Torsion %** vs **Stress Concentration $K_t$**.
* Explains tradeoffs: *"Bending is the limiting condition (82% of stress); increasing shaft diameter or narrowing bearing span yields high stress reduction ($1/d^3$)."*
* **AI Safety Override:** If AI asserts a design is safe while physics calculates $SF < 1.0$, the system issues a hard override:
  ```text
  SAFETY OVERRIDE: FAIL
  AI recommendation conflicts with physics result.
  Physics solver takes precedence.
  ```

### 4.4 OpenSCAD 3D Engine
* Generates standard OpenSCAD `.scad` scripts for:
  * Stepped cylindrical segments with smooth transitions.
  * DIN 6885 / ANSI standard keyway cuts (`difference()` operations).
  * Bearing journals and mounting shoulders.
  * Visual highlights: metallic steel body, golden bearing seats, and high-stress plane marker.
* In-browser real-time 3D rendering powered by Three.js WebGL.

### 4.5 Parametric Optimization
* **Min Mass Optimizer:** Searches standardized shaft diameters ($12\text{ mm}$ to $120\text{ mm}$) to find the lightest geometry satisfying all constraints simultaneously.
* **Tradeoff Matrix:** Explores multi-candidate comparisons (Candidates A, B, C...) across various alloy steels and aluminum alloys with mass and safety factor evaluations.

---

## 5. Materials Database

Curated mechanical properties from standard engineering references (Shigley, ASM):

| Material ID | Name | Category | $S_y$ (MPa) | $S_{ut}$ (MPa) | $E$ (GPa) | $\rho$ ($\text{kg/m}^3$) | Cost Index |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `AISI_1018_CD` | AISI 1018 Cold Drawn | Carbon Steel | 370 | 440 | 205 | 7,850 | 1.0 |
| `AISI_1045_CD` | AISI 1045 Cold Drawn | Carbon Steel | 530 | 625 | 206 | 7,850 | 1.2 |
| `AISI_1045_QT` | AISI 1045 Q&T (540°C) | Carbon Steel | 620 | 770 | 206 | 7,850 | 1.5 |
| `AISI_4140_QT` | AISI 4140 Chromoly Q&T | Alloy Steel | 850 | 1,020 | 210 | 7,850 | 2.3 |
| `AISI_4340_QT` | AISI 4340 Ni-Cr-Mo | Alloy Steel | 1,100 | 1,280 | 210 | 7,850 | 3.8 |
| `AISI_304_SS` | AISI 304 Stainless | Stainless Steel | 215 | 505 | 193 | 8,000 | 3.5 |
| `AL_6061_T6` | Aluminum 6061-T6 | Aluminum | 276 | 310 | 68.9 | 2,700 | 2.8 |
| `AL_7075_T6` | Aluminum 7075-T6 | Aluminum | 503 | 572 | 71.7 | 2,810 | 5.2 |
| `TI_6AL_4V` | Titanium Grade 5 | Titanium | 880 | 950 | 113.8 | 4,430 | 18.0 |
| `BRONZE_C93200` | SAE 660 Bearing Bronze| Copper Alloy | 140 | 240 | 100 | 8,930 | 4.2 |

---

## 6. Test Suite

Run all verification tests:
```bash
python -m pytest tests/ -v
```
Includes:
* `test_equilibrium.py`: Reactions for simply-supported and cantilever systems.
* `test_stress_deflection.py`: Bending, torsion, Peterson $K_t$, and Euler-Bernoulli deflection.
* `test_fatigue.py`: Marin factors, endurance limit, and lifecycle predictions.
* `test_end_to_end.py`: Full workflow from natural language prompt to report generation.

---

## 7. License

MIT License. Designed for computational mechanical engineering and machine design intelligence.
