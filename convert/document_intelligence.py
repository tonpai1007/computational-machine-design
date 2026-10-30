from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DocumentSection:
    heading: str
    paragraphs: list[str] = field(default_factory=list)
    tables: list[list[list[str]]] = field(default_factory=list)
    images: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    semantic_tags: list[str] = field(default_factory=list)


@dataclass
class FigureReference:
    index: int
    caption: str = ""
    section_heading: str = "Document"
    image_meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class FigureLink:
    figure_index: int
    section_heading: str
    caption: str
    context_summary: str = ""


@dataclass
class EngineeringMetadata:
    objective: str = ""
    assumptions: list[str] = field(default_factory=list)
    conclusion: str = ""
    key_results: list[str] = field(default_factory=list)


@dataclass
class EvidenceLink:
    section_heading: str
    evidence_type: str
    summary: str
    reference: str = ""


@dataclass
class DocumentGraph:
    figures: list[FigureReference] = field(default_factory=list)
    figure_links: list[FigureLink] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    evidence_links: list[EvidenceLink] = field(default_factory=list)


@dataclass
class DocumentContext:
    path: str
    title: str
    full_text: str
    paragraphs: list[str]
    tables: list[list[list[str]]]
    images: list[dict[str, Any]]
    sections: list[DocumentSection]
    semantic_tags: list[str] = field(default_factory=list)


def _infer_semantic_tags(text: str) -> list[str]:
    """Extract a small, document-friendly set of keywords for semantic reasoning."""
    value = text.lower()
    candidates = [
        "design",
        "review",
        "fatigue",
        "stress",
        "safety",
        "bearing",
        "shaft",
        "load",
        "result",
        "assumption",
        "analysis",
        "conclusion",
    ]
    found = [token for token in candidates if token in value]
    return found or (value.split()[:3] if value else [])


def _section_summary(paragraphs: list[str], heading: str) -> str:
    parts = paragraphs[:3]
    if not parts:
        return heading
    summary = " ".join(p.strip() for p in parts if p.strip())
    return summary[:220]


def _as_keyword_list(values: list[str] | tuple[str, ...] | None) -> list[str]:
    items: list[str] = []
    for value in values or []:
        token = str(value).strip().lower()
        if token and token not in items:
            items.append(token)
    return items


def _figure_caption_from_paragraphs(paragraphs: list[str], index: int) -> str:
    for text in paragraphs:
        lowered = text.lower().strip()
        if lowered.startswith("figure ") or lowered.startswith("fig. "):
            return text.strip()
    if not paragraphs:
        return ""
    return paragraphs[min(index, len(paragraphs) - 1)] if len(paragraphs) > 0 else ""


def extract_engineering_metadata(context: DocumentContext) -> EngineeringMetadata:
    """Extract objective, assumptions, key results, and conclusion from section headings."""
    by_heading: dict[str, list[str]] = {}
    for section in context.sections:
        by_heading.setdefault(section.heading.lower(), [])
        by_heading[section.heading.lower()].extend(section.paragraphs)

    objective = ""
    assumptions: list[str] = []
    conclusion = ""
    key_results: list[str] = []

    for heading, paragraphs in by_heading.items():
        text = " ".join(paragraphs).strip()
        if not text:
            continue
        if "objective" in heading or "goal" in heading:
            objective = text
        elif "assum" in heading:
            assumptions.append(text)
        elif "conclusion" in heading or "recommend" in heading:
            conclusion = text
        elif "result" in heading or "analysis" in heading or "summary" in heading:
            key_results.append(text)

    if not objective and context.paragraphs:
        objective = context.paragraphs[0]
    if not conclusion and context.paragraphs:
        conclusion = context.paragraphs[-1]
    if not assumptions and context.full_text:
        for sentence in context.full_text.split("."):
            stripped = sentence.strip()
            if "assume" in stripped.lower() or "safety" in stripped.lower() or "material" in stripped.lower():
                assumptions.append(stripped)
    if not key_results and context.full_text:
        for sentence in context.full_text.split("."):
            stripped = sentence.strip()
            if any(word in stripped.lower() for word in ("stress", "fatigue", "load", "result", "allowable")):
                key_results.append(stripped)

    return EngineeringMetadata(
        objective=objective,
        assumptions=assumptions,
        conclusion=conclusion,
        key_results=key_results,
    )


def synthesize_report_summary(context: DocumentContext, graph: DocumentGraph | None = None) -> str:
    """Produce a compact section-aware summary of the report for downstream reasoning."""
    metadata = extract_engineering_metadata(context)
    summary_parts: list[str] = []

    if metadata.objective:
        summary_parts.append(f"Objective: {metadata.objective}")
    if metadata.assumptions:
        summary_parts.append(f"Assumptions: {'; '.join(metadata.assumptions[:3])}")
    if metadata.key_results:
        summary_parts.append(f"Results: {'; '.join(metadata.key_results[:3])}")
    if metadata.conclusion:
        summary_parts.append(f"Conclusion: {metadata.conclusion}")

    if not summary_parts and context.sections:
        for section in context.sections[:4]:
            text = " ".join(section.paragraphs).strip()
            if text:
                summary_parts.append(f"{section.heading}: {text[:180]}")

    if not summary_parts:
        return context.title or "Document summary unavailable."

    return " ".join(summary_parts)


def build_document_graph(context: DocumentContext) -> DocumentGraph:
    """Build a light document graph around sections, figures, and semantic keywords."""
    keywords = _as_keyword_list(context.semantic_tags)
    for section in context.sections:
        for tag in _as_keyword_list(section.semantic_tags):
            if tag not in keywords:
                keywords.append(tag)

    section_headings = [section.heading for section in context.sections]
    for heading in section_headings:
        for word in heading.lower().replace("-", " ").split():
            if len(word) > 3 and word not in keywords:
                keywords.append(word)

    figures: list[FigureReference] = []
    figure_links: list[FigureLink] = []
    evidence_links: list[EvidenceLink] = []
    for image_index, image in enumerate(context.images, start=1):
        caption = str(image.get("caption") or _figure_caption_from_paragraphs(context.paragraphs, image_index)).strip()
        section_heading = "Document"
        for section in reversed(context.sections):
            if section.paragraphs or section.images or section.tables:
                section_heading = section.heading
                break
        if context.sections and any(section.heading != "Document" for section in context.sections):
            for section in reversed(context.sections):
                if section.heading != "Document":
                    section_heading = section.heading
                    break
        figure = FigureReference(
            index=image_index,
            caption=caption,
            section_heading=section_heading,
            image_meta=image,
        )
        figures.append(figure)
        figure_links.append(
            FigureLink(
                figure_index=image_index,
                section_heading=section_heading,
                caption=caption,
                context_summary=_section_summary(
                    [*context.paragraphs[:3], caption] if caption else context.paragraphs[:3],
                    section_heading,
                ),
            )
        )

    for section in context.sections:
        text = " ".join(section.paragraphs).strip()
        if text:
            evidence_links.append(
                EvidenceLink(
                    section_heading=section.heading,
                    evidence_type="section",
                    summary=_section_summary(section.paragraphs, section.heading),
                    reference=section.heading,
                )
            )
        if section.images:
            evidence_links.append(
                EvidenceLink(
                    section_heading=section.heading,
                    evidence_type="figure",
                    summary=section.summary or section.heading,
                    reference="image",
                )
            )

    if not figures and context.sections:
        for section in context.sections:
            caption = _figure_caption_from_paragraphs(section.paragraphs, 1)
            if caption:
                figures.append(
                    FigureReference(
                        index=len(figures) + 1,
                        caption=caption,
                        section_heading=section.heading,
                        image_meta={},
                    )
                )
                figure_links.append(
                    FigureLink(
                        figure_index=len(figure_links) + 1,
                        section_heading=section.heading,
                        caption=caption,
                        context_summary=section.summary,
                    )
                )

    return DocumentGraph(
        figures=figures,
        figure_links=figure_links,
        keywords=keywords,
        evidence_links=evidence_links,
    )


def extract_document_context(path: str | Path) -> DocumentContext:
    """Unify the document model into title, sections, paragraphs, tables, and figures."""
    import docx

    from convert.documents import extract_docx_context

    doc_path = Path(path)
    raw = extract_docx_context(doc_path)
    document = docx.Document(str(doc_path))

    sections: list[DocumentSection] = []
    current_heading = "Document"
    current_paragraphs: list[str] = []
    current_tables: list[list[list[str]]] = []
    current_images: list[dict[str, Any]] = []

    first_heading: str | None = None

    for para in document.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        style = (para.style.name if para.style else "").lower()
        if style.startswith("heading"):
            if (
                current_heading != "Document"
                or current_paragraphs
                or current_tables
                or current_images
            ):
                sections.append(
                    DocumentSection(
                        heading=current_heading,
                        paragraphs=current_paragraphs[:],
                        tables=current_tables[:],
                        images=current_images[:],
                        summary=_section_summary(current_paragraphs[:], current_heading),
                        semantic_tags=_infer_semantic_tags(" ".join(current_paragraphs[:])),
                    )
                )
            current_heading = text
            if first_heading is None:
                first_heading = text
            current_paragraphs = []
            current_tables = []
            current_images = []
            continue

        if text.lower().startswith("figure ") or text.lower().startswith("fig. "):
            current_paragraphs.append(text)
            continue

        current_paragraphs.append(text)

    if (
        current_heading != "Document"
        or current_paragraphs
        or current_tables
        or current_images
    ):
        sections.append(
            DocumentSection(
                heading=current_heading,
                paragraphs=current_paragraphs[:],
                tables=current_tables[:],
                images=current_images[:],
                summary=_section_summary(current_paragraphs[:], current_heading),
                semantic_tags=_infer_semantic_tags(" ".join(current_paragraphs[:])),
            )
        )

    if not sections:
        sections.append(
            DocumentSection(
                heading="Document",
                paragraphs=raw["paragraphs"][:],
                tables=raw["tables"][:],
                images=raw["images"][:],
                summary=_section_summary(raw["paragraphs"][:], "Document"),
                semantic_tags=_infer_semantic_tags(" ".join(raw["paragraphs"][:])),
            )
        )

    title = first_heading or "Document"
    if not title and raw["paragraphs"]:
        title = raw["paragraphs"][0]

    semantic_tags = _infer_semantic_tags(raw["full_text"])
    return DocumentContext(
        path=str(doc_path),
        title=title,
        full_text=raw["full_text"],
        paragraphs=raw["paragraphs"],
        tables=raw["tables"],
        images=raw["images"],
        sections=sections,
        semantic_tags=semantic_tags,
    )


def _try_import_ocr() -> str | None:
    """Return the name of an importable OCR backend, or None."""
    for name, module in (
        ("pytesseract", "pytesseract"),
        ("docling", "docling.document_converter"),
    ):
        try:
            importlib.import_module(module)
        except ImportError:
            continue
        return name
    return None


def extract_document_context_ocr(path: str | Path) -> dict[str, Any]:
    """OCR fallback for scanned documents.

    Uses available OCR libraries (pytesseract or docling) to extract
    text from image-based PDFs or scanned documents.

    This is an ENRICHMENT layer - it feeds the canonical DocumentContext
    model but does NOT replace the native DOCX parsing pipeline.
    The native pipeline remains authoritative for native DOCX content.
    """
    from pathlib import Path

    from PIL import Image

    ocr_lib = _try_import_ocr()
    if ocr_lib is None:
        return {
            "full_text": "",
            "paragraphs": [],
            "tables": [],
            "images": [],
            "success": False,
            "note": "No OCR library available. Install pytesseract or docling for OCR support.",
        }

    doc_path = Path(path)

    if ocr_lib == "docling":
        try:
            from docling.document_converter import DocumentConverter  # type: ignore[import-not-found]
            converter = DocumentConverter()
            result = converter.convert(str(doc_path))
            text = result.text if hasattr(result, "text") else ""
            return {
                "full_text": text,
                "paragraphs": [text] if text else [],
                "tables": [],
                "images": [],
                "success": True,
            }
        except Exception as e:
            return {
                "full_text": "",
                "paragraphs": [],
                "tables": [],
                "images": [],
                "success": False,
                "note": f"docling OCR failed: {e}",
            }

    # pytesseract path
    try:
        import pytesseract  # type: ignore[import-not-found]
        image = Image.open(str(doc_path))
        text = pytesseract.image_to_string(image)
        return {
            "full_text": text,
            "paragraphs": [p for p in text.split("\n") if p.strip()],
            "tables": [],
            "images": [
                {
                    "source": str(doc_path),
                    "format": image.format or "Unknown",
                }
            ],
            "success": True,
        }
    except Exception as e:
        return {
            "full_text": "",
            "paragraphs": [],
            "tables": [],
            "images": [],
            "success": False,
            "note": f"pytesseract OCR failed: {e}",
        }


def enrich_document_context_with_ocr(
    path: str | Path, context: DocumentContext | None = None
) -> DocumentContext:
    """Enrich an existing DocumentContext with OCR-extracted text.

    If the native DOCX parse found little or no text, OCR can supplement it.
    The OCR result is merged but the native context remains authoritative.

    Parameters:
        path: Path to the DOCX file (used only if context is not provided)
        context: Optional pre-extracted context. If provided, this is used
                 instead of re-extracting from the file.
    """
    native = context if context is not None else extract_document_context(path)
    ocr = extract_document_context_ocr(path)

    if not ocr["success"]:
        return native

    merged_paragraphs = list(native.paragraphs)
    if ocr["full_text"] and not native.full_text:
        merged_paragraphs = list(ocr["paragraphs"])
    elif native.full_text and ocr["full_text"]:
        merged_paragraphs = native.paragraphs + list(ocr["paragraphs"][:5])

    merged_full_text = native.full_text or ocr["full_text"]

    return DocumentContext(
        path=native.path,
        title=native.title,
        full_text=merged_full_text,
        paragraphs=merged_paragraphs,
        tables=native.tables,
        images=native.images + list(ocr.get("images", [])),
        sections=native.sections,
        semantic_tags=native.semantic_tags,
    )
