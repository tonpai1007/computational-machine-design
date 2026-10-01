# MDIE Agent Guidelines & Project Instructions

You are working on the **Machine Design Intelligence Engine (MDIE)**, an AI-assisted computational engineering platform for machine design, structural analysis, 3D parametric CAD, and verified engineering reports.

---

## Core Directives

### 1. Physics Determinism is Absolute
- **AI proposes, physics calculates and verifies.**
- Never estimate, guess, or hallucinate stress values, safety factors, deflections, or reaction forces in responses or documentation.
- All numerical engineering conclusions must come from deterministic solver executions in [`physics/`](file:///c:/codework/computational-machine-design/physics/).
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
  .venv\Scripts\python.exe -m pytest
  ```
  *(Prefer the project-local `.venv` interpreter. Using the ambient `python`
  on Windows may fail to resolve the root packages, and a bare `pytest` may
  land in the wrong environment entirely.)*
- Keep all unit and integration tests passing (100% green) before concluding any code changes.
- Ship a regression test with every bug fix — one that fails without the fix.
- Full specification: [`.agents/rules/testing-and-dev.md`](file:///c:/codework/computational-machine-design/.agents/rules/testing-and-dev.md).
- Execution protocol (batching, ground-truth dumps, no mid-task narration): [`.agents/rules/agent-workflow.md`](file:///c:/codework/computational-machine-design/.agents/rules/agent-workflow.md).

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
- The primary user interface is the **`computational-machine-design` CLI** (console script from `pyproject.toml`, or `python -m cli`; `computational-machine-design.bat` wraps the module form) and direct Python library workflows.
- Entry point is [`cli/`](file:///c:/codework/computational-machine-design/cli/): `app.py` holds argparse dispatch, `designers.py` the per-domain prompt handlers, `viewers.py` CAD viewer detection. Do not add a second root-level `cli.py`.
- Subcommands: free-form prompt, `chair`/`bracket`, `shaft`, `convert`, `drawings`, `report`, `view`, `info`.
- All runs must output directly to local files in `Project/<project_name>/`:
  - **`.step`** for ISO-10303 CAD solid assembly
  - **`.stl`** for watertight sliced 3D printing
  - **`.scad`** for parametric OpenSCAD scripts
  - **`.html`** for self-contained engineering reports
  - Rich terminal tables with forces, stresses, safety factors, and pass/fail verdicts.

### 5.1 Package Layout
**The repository root IS MDIE.** There is no enclosing `mdie/` wrapper package —
all 13 packages live at the top level and import each other directly
(`from core.models import ...`, not `from mdie.core.models import ...`).

Keep responsibilities separated - do not merge these back together:

| Package | Owns |
| --- | --- |
| `core` | geometry primitives, units, the design data model |
| `cad` | solids, STEP/STL export, OpenSCAD emission |
| `components` | standard component sizing |
| `physics` | stress, deflection, fatigue, buckling, FEA, frame solver |
| `drafting` | dimensioned drawing sheets, FBD plots, Mermaid diagrams |
| `reporting` | HTML/Markdown engineering report generators |
| `convert` | the file converter: documents, CAD solids, drawing sheets |
| `cli` | command line interface (entry point; `__version__` lives in `core`) |
| `ai` | NL prompt parsing, domain classification, LLM routing, design critic, assumption audit |
| `materials` | the material property database and derived elastic/shear moduli |
| `optimizer` | parametric design search over candidate geometries |
| `integrations` | bridges to external toolchains (e.g. the learning-tools project) |

- `drafting` must stay **model-derived**: read dimensions back off the actual primitives, never restate input parameters. The drawing regression tests enforce this.
- `convert` must degrade gracefully when an optional dependency is missing - probe with `convert.registry.has_dependency` and raise a `ConversionError` that names the tool, rather than an `ImportError`.
- Do not reintroduce an `mdie/` wrapper directory, and do not reintroduce `mdie/reports/` (long gone; split into `drafting/` and `reporting/`).

### 6. Dual-Tier Engineering Report Standards
Engineering deliverables maintain a strict white-paper aesthetic (`#ffffff`, `#0f172a` ink, printable A4):
- **Tier 1 (Core Professional Calculation Sheet):** Clean, concise calculation sheet for engineers (`<part>_report.html`) with FBD, equilibrium, and buckling tables. No student/homework data.
- **Tier 2 (University Assignment Project Dossier):** Complete course assignment report (`academic_assignment_report.html`) with official Thai/English cover page, Table of Contents, 3D CAD render, BOM, 3D FEA summary, and academic sign-off block.
- Full specification: [`.agents/rules/Engineerview.md`](file:///c:/codework/computational-machine-design/.agents/rules/Engineerview.md).

### 7. Code & Pydantic Conventions
- MDIE uses **Pydantic v2**. Use `.model_dump()` and strictly avoid deprecated `.dict()`.
- Explicitly declare mechanical units in Pydantic `Field(..., description="...")` tags.
