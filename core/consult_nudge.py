"""Когда предлагать консультацию в тексте ответа (счётчик + исчерпание темы).

Текст приглашения формирует LLM по инструкции в промпте — без фиксированных заготовок.
"""
from __future__ import annotations

import re
from typing import Literal

from dialog_offer import detect_explicit_lead_offer_in_answer
from policy import _is_topic_exhausted
from session import (
    get_consult_streak,
    increment_consult_streak,
    reset_consult_streak,
)

ConsultNudgeKind = Literal["exhausted", "streak"]

_SUBSTANTIVE_ROUTES = frozenset(
    {
        "retrieval_chunk",
        "catalog_md_first",
        "contacts_chunk",
        "price_concern",
        "catalog_facts",
        "price_lookup",
    }
)

_NON_SUBSTANTIVE_ROUTES = frozenset(
    {
        "low_score_fallback",
        "retrieval_no_candidates",
        "offtopic",
        "lead_flow",
        "booking_flow",
        "error",
        "rate_limited",
        "duplicate_short_circuit",
        "guided",
        "continuation_clarify",
        "reset_session",
    }
)

_HAS_CONSULT_INVITE_RX = re.compile(
    r"(?:"
    r"запис(?:аться|ать)\s+на\s+(?:бесплатн\w+\s+)?консультаци"
    r"|бесплатн\w+\s+консультаци"
    r"|на\s+консультаци(?:и|ю)\s+(?:можно|разбер)"
    r")",
    re.I | re.U,
)


def is_substantive_content_route(route: str | None) -> bool:
    r = (route or "").strip().lower()
    if not r or r in _NON_SUBSTANTIVE_ROUTES:
        return False
    if r.startswith("ingress_"):
        return False
    return r in _SUBSTANTIVE_ROUTES


def answer_has_consult_invite(answer: str) -> bool:
    text = (answer or "").strip()
    if not text:
        return False
    if detect_explicit_lead_offer_in_answer(text):
        return True
    return bool(_HAS_CONSULT_INVITE_RX.search(text))


def topic_exhausted_after_this_chunk(
    doc_meta: dict,
    topic_state: dict,
    *,
    chunk_h3_id: str | None,
) -> bool:
    """Тема будет исчерпана после показа текущего чанка (как в policy после mark_h3)."""
    suggest_h3 = list(doc_meta.get("suggest_h3") or [])
    covered = set(topic_state.get("covered_h3_ids") or [])
    if chunk_h3_id and chunk_h3_id in set(suggest_h3):
        covered = covered | {chunk_h3_id}
    projected = {
        "covered_h3_ids": list(covered),
        "doc_turn_count": int(topic_state.get("doc_turn_count") or 0) + 1,
    }
    return _is_topic_exhausted(doc_meta, projected)


def plan_consult_nudge(
    session_id: str,
    route: str | None,
    *,
    topic_exhausted: bool,
) -> ConsultNudgeKind | None:
    """До генерации: нужно ли попросить LLM завершить ответ приглашением на консультацию."""
    if not is_substantive_content_route(route):
        return None
    if topic_exhausted:
        return "exhausted"
    if get_consult_streak(session_id) >= 2:
        return "streak"
    return None


def record_consult_nudge_after_answer(
    session_id: str,
    route: str | None,
    planned_kind: ConsultNudgeKind | None,
    answer: str,
) -> dict:
    """После генерации: обновить счётчик (без дописывания текста)."""
    meta: dict = {
        "consult_nudge": planned_kind,
        "consult_streak_before": None,
    }
    if not is_substantive_content_route(route):
        return meta

    meta["consult_streak_before"] = get_consult_streak(session_id)
    if planned_kind:
        reset_consult_streak(session_id)
        return meta
    if answer_has_consult_invite(answer):
        reset_consult_streak(session_id)
    elif (answer or "").strip():
        increment_consult_streak(session_id)
    return meta


def reset_consult_nudge_on_route(route: str | None, session_id: str) -> None:
    r = (route or "").strip().lower()
    if r in {"low_score_fallback", "retrieval_no_candidates"}:
        reset_consult_streak(session_id)
    if r.startswith("ingress_") or r in {"offtopic", "lead_flow", "booking_flow", "error"}:
        reset_consult_streak(session_id)


def consult_nudge_prompt_addon(kind: ConsultNudgeKind | None) -> str:
    """Инструкция для LLM (не готовый текст для пациента)."""
    if kind == "exhausted":
        return (
            "\n\nЗадача на этот ответ:\n"
            "После ответа по вопросу пациенту по этой теме в базе больше нечего добавить — "
            "тема для справочного ответа исчерпана.\n"
            "Заверши ответ естественно: мягко предложи бесплатную консультацию в клинике "
            "как следующий шаг (своими словами, в том же тоне, без давления).\n"
            "Не предлагай текстом «могу ещё рассказать» — только консультацию, если уместно завершить диалог."
        )
    if kind == "streak":
        return (
            "\n\nЗадача на этот ответ:\n"
            "Пациент уже несколько раз уточнял по теме клиники.\n"
            "Сначала ответь по существу на вопрос, затем в конце того же ответа "
            "мягко предложи бесплатную консультацию, чтобы разобрать детали лично "
            "(своими словами, без шаблонных фраз и без давления)."
        )
    return ""
