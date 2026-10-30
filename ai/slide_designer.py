"""AI-powered slide design for MDIE.

Design spec is produced by LLMRouter (Groq/OpenRouter/Gemini/Ollama) with a
deterministic fallback. All engineering numbers remain 100% physics-derived:
this module only authors layout, typography, colour and wording.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from ai.llm_router import LLMRouter

logger = logging.getLogger("ai.slide_designer")


class SlideSpec(BaseModel):
    title: str = ""
    subtitle: str = ""
    palette: dict[str, str] = Field(default_factory=dict)
    typography: dict[str, str] = Field(default_factory=dict)
    slides: list[dict[str, Any]] = Field(default_factory=list)


# Deterministic fallback used when no LLM provider is configured.
_FALLBACK = SlideSpec(
    title="Machine Design Intelligence Engine",
    subtitle="Engineering Slide Deck",
    palette={
        "bg": "#0f172a",
        "ink": "#f8fafc",
        "accent": "#38bdf8",
        "muted": "#94a3b8",
        "pass": "#22c55e",
        "fail": "#ef4444",
    },
    typography={"heading": "Inter, system-ui, sans-serif", "body": "Inter, system-ui, sans-serif"},
    slides=[],
)


def _build_prompt(content: dict[str, Any]) -> str:
    return (
        "You are a senior presentation designer. Produce a slide design spec as JSON.\n"
        "Return ONLY a JSON object with these keys:\n"
        "- title: short deck title\n"
        "- subtitle: one-line subtitle\n"
        "- palette: {bg, ink, accent, muted, pass, fail} hex colours\n"
        "- typography: {heading, body} font stacks\n"
        "- slides: array of {type, heading, body, accent}\n"
        "  type is one of: cover, bullet, table, metric, quote, end\n"
        "  body is an array of strings (bullet items) or a 2D array for tables\n"
        "  accent is an optional highlight colour override\n\n"
        f"Content to design around:\n{json.dumps(content, ensure_ascii=False, indent=2)}\n\n"
        "Rules: use a professional engineering white-paper aesthetic. "
        "Keep slide count concise. No markdown, no HTML."
    )


def design_slides(content: dict[str, Any], use_ai: bool = True) -> SlideSpec:
    """Generate a slide design spec, using LLM when available."""
    if not use_ai:
        spec = _FALLBACK.model_copy(deep=True)
        spec.slides = content.get("slides", [])
        return spec

    try:
        resp, provider, logs = LLMRouter.call_chat_completion(
            system_prompt="You are a presentation design specialist.",
            user_prompt=_build_prompt(content),
            response_format_json=True,
            max_tokens=4000,
            temperature=0.3,
        )
        if resp:
            data = json.loads(resp)
            spec = SlideSpec.model_validate(data)
            logger.info("Slide design generated via %s", provider)
            return spec
    except Exception as exc:  # noqa: BLE001
        logger.warning("Slide design AI failed: %s", exc)

    spec = _FALLBACK.model_copy(deep=True)
    spec.slides = content.get("slides", [])
    return spec


__all__ = ["SlideSpec", "design_slides"]
