"""Стриминг текста ответа: prebuffer, одна display-версия, без переписывания начала."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.answer_bold import normalize_answer_bold
from core.answer_lead import ensure_lead_before_list, starts_with_list_marker

# UX prebuffer (не routing thresholds — см. docs/WIDGET_ANSWER_FORMAT.md)
PREBUFFER_MIN_CHARS = 120
PREBUFFER_MAX_CHARS = 250
PREBUFFER_LIST_MIN_CHARS = 32

_SENTENCE_END_RE = re.compile(r"[.!?…][\s\n]")


@dataclass(frozen=True)
class AnswerFormatContext:
    user_question: str = ""
    h2: str | None = None
    h3: str | None = None
    doc_id: str | None = None


def format_answer_for_display(raw: str, ctx: AnswerFormatContext) -> str:
    """Единая display-версия (lead-before-list + жирный только цифры/сроки)."""
    text = (raw or "").strip()
    if not text:
        return text
    text = ensure_lead_before_list(
        text,
        user_question=ctx.user_question,
        h2=ctx.h2,
        h3=ctx.h3,
        doc_id=ctx.doc_id,
    )
    return normalize_answer_bold(text)


def prebuffer_ready(raw: str, *, stream_ended: bool) -> bool:
    """Достаточно текста, чтобы зафиксировать начало ответа перед показом."""
    if stream_ended:
        return bool((raw or "").strip())
    buf = raw or ""
    if len(buf) >= PREBUFFER_MAX_CHARS:
        return True
    stripped = buf.strip()
    if stripped and starts_with_list_marker(stripped):
        if len(buf) >= PREBUFFER_LIST_MIN_CHARS or "\n" in buf:
            return True
    if len(buf) >= PREBUFFER_MIN_CHARS:
        if _SENTENCE_END_RE.search(buf) or "\n\n" in buf:
            return True
    return False


@dataclass
class StreamTextAccumulator:
    """Накопитель raw → display; display_sent_len — сколько уже отдано клиенту."""

    ctx: AnswerFormatContext
    raw: str = ""
    display_sent_len: int = 0
    released: bool = False

    def ingest_llm_delta(self, delta: str) -> str:
        if not delta:
            return ""
        self.raw += delta
        if not self.released:
            if not prebuffer_ready(self.raw, stream_ended=False):
                return ""
            self.released = True
        return self._emit_display_tail()

    def finalize(self, raw_final: str) -> str:
        """После окончания LLM: догнать display-хвост (без изменения уже отправленного префикса)."""
        self.raw = raw_final or ""
        if not self.released:
            if not (self.raw or "").strip():
                return ""
            self.released = True
        return self._emit_display_tail()

    def emit_through(self, full_display: str) -> str:
        """Отдать хвост display-текста, не меняя уже отправленный префикс."""
        out = full_display[self.display_sent_len :]
        self.display_sent_len = len(full_display)
        return out

    def display_text(self) -> str:
        return format_answer_for_display(self.raw, self.ctx)

    def _emit_display_tail(self) -> str:
        display = self.display_text()
        out = display[self.display_sent_len :]
        self.display_sent_len = len(display)
        return out
