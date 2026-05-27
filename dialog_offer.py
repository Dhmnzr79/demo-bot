"""Детерминированная логика lead-offer и запрета «свободных» continuation invites."""
from __future__ import annotations

import re

# Strict affirmative для pending_lead_offer (не общий parse_yes).
_LEAD_OFFER_YES_RX = re.compile(
    r"^(?:"
    r"да"
    r"|давай(?:те)?"
    r"|ок(?:ей)?"
    r"|ok"
    r"|хорошо"
    r"|конечно"
    r")\W*$",
    re.I | re.U,
)

_LEAD_OFFER_NO_RX = re.compile(
    r"^(?:"
    r"нет"
    r"|неа"
    r"|не\s+надо"
    r"|не\s+нужно"
    r"|no"
    r")\W*$",
    re.I | re.U,
)

# Явный бинарный вопрос бота про запись/консультацию (не общее «можно на консультации»).
_EXPLICIT_LEAD_OFFER_RX = re.compile(
    r"(?:"
    r"хотите[\s,]+запис(?:аться|ать)\??"
    r"|записать\s+вас\s+на\s+консультаци(?:ю|и)\??"
    r"|хотите[\s,]+(?:я\s+)?помог(?:у|ю)\s+(?:вам\s+)?запис(?:аться|ать)\??"
    r"|оставить\s+заявку\s+на\s+консультаци(?:ю|и)\??"
    r"|запис(?:аться|ать)\s+на\s+консультаци(?:ю|и)\??"
    r")",
    re.I | re.U,
)

# Свободные приглашения продолжить без structural followup.
_CONTINUATION_INVITE_SENTENCE_RX = re.compile(
    r"(?:"
    r"если\s+хотите[\s,]+(?:я\s+)?(?:могу|мог(?:у|ите))\s+(?:ещё|еще|ещё|продолжить|рассказать|сравнить)"
    r"|(?:могу|мог(?:у|ите))\s+(?:ещё|еще|ещё)\s+(?:коротко\s+)?(?:рассказать|сравнить|продолжить)"
    r"|(?:могу|мог(?:у|ите))\s+(?:продолжить|сравнить\s+дальше|рассказать\s+(?:ещё|еще|ещё))"
    r"|если\s+хотите[\s,]+(?:продолж(?:у|им)|расскаж(?:у|ем))"
    r")",
    re.I | re.U,
)

_TRAILING_INVITE_BLOCK_RX = re.compile(
    r"(?:\n\n|\.\s+|\?\s+|\!\s+)+[^.!?\n]*"
    + _CONTINUATION_INVITE_SENTENCE_RX.pattern
    + r"[^.!?\n]*[.!?…]?\s*$",
    re.I | re.U,
)


def parse_lead_offer_yes(text: str) -> bool:
    return bool(_LEAD_OFFER_YES_RX.fullmatch((text or "").strip()))


def parse_lead_offer_no(text: str) -> bool:
    return bool(_LEAD_OFFER_NO_RX.fullmatch((text or "").strip()))


def detect_explicit_lead_offer_in_answer(answer: str) -> bool:
    return bool(_EXPLICIT_LEAD_OFFER_RX.search((answer or "").strip()))


def sanitize_ungrounded_continuation_invites(
    answer: str,
    *,
    has_structural_followups: bool,
) -> str:
    """Убрать текстовые «могу продолжить», если нет followup-кнопок."""
    text = (answer or "").strip()
    if not text or has_structural_followups:
        return text
    cleaned = _TRAILING_INVITE_BLOCK_RX.sub("", text).strip()
    if not cleaned:
        return text
    return cleaned
