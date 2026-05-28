"""Очистка текста md-чанка перед подачей в LLM (не меняет файлы на диске)."""

from __future__ import annotations

import re

ALIAS_COMMENT_RX = re.compile(r"<!--\s*aliases:\s*\[.*?\]\s*-->", re.I | re.S)


def strip_alias_comments(text: str) -> str:
    """Убирает HTML-комментарии aliases; сами алиасы остаются в индексе при build."""
    if not text:
        return ""
    lines: list[str] = []
    for ln in text.splitlines():
        stripped = ln.strip()
        if stripped and ALIAS_COMMENT_RX.fullmatch(stripped):
            continue
        lines.append(ln)
    return "\n".join(lines).strip()
