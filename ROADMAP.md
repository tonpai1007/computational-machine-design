# MDIE Repository Roadmap – What’s Missing & How to Proceed

## 1. AI prompt → JSON parser
**Location**: `ai/` (e.g., `ai/parser.py`)
**Goal**: Parse a free‑form design prompt and emit a Pydantic `DesignSpec` object, then dump `design_spec.json`.
**Minimal implementation**:
- Extract these fields from the prompt:
  - `load_n` (vertical service load in N)
  - `safety_factor` (target ≥ 3)
  - `endurance_cycles` (target ≥ 1 × 10⁶)
  - `material` (e.g., “AISI 1018”)
  - `tube_od` / `tube_id` arrays (leg, lower‑bracing, arm‑rest)
- Return a `DesignSpec` model and write `design_spec.json`.
**Next step**: Run a quick test:
```powershell
python -c "from ai.parser import from_prompt; from_prompt('Design a …'); # produces design_spec.json"
```

## 2. Physics hand‑calc engine
**Location**: `physics/handcalc.py`
**Goal**: Read `design_spec.json`, compute:
- Axial stress `σ = F/A` for each member
- Column slenderness and decide Euler vs. J.B. Johnson
- Endurance limit `Se` using the \(K_a K_b K_c K_d K_e\) factors
- Safety factors on stress and on endurance
- Recommend member sizes/lengths
**Output**: `spec_calc.json` with stresses, safety factors, and recommended tube lengths/IDs.
**Minimal implementation**:
```python
import json, math
def run(spec):
    # 1. axial stress
    sigma = spec['load_n'] / math.pi*(spec['tube_od']**2 - spec['tube_id']**2)/4
    # 2. slenderness (example)
    lk = spec['lengths'] / (0.7*spec['tube_od'])
    # 3. decide Euler/Johnson (simplified)
    # 4. endurance factors Ka,Kb,Kc,Kd,Ke (use typical values)
    # 5. write spec_calc.json
    with open('spec_calc.json','w') as f:
        json.dump({'sigma':sigma,'safety_factor':3,'endurance_ok':True}, f)
run(json.load(open('design_spec.json')))
```
**Next step**: Execute `python -m physics.handcalc --spec design_spec.json --out spec_calc.json` and verify the JSON contents.

## 2‑3. OpenSCAD parametric models
**Location**: `cad/` – four sub‑assembly scripts (leg columns, seat rails, lower bracing, arm‑rest struts).
**What they must produce**:
- `armchair.scad` (source)
- `armchair.step` (STEP)
- `armchair.stl` (mesh)
- `armchair.svg` (2‑D blueprint)
**Coordinate convention** (MDIE): X‑long, radial in Y‑Z plane for shafts; ground plane X‑Y, height +Z for structures.
**Minimal implementation**:
Create four tiny `.scad` files that extrude a tube given `od`, `id`, `length`. Then a `cad/generate.py` wrapper that calls:
```bash
openscad -o armchair.scad armchair.scad
openscad -o armchair.step -d step armchair.scad
openscad -o armchair.stl -d stl armchair.scad
openscad -o armchair.svg -d svg armchair.scad
```
**Next step**: After writing the `.scad` files, run `cad generate --spec spec_calc.json --output Project/chair/armchair` and verify the four output files appear.

## 4. Docx report generator
**Location**: `reporting/generate.py` (or a template `.docx`).
**Goal**: Read `spec_calc.json`, produce a Tier‑1 white‑paper style `.docx`:
- Title, project info
- FBD and equilibrium table
- Safety‑factor table (stress, Se, Sf)
- Endurance‑life summary
- References (four REF PDFs + assignment report)
**Styling**: background `#ffffff`, text `#0f172a`, A4 page.
**Minimal implementation** (using `python-docx`):
```python
from docx import Document
from docx.shared import Pt, RGBColor
doc = Document()
style = doc.styles['Normal']
font = style.font
font.color.rgb = RGBColor(0x0f,0x17,0x2a)
font.size = Pt(11)
# ... fill tables from spec_calc.json ...
doc.save('Report_armchair.docx')
```
**Next step**: After the file exists, verify `Project/chair/Report_armchair.docx` opens with the correct style.

## 5. Orchestration updates
**Files**: `run_pipeline.ps1`, `Makefile`
**What to change**: Add dependencies so `make all` (or the PowerShell script) runs:
1. `design_spec.json` from AI parser
2. `spec_calc.json` from physics
3. CAD models from `cad generate`
4. Docx report from `reporting generate`
5. Slide deck (already functional)
**Example Makefile fragment**:
```makefile
design_spec.json: ai/parser.py
	python ai/parser.py --prompt "Design a …"

spec_calc.json: design_spec.json physics/handcalc.py
	python physics/handcalc.py --spec design_spec.json --out spec_calc.json

cad.models: spec_calc.json cad/generate.py
	cad generate --spec spec_calc.json --output Project/chair/armchair

report: spec_calc.json reporting/generate.py
	reporting generate --spec spec_calc.json --output Project/chair/Report_armchair.docx

slides: Project/chair/armchair_slides.md
	make slides

all: design_spec.json spec_calc.json cad.models report slides
```
**Next step**: After each piece is functional, run `make all` and confirm every target produces its artefact.

## 6. Full end‑to‑end test script
**File**: `run_pipeline.ps1`
**Purpose**: One‑command build & verify.
```powershell
param([string]$Prompt = "Design a portable MDIE Ergonomic Armchair …")
# 1. AI parser
computational-machine-design prompt --text $Prompt | Out-File design_spec.json
# 2. Physics
python -m physics.handcalc --spec design_spec.json --out spec_calc.json
# 3. CAD
cad generate --spec spec_calc.json --output Project/chair/armchair
# 4. Docx report
reporting generate --spec spec_calc.json --output Project/chair/Report_armchair.docx
# 5. Slides
marp --revealjs "Project/chair/armchair_slides.md" --output ".reveal.js/armchair_slides.html" --theme "white" --transition "fade"
Write-Host "✅ Pipeline finished."
Write-Host "• CAD models in Project/chair/
• Report in Project/chair/Report_armchair.docx
• Slides in .reveal.js/armchair_slides.html"
```
**Next step**: After the above stubs are functional, execute `.\run_pipeline.ps1` and verify all artefacts appear.

---
*Roadmap ends here. Each bullet can be tackled independently; once a piece works, the downstream `make`/`pipeline` targets will automatically pick up the generated artefacts.*