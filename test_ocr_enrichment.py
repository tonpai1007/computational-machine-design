"""Test script for OCR enrichment layer."""
from pathlib import Path

from convert.document_intelligence import (
    _try_import_ocr,
    extract_document_context_ocr,
    enrich_document_context_with_ocr,
)


def make_native_context():
    """Create a mock native DocumentContext dict."""
    return {
        "path": "test.docx",
        "title": "Test Report",
        "full_text": "Design overview and analysis",
        "paragraphs": ["Design overview paragraph", "Analysis results here"],
        "tables": [],
        "images": [],
        "sections": [],
        "semantic_tags": ["design", "analysis"],
    }


def test_ocr_import():
    """Test that OCR imports gracefully without required libs."""
    result = _try_import_ocr()
    assert result is None, f"Expected None, got {result}"
    print("PASS: _try_import_ocr returns None when no OCR libs installed")


def test_ocr_no_lib_fallback():
    """Test OCR fallback when no libraries installed - should not crash."""
    # Just test the function exists and returns expected structure
    result = extract_document_context_ocr(str(Path("nonexistent.docx")))
    # Should return dict with success=False and note
    assert isinstance(result, dict), "Should return dict"
    assert result.get("success") is False, "Should fail for nonexistent file"
    assert "note" in result, "Should have note about missing libs"
    print("PASS: OCR falls gracefully for nonexistent file")


def test_enrich_no_lib_fallback():
    """Test enrichment falls back gracefully when OCR unavailable."""
    native = make_native_context()
    enriched = enrich_document_context_with_ocr("nonexistent.docx", native)
    # Should preserve native data (OCR fails, returns native)
    assert enriched["title"] == "Test Report"
    assert enriched["full_text"] == "Design overview and analysis"
    assert enriched["path"] == "test.docx"
    print("PASS: Enrichment preserves native data when OCR unavailable")


def test_enrich_with_ocr_note():
    """Test enrichment includes OCR note when available."""
    native = make_native_context()
    enriched = enrich_document_context_with_ocr("nonexistent.docx", native)
    assert "ocr_note" in enriched, "Should include ocr_note key"
    assert enriched["ocr_note"] is not None, "ocr_note should not be None"
    print(f"PASS: Enrichment includes ocr_note: '{enriched['ocr_note']}'")


if __name__ == "__main__":
    test_ocr_import()
    test_ocr_no_lib_fallback()
    test_enrich_no_lib_fallback()
    test_enrich_with_ocr_note()
    print("\nAll tests passed!")