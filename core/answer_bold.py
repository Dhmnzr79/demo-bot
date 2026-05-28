"""Нормализация **жирного** в ответе Generator: только цифры, сроки, этапы (как в md)."""

from __future__ import annotations

import re

_BOLD_SPAN_RE = re.compile(r"\*\*([^*\n]+)\*\*")

_DURATION_IN_BOLD_RE = re.compile(
    r"\d+(?:[–\-]\d+)?\s*(?:"
    r"лет|года|год|месяцев|месяца|месяц|дней|дня|день|дню|"
    r"недель|недели|неделю|минут|минуты|часов|часа|час|параметров|визита|визитов"
    r")",
    re.IGNORECASE,
)


def _bold_inner_allowed(inner: str) -> bool:
    """Сохранить ** только для цифр/сроков/этапов — не для брендов и названий."""
    s = (inner or "").strip()
    if not s:
        return False
    if re.match(r"(?i)этап\s+\d+", s):
        return True
    if re.match(r"(?i)пожизненн\w*", s):
        return True
    if "₽" in s or "%" in s:
        return True
    if not re.search(r"\d", s):
        return False
    if _DURATION_IN_BOLD_RE.search(s):
        return True
    if re.match(r"\d+\s*(?:лет|года|год)\b", s, re.IGNORECASE):
        return True
    if re.match(r"\d+\+\s*лет", s, re.IGNORECASE):
        return True
    if re.match(r"\d[\d\s]*", s) and ("₽" in s or "%" in s):
        return True
    # Только цифра(ы) без букв — «**4** импланта»
    if re.fullmatch(r"\d+(?:[.,]\d+)?", s):
        return True
    if re.fullmatch(r"\d+(?:[.,]\d+)?\s*%", s):
        return True
    # «76 200» без ₽ в разметке — редко, но допустимо
    if re.fullmatch(r"[\d\s]+", s) and len(s) >= 2:
        return True
    return False


def normalize_answer_bold(text: str) -> str:
    """Убирает ** с брендов и прочего текста; оставляет цены, %, сроки, Этап N."""
    if not text or "**" not in text:
        return text

    def _repl(m: re.Match[str]) -> str:
        inner = m.group(1)
        if _bold_inner_allowed(inner):
            return m.group(0)
        return inner

    return _BOLD_SPAN_RE.sub(_repl, text)
