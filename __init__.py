"""Hermes plugin for Anti-Slop Engineering."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
RULES_PATH = ROOT / "rules" / "AGENTS.md"
ROOT_RULES_PATH = ROOT / "AGENTS.md"


def _get_instructions() -> str:
    if RULES_PATH.exists():
        return f"ANTI-SLOP ENGINEERING ACTIVE — 7 Gates & SRE Invariants Engaged\n\n{RULES_PATH.read_text(encoding='utf-8').strip()}"
    if ROOT_RULES_PATH.exists():
        return f"ANTI-SLOP ENGINEERING ACTIVE — 7 Gates & SRE Invariants Engaged\n\n{ROOT_RULES_PATH.read_text(encoding='utf-8').strip()}"
    return "ANTI-SLOP ENGINEERING ACTIVE — Enforce 7 gates, Google SRE KISS/DRY/YAGNI, and eliminate AST slop."


def register(gateway: Any) -> None:
    """Register Hermes hooks and commands."""
    if hasattr(gateway, "hook"):
        @gateway.hook("pre_llm_call")
        def pre_llm_call(prompt: str, context: dict[str, Any] | None = None) -> str:
            instructions = _get_instructions()
            return f"{instructions}\n\n{prompt}"
