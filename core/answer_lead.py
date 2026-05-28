"""Детерминированное оформление ответа Generator: вводная перед списком в начале."""

from __future__ import annotations

import re

_LIST_LINE_RE = re.compile(r"^(?:[-*•]\s+|\d+\.\s+)", re.UNICODE)


def _first_nonempty_line(text: str) -> str:
    for ln in text.splitlines():
        s = ln.strip()
        if s:
            return s
    return ""


def starts_with_list_marker(text: str) -> bool:
    """True, если ответ начинается с маркера списка (-, •, 1. и т.п.)."""
    return bool(_LIST_LINE_RE.match(_first_nonempty_line((text or "").strip())))


def lead_line_before_list(
    *,
    user_question: str = "",
    h2: str | None = None,
    h3: str | None = None,
    doc_id: str | None = None,
) -> str:
    """Короткая вводная по контексту вопроса/чанка (без LLM)."""
    q = (user_question or "").lower()
    h2s = (h2 or "").strip()
    h3s = (h3 or "").strip()
    doc = (doc_id or "").lower()
    h2l = h2s.lower()
    h3l = h3s.lower()

    if "pricing" in doc or "цен" in h2l:
        if "all_on_4" in doc or "all-on-4" in q or "all on 4" in q:
            return "Стоимость All-on-4 на одну челюсть зависит от системы имплантов:"
        if "all_on_6" in doc or "all-on-6" in q or "all on 6" in q:
            return "Стоимость All-on-6 на одну челюсть зависит от системы имплантов:"
        if "implants" in doc or ("имплант" in q and "all-on" not in q and "all on" not in q):
            return "Стоимость имплантации «под ключ» зависит от выбранной системы:"
        if any(w in q for w in ("сколько", "стоим", "цен", "прайс", "дорог")):
            return "Ориентиры по стоимости такие:"

    if "оплат" in h3l or "этап" in h3l:
        return "Оплата по этапам выглядит так:"

    if h3l == "коротко":
        if "имплант" in q or "implant" in doc:
            return "Кратко по имплантации — ориентиры по системам:"
        return "Кратко по сути:"

    if h3s:
        return f"По теме «{h3s}» — основное:"

    if h2s:
        return f"По разделу «{h2s}» — основное:"

    return "Кратко по вашему вопросу:"


def ensure_lead_before_list(
    answer: str,
    *,
    user_question: str = "",
    h2: str | None = None,
    h3: str | None = None,
    doc_id: str | None = None,
) -> str:
    """Если ответ начинается со списка — добавить вводную строку."""
    text = (answer or "").strip()
    if not text or not starts_with_list_marker(text):
        return answer
    lead = lead_line_before_list(
        user_question=user_question,
        h2=h2,
        h3=h3,
        doc_id=doc_id,
    ).strip()
    if not lead:
        return answer
    if text.startswith(lead):
        return answer
    return f"{lead}\n\n{text}"
