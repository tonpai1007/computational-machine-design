"""
MDIE Learning Tools Integration Bridge
Provides computational-machine-design direct access to tools from learning-tools:
- Report Converter: HTML-to-Word Converter (HTMLToDocxConverter / write_docx)
- Knowledge Consolidator: Ingest reports, chunk content, generate summaries & study notes
- Study Guide Exporter: Markdown summaries, NotebookLM packs, and Anki decks

Supports Dual-Mode execution:
1. REST API: Communicates with learning-tools web service (port 5000) when running.
2. Direct Library Import: Seamless fallback directly importing `lt.*` when running offline or standalone.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

LEARNING_TOOLS_DIR = Path(
    os.environ.get("LEARNING_TOOLS_DIR", r"c:\codework\learning-tools")
).resolve()
DEFAULT_LT_URL = os.environ.get("LEARNING_TOOLS_URL", "http://127.0.0.1:5000")


def ensure_lt_imported():
    """Ensure learning-tools package is discoverable on sys.path."""
    if LEARNING_TOOLS_DIR.exists() and str(LEARNING_TOOLS_DIR) not in sys.path:
        sys.path.insert(0, str(LEARNING_TOOLS_DIR))


class LearningToolsBridge:
    """
    Bridge allowing MDIE to leverage tools from the learning-tools repository and API.
    """

    def __init__(self, base_url: str = DEFAULT_LT_URL, lt_dir: Path | None = None):
        self.base_url = base_url.rstrip("/")
        self.lt_dir = lt_dir or LEARNING_TOOLS_DIR
        ensure_lt_imported()

    # -------------------------------------------------------------------------
    # Service Connectivity
    # -------------------------------------------------------------------------
    def is_online(self, timeout: float = 1.0) -> bool:
        """Check if the learning-tools Flask web service is running."""
        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/stats", headers={"User-Agent": "MDIE-Bridge/1.0"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status == 200
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # Report Converter Tool (HTML -> DOCX)
    # -------------------------------------------------------------------------
    def convert_docx(
        self,
        html_path: str | Path,
        output_docx_path: str | Path | None = None,
        enable_ai: bool = False,
        custom_ai_instructions: str | None = None,
    ) -> Path:
        """
        Convert an HTML engineering report to Word (.docx).
        Dual-mode: Uses REST API if online, falls back to direct library execution.
        """
        html_path = Path(html_path)
        if not html_path.exists():
            raise FileNotFoundError(f"HTML file not found: {html_path}")

        if output_docx_path is None:
            output_docx_path = html_path.with_suffix(".docx")
        else:
            output_docx_path = Path(output_docx_path)

        # 1. Try remote API if server is online
        if self.is_online():
            try:
                payload = {
                    "html_path": str(html_path.resolve()),
                    "output_docx_path": str(output_docx_path.resolve()),
                    "enable_ai": enable_ai,
                    "custom_ai_instructions": custom_ai_instructions,
                }
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    f"{self.base_url}/api/convert/docx",
                    data=data,
                    headers={"Content-Type": "application/json", "User-Agent": "MDIE-Bridge/1.0"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=30.0) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    if resp_data.get("status") == "ok" and output_docx_path.exists():
                        logger.info(f"Converted DOCX via learning-tools API: {output_docx_path}")
                        return output_docx_path
            except Exception as e:
                logger.warning(
                    f"API call to learning-tools failed ({e}); falling back to direct library."
                )

        # 2. Direct library execution via learning-tools
        from convert.registry import has_dependency
        from convert.solids import ConversionError

        if not has_dependency("bs4"):
            raise ConversionError(
                "learning-tools HTML->DOCX conversion needs the optional 'bs4' "
                "(beautifulsoup4) package, which is not installed. Install it with "
                "'pip install beautifulsoup4' or start the learning-tools REST API "
                "on port 5000 to use the API path instead."
            )
        try:
            from lt.docx_converter import HTMLToDocxConverter
        except ImportError as exc:
            raise ConversionError(
                f"learning-tools DOCX conversion unavailable: {exc}. Install "
                "beautifulsoup4, or start the learning-tools REST API on port 5000."
            ) from exc
        return HTMLToDocxConverter.convert(
            html_path=html_path,
            output_docx_path=output_docx_path,
            enable_ai=enable_ai,
            custom_ai_instructions=custom_ai_instructions,
        )

    # -------------------------------------------------------------------------
    # Knowledge Consolidator Tool
    # -------------------------------------------------------------------------
    def consolidate_report(
        self,
        report_path: str | Path,
        output_dir: str | Path | None = None,
        convert_docx: bool = True,
        generate_summaries: bool = True,
        generate_notebooklm: bool = True,
        enable_ai: bool = False,
    ) -> dict[str, Any]:
        """
        Consolidate an MDIE engineering report (HTML or Markdown) into structured study materials
        using chunking, summarization, and export tools from learning-tools.
        Dual-mode: Uses REST API if online, falls back to direct library execution.
        """
        report_path = Path(report_path)
        if not report_path.exists():
            raise FileNotFoundError(f"Report file not found: {report_path}")

        if output_dir is None:
            output_dir = report_path.parent / "learning_materials"
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 1. Try remote API if server is online
        if self.is_online():
            try:
                payload = {
                    "report_path": str(report_path.resolve()),
                    "output_dir": str(output_dir.resolve()),
                    "convert_docx": convert_docx,
                    "generate_summaries": generate_summaries,
                    "generate_notebooklm": generate_notebooklm,
                    "enable_ai": enable_ai,
                }
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    f"{self.base_url}/api/consolidate",
                    data=data,
                    headers={"Content-Type": "application/json", "User-Agent": "MDIE-Bridge/1.0"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=60.0) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    if resp_data.get("status") == "ok":
                        logger.info(f"Consolidated report via learning-tools API: {resp_data}")
                        return resp_data
            except Exception as e:
                logger.warning(
                    f"API call to learning-tools /api/consolidate failed ({e}); falling back to direct library."
                )

        # 2. Direct library execution via learning-tools
        from convert.registry import has_dependency
        from convert.solids import ConversionError

        for pkg, tool in (("bs4", "HTML->DOCX"), ("yaml", "report consolidation")):
            if not has_dependency(pkg):
                raise ConversionError(
                    f"learning-tools {tool} needs the optional '{pkg}' package, "
                    f"which is not installed. Install it with 'pip install {pkg}' "
                    "or start the learning-tools REST API on port 5000 to use the "
                    "API path instead."
                )
        try:
            from lt import export, generate
            from lt.chunker import chunk_sources
            from lt.docx_converter import HTMLToDocxConverter
            from lt.ingest import Source
        except ImportError as exc:
            raise ConversionError(
                f"learning-tools consolidation unavailable: {exc}. Install its "
                "optional dependencies, or start the learning-tools REST API on "
                "port 5000."
            ) from exc

        source = Source(report_path)
        chunks = chunk_sources([source])

        generated_files = {}

        # Convert to DOCX if HTML
        if convert_docx and report_path.suffix.lower() in (".html", ".htm"):
            docx_path = output_dir / f"{report_path.stem}.docx"
            HTMLToDocxConverter.convert(
                html_path=report_path, output_docx_path=docx_path, enable_ai=enable_ai
            )
            generated_files["docx"] = str(docx_path)

        # Summaries & NotebookLM study pack
        if generate_summaries and chunks:
            summaries = generate.generate_summaries(chunks)
            sum_path = output_dir / f"{report_path.stem}_summaries.md"
            export.write_summaries(summaries, sum_path)
            generated_files["summaries"] = str(sum_path)

            if generate_notebooklm:
                export.write_notebooklm_pack(summaries, output_dir)
                generated_files["notebooklm_pack"] = str(output_dir / "notebooklm_pack")

        return {
            "status": "ok",
            "source": report_path.name,
            "chunks_count": len(chunks),
            "output_dir": str(output_dir),
            "generated_files": generated_files,
        }


# Convenient alias
LearningToolsClient = LearningToolsBridge
