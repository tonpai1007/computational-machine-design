# MDIE Repository Status – Overview

## Repository location
`C:\codework\computational-machine-design`

## Folders & key files
- `Makefile` – targets: `slides`, `clean`, `publish`
- `.github\workflows\build-slides.yml` – GitHub Actions CI
- `.vscode\tasks.json` – VS Code tasks (build, clean, publish)
- `Project\chair\`
  - `armchair_slides.md` – Markdown source for Reveal.js slides (complete)
  - `armchair*` – placeholder for generated CAD files
  - `Report_armchair.docx` – placeholder for docx report
- `revealjs\` – Reveal.js framework (`npm install revealjs/revealjs`)
- `ai\` – stub prompt‑parsing package
- `physics\` – stub hand‑calc scripts
- `cad\` – CAD generation utilities (stub)
- `reporting\` – docx report generator (stub)
- `convert\` – optional conversion utilities

## What is already complete
- **Slide‑deck pipeline**: `armchair_slides.md` → Reveal.js HTML via `marp --revealjs`. Makefile, Actions and VS Code tasks all work.
- **Orchestration glue**: `Makefile`, Actions, tasks define the order of operations.
- **Conventions**: SI units (mm, N, MPa), Pydantic‑style JSON specs, MDIE colour palette (`#ffffff` / `#0f172a`).
- **Reveal.js integration**: Marp‑Reveal.js plugin configured; slide HTML can be opened in a browser.

## What is still missing (high‑level)
- AI prompt → JSON parser (stub)
- Physics hand‑calc engine (stub)
- OpenSCAD parametric models (stub)
- Docx report generator (stub)
- Full orchestration chain that connects the above stages

These gaps are described in the accompanying `ROADMAP.md` file (see next section).

---
*End of Overview*