"""MDIE command line interface.

``mdie`` (console script) and ``python -m mdie`` both land on :func:`main`.
"""

from cli.app import main, process_prompt

__all__ = ["main", "process_prompt"]