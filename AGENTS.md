# MDIE Agent Guidelines & Project Instructions

You are working on the **Machine Design Intelligence Engine (MDIE)**, an AI-assisted computational engineering platform for machine design, structural analysis, 3D parametric CAD, and verified engineering reports.

---

## Core Directives

### 1. Physics Determinism is Absolute
- **AI proposes, physics calculates and verifies.**
- Never estimate, guess, or hallucinate stress values, safety factors, deflections, or reaction forces in responses or documentation.
- All numerical engineering conclusions must come from deterministic solver executions in [`mdie/physics/`](file:///c:/codework/computational-machine-design/mdie/physics/).
- Full specification: [`.agents/rules/physics-authority.md`](file:///c:/codework/computational-machine-design/.agents/rules/physics-authority.md).

### 2. Standard Units Convention
All internal calculations and models strictly use the mechanical engineering SI subset:
- **Dimensions & Length:** Millimeters ($mm$)
- **Forces:** Newtons ($N$)
- **Moments & Torque:** Newton-millimeters ($N \cdot mm$) or Newton-meters ($N \cdot m$) explicitly tagged
- **Stresses & Pressures:** Megapascals ($MPa = N/mm^2$)
- **Modulus of Elasticity ($E, G$):** Megapascals ($MPa$)
- **Density:** $g/cm^3$ or $kg/m^3$ with conversion

### 3. Testing and Command Execution
- Always invoke test suites with:
  ```powershell
  python -m pytest
  ```
  *(Using plain `pytest` on Windows may fail to resolve the root `mdie` module).*
- Keep all unit and integration tests passing (100% green) before concluding any code changes.
- Full specification: [`.agents/rules/testing-and-dev.md`](file:///c:/codework/computational-machine-design/.agents/rules/testing-and-dev.md).

### 4. CAD & Geometry Standards
- **Coordinate Conventions:**
  - **Shafts & Transmissions:** Longitudinal axis along $+X$, radial dimensions in $Y$-$Z$ plane.
  - **Frames, Structures & Stands (e.g. Chairs):** Ground plane $X$-$Y$ ($Z=0$), vertical height along $+Z$.
- **Multi-Format Generation Pipeline:**
  - Provide parametric **OpenSCAD (`.scad`)** for lightweight, human-readable CSG preview.
  - Provide **STEP (`.step`)** for ISO 10303 manufacturing interchange.
  - Provide **STL (`.stl`)** for watertight 3D print slicing.
  - Provide **Vector Blueprints (`.svg`)** for ISO 128 / ANSI Y14.5 manufacturing drawings.
- Full specification: [`.agents/rules/cad-and-fea.md`](file:///c:/codework/computational-machine-design/.agents/rules/cad-and-fea.md).

### 5. Primary Interface: CLI & Python Scripts (No Web Interface)
- **Do NOT rely on or prioritize web browser interfaces.**
- The primary user interface is the **`mdie` CLI** (console script from `pyproject.toml`, or `python -m mdie`; `mdie.bat`/`cli.bat` wrap the module form) and direct Python library workflows.
- Entry point is [`mdie/cli/`](file:///c:/codework/computational-machine-design/mdie/cli/): `app.py` holds argparse dispatch, `designers.py` the per-domain prompt handlers, `viewers.py` CAD viewer detection. Do not add a second root-level `cli.py`.
- Subcommands: free-form prompt, `chair`/`bracket`, `shaft`, `convert`, `drawings`, `report`, `view`, `info`.
- All runs must output directly to local files in `Project/<project_name>/`:
  - **`.step`** for ISO-10303 CAD solid assembly
  - **`.stl`** for watertight sliced 3D printing
  - **`.scad`** for parametric OpenSCAD scripts
  - **`.html`** for self-contained engineering reports
  - Rich terminal tables with forces, stresses, safety factors, and pass/fail verdicts.

### 5.1 Package Layout
Keep responsibilities separated - do not merge these back together:

| Package | Owns |
| --- | --- |
| `mdie/core` | geometry primitives, units, the design data model |
| `mdie/cad` | solids, STEP/STL export, OpenSCAD emission |
| `mdie/components` | standard component sizing |
| `mdie/physics` | stress, deflection, fatigue, buckling, FEA, frame solver |
| `mdie/drafting` | dimensioned drawing sheets, FBD plots, Mermaid diagrams |
| `mdie/reporting` | HTML/Markdown engineering report generators |
| `mdie/convert` | the file converter: documents, CAD solids, drawing sheets |
| `mdie/cli` | command line interface |

- `mdie/drafting` must stay **model-derived**: read dimensions back off the actual primitives, never restate input parameters. The drawing regression tests enforce this.
- `mdie/convert` must degrade gracefully when an optional dependency is missing - probe with `mdie.convert.registry.has_dependency` and raise a `ConversionError` that names the tool, rather than an `ImportError`.
- The former `mdie/reports/` package no longer exists; it was split into `mdie/drafting/` and `mdie/reporting/`.

### 6. Dual-Tier Engineering Report Standards
Engineering deliverables maintain a strict white-paper aesthetic (`#ffffff`, `#0f172a` ink, printable A4):
- **Tier 1 (Core Professional Calculation Sheet):** Clean, concise calculation sheet for engineers (`<part>_report.html`) with FBD, equilibrium, and buckling tables. No student/homework data.
- **Tier 2 (University Assignment Project Dossier):** Complete course assignment report (`academic_assignment_report.html`) with official Thai/English cover page, Table of Contents, 3D CAD render, BOM, 3D FEA summary, and academic sign-off block.
- Full specification: [`.agents/rules/Engineerview.md`](file:///c:/codework/computational-machine-design/.agents/rules/Engineerview.md).

### 7. Code & Pydantic Conventions
- MDIE uses **Pydantic v2**. Use `.model_dump()` and strictly avoid deprecated `.dict()`.
- Explicitly declare mechanical units in Pydantic `Field(..., description="...")` tags.
