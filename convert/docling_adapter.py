from __future__ import annotations

from pathlib import Path

from convert.document_intelligence import DocumentContext, DocumentSection, _infer_semantic_tags


def _extract_docling_semantics(document: object) -> tuple[str, list[str], list[str]]:
    """Best-effort extraction of useful Docling metadata.

    The adapter is intentionally defensive: it reads the usual title/text fields
    from multiple Docling versions and converts them into the repo-native model.
    """
    title = ""
    text_chunks: list[str] = []

    def walk(node: object) -> None:
        nonlocal title
        if node is None:
            return

        if isinstance(node, dict):
            for key, value in node.items():
                lowered = str(key).lower()
                if lowered in {"title", "name"} and isinstance(value, str) and value.strip():
                    title = value.strip()
                elif isinstance(value, str) and value.strip():
                    text_chunks.append(value.strip())
                else:
                    walk(value)
            return

        if isinstance(node, (list, tuple, set)):
            for value in node:
                walk(value)
            return

        for attr_name in ("title", "name", "text", "body_text", "content"):
            if not hasattr(node, attr_name):
                continue
            value = getattr(node, attr_name)
            if attr_name in {"title", "name"} and isinstance(value, str) and value.strip():
                title = value.strip()
            elif isinstance(value, str) and value.strip():
                text_chunks.append(value.strip())
            elif value is not None:
                walk(value)

    walk(document)

    text_blurb = "\n".join(text_chunks)
    return title.strip(), text_blurb.splitlines(), _infer_semantic_tags(text_blurb)


def enrich_document_context(context: DocumentContext) -> DocumentContext:
    """Optionally enrich a repo-native document context with Docling semantics.

    Docling remains an optional enhancer; the repo-native document model remains
    the source of truth for Word edits, layout placement, and report generation.
    """
    path = Path(context.path) if context.path else None

    try:
        from docling.document_converter import DocumentConverter  # type: ignore
    except Exception:  # pragma: no cover - optional dependency path
        return context

    try:
        result = DocumentConverter().convert(str(path) if path is not None else "")
    except Exception:
        return context

    document = getattr(result, "document", result)
    title, body_lines, docling_tags = _extract_docling_semantics(document)
    if not title and not docling_tags and not body_lines:
        return context

    merged_text = "\n".join(filter(None, [context.full_text, *body_lines]))
    merged_tags = list(dict.fromkeys([*context.semantic_tags, *docling_tags]))
    title = title or context.title

    context.title = title
    if merged_text and merged_text != context.full_text:
        context.full_text = merged_text
    if merged_tags:
        context.semantic_tags = merged_tags

    for section in context.sections:
        if section.summary:
            continue
        text = " ".join(section.paragraphs).strip()
        if text:
            section.summary = text[:220]
        if docling_tags:
            section.semantic_tags = list(dict.fromkeys([*section.semantic_tags, *docling_tags]))

    if not context.sections and body_lines:
        summary_lines = [line.strip() for line in body_lines if line.strip()]
        context.sections = [
            DocumentSection(
                heading=title or "Document",
                paragraphs=summary_lines[:10],
                tables=[],
                images=[],
                summary=" ".join(summary_lines[:3])[:220] or (title or "Document"),
                semantic_tags=docling_tags or merged_tags,
            )
        ]

    return context
