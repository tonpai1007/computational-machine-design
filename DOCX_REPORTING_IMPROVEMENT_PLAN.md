# DOCX Reporting & Document Intelligence Improvement Plan

## Goal

Turn the current reporting pipeline into a document-aware engineering workflow that can:

- read Word files reliably
- understand the document structure and context
- preserve tables, headings, captions, and embedded figures
- insert and update images within generated reports
- feed extracted document intelligence into the MDIE design and reporting pipeline

---

## Current State

The project already supports:

- HTML to DOCX conversion
- DOCX to markdown/text extraction
- basic table parsing
- inline image insertion into generated DOCX files
- simple document context extraction via the converter layer

This is a solid base, but it is still limited to shallow document understanding compared with a true report analysis workflow.

---

## Key Gaps

1. Semantic structure is not fully modeled
   - paragraphs, headings, captions, tables, and images are treated separately
   - there is no unified document model that links surrounding context to figures/tables

2. Figure and caption relationships are weak
   - images can be inserted, but there is no robust association between a figure, its caption, and nearby narrative text

3. Table understanding is basic
   - tables are parsed as raw rows but not interpreted as engineering data structures

4. No document-level reasoning layer
   - the system can extract text but does not yet synthesize meaning like: what is the design objective, what data is important, what assumptions are present, and what should be highlighted in the report

5. No OCR / scanned-document fallback
   - the current approach works best on native DOCX content; it does not yet handle scanned PDFs or image-heavy docs as well as an OCR-driven pipeline would

6. No reusable report-aware API
   - there is no clean abstraction for: document load -> context parse -> summary -> image insertion -> revised output

---

## Target Architecture

The strongest system for this repo is not a single “agentic DOCX tool.” It is a hybrid pipeline with a canonical structured model at the center.

### 1. Canonical Document Model (authoritative source of truth)

The engine should normalize source content into a reusable document model before any editing or reasoning happens.

```python
context = extract_document_context(path)
```

This should return a normalized object with:

- title
- headings
- paragraphs
- lists
- tables
- figures
- captions
- references
- section summaries
- semantic metadata

The important part is that the model, not the raw file format, becomes the control plane.

### 2. Hybrid parse + enrichment layer

Use external document tools only as enrichment, not as the primary system-of-record:

- Docling / Unstructured / similar extractors can improve semantic structure recognition
- they are useful for layout understanding and rough segmentation
- they should feed the canonical model, not replace the write-back layer

This is the crucial design choice: semantic extraction helps the agent understand the document, but the actual edit path still belongs to the repo-native writer.

### 3. AI reasoning over structured content

Represent the document as structured objects instead of plain strings:

- `DocumentSection`
- `ParagraphBlock`
- `TableBlock`
- `FigureBlock`
- `CaptionBlock`
- `ReferenceLink`

This makes it easier to reason across the whole report rather than each block in isolation.

The agent should operate on this model to decide:

- where to insert a figure
- which heading should receive a new subsection
- which caption should be updated
- how to preserve engineering narrative structure
- which values are relevant to design context

### 4. Exact write-back layer for Word files

This repo already has the right core for the operational path:

- the actual file editing is best done directly through the Word backend
- figure insertion, caption updates, and section-aware placement should stay in the `python-docx`-based writer layer
- the repo’s current report editor is the correct foundation for this exact write-back behavior

This prevents a generic parser from becoming the only source of truth and keeps final document edits precise and stable.

### 5. Rendered output layer: HTML + PDF + DOCX

The final pipeline should separate responsibilities:

- HTML: AI-readable, inspectable, semantically structured representation
- PDF: publication / archival output
- DOCX: editable office-native output for users and Word workflows

This is stronger than trying to make a single format do everything.

### 6. Engineering report semantics

For MDIE specifically, the model should also capture engineering context:

- design objective
- machine part or assembly being analyzed
- assumptions and constraints
- key safety factors
- material choices
- critical dimensions
- table data for design sizing
- figures used as validation or supporting evidence

This creates a document model that is usable by design agents rather than a flat text blob.

### First-scope recommendation: college report MVP (MT/REF style)

For the first phase, we should not build a general-purpose document agent. We should target the common college engineering report pattern:

- title page or report heading
- objective / purpose
- assumptions and design conditions
- method or setup
- results and discussion
- figures and captions
- conclusion and recommendation
- appendices or references

This is enough for the majority of MT/REF-style submissions and is much easier to make reliable.

The practical architecture for this MVP is:

- parse DOCX into a lightweight structured model
- detect common section headings and narrative blocks
- keep figures, captions, and tables attached to the right section
- extract objective, assumptions, results, and conclusion
- write updated content back to DOCX accurately
- optionally render HTML for review, but keep DOCX as the master output

That is the correct architecture for the first version: parse -> structure -> extract -> update -> render.

It is intentionally simpler than a full multi-tool document intelligence engine, while still solving the real engineering workflow problem.

---

## Proposed Modules

### A. `convert/document_intelligence.py`

Responsibilities:

- parse DOCX content into structured blocks
- detect headings and semantic sections
- collect captions and image references
- merge paragraphs with adjacent figures
- build a reusable summary object

### B. `convert/report_editor.py`

Responsibilities:

- insert inline images
- update captions
- add figures to existing sections
- preserve layout and paragraph flow
- maintain context around edited blocks

### C. `convert/report_context.py`

Responsibilities:

- normalize report metadata
- infer section types
- map engineering data fields
- prepare structured prompt input for the AI design pipeline

### D. `ai/docx_reader.py`

Responsibilities:

- convert extracted document context into machine-readable engineering assumptions
- feed relevant report sections to downstream calculation or design agents
- summarize design intent and constraints for generation

---

## Recommended Improvement Roadmap

### Phase 0: College report MVP (target first)

- support standard report sections: objective, assumptions, results, conclusion
- preserve paragraphs, figures, captions, and simple tables
- extract report context with a lightweight section-aware model
- write back to DOCX without breaking layout
- add regression tests for MT/REF-style documents

### Phase 1: Stabilize the core document model

- finish unified parsing of paragraphs, headings, tables, and images
- normalize block structure
- keep caption/image associations stable
- add regression tests for mixed documents

### Phase 2: Add focused editing tools

- support inserting images inline into existing paragraphs
- support caption replacement and update
- support adding tables into sections without disrupting flow
- support append/replace behavior for report sections

### Phase 3: Add contextual understanding

- classify section types such as objective, assumptions, results, conclusion
- detect engineering language patterns like loads, dimensions, materials, factors of safety
- extract values from tables into machine-readable data

### Phase 4: Connect to the design engine

- pass extracted context into AI design routines
- use document content as input to a design brief
- allow a generated report to be updated based on new calculations

### Phase 5: Quality and validation

- verify Word output remains valid and readable in Microsoft Word
- test for image sizing, caption placement, and table preservation
- add end-to-end report generation checks from DOCX input to generated output

---

## Suggested API Surface

```python
from convert.document_intelligence import extract_document_context
from convert.report_editor import insert_report_figure, update_report_caption

context = extract_document_context("specification.docx")

report_path = insert_report_figure(
    "report.docx",
    "figure.png",
    caption="Figure 1: Bearing layout",
    section_heading="Design Overview",
    width=180,
)
```

This pattern is easier for the rest of the system to consume and scales better than just ad hoc file manipulation.

---

## Success Criteria

The system is considered improved when it can:

- ingest a DOCX file and produce a structured understanding of its content
- preserve or correctly reconstruct engineering tables, captions, and figures
- insert figures into report content without breaking formatting
- use parsed document context as a meaningful input to generation and reporting flows
- handle both standard text documents and engineering specimen reports

---

## Recommended Next Step

The immediate next improvement should be:

1. unify the DOCX extraction helpers into a dedicated `document_intelligence` module
2. add section-aware parsing and figure-caption linking
3. expose a standard API that the MDIE design engine can call

This is the most valuable improvement because it turns raw Word files into usable engineering context instead of just text blobs.
