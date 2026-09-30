"""
MDIE HTML to DOCX Converter Bridge.

The core implementation of HTMLToDocxConverter has moved to the learning-tools repository:
`c:\\codework\\learning-tools\\lt\\docx_converter.py`

This module provides seamless backward compatibility for MDIE CLI and test suites,
delegating to `lt.docx_converter.HTMLToDocxConverter` and the Learning Tools suite.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Union

# Ensure learning-tools is on sys.path for direct module import
LT_PATH = Path("c:/codework/learning-tools").resolve()
if LT_PATH.exists() and str(LT_PATH) not in sys.path:
    sys.path.insert(0, str(LT_PATH))

try:
    from lt.docx_converter import HTMLToDocxConverter
except ImportError as e:
    raise ImportError(
        f"Could not import HTMLToDocxConverter from lt.docx_converter at {LT_PATH}: {e}"
    )

__all__ = ["HTMLToDocxConverter"]
