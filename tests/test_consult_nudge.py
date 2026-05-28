"""Тесты дожима на консультацию (счётчик и планирование, без заготовок текста)."""
from __future__ import annotations

import uuid

import pytest

from core.consult_nudge import (
    answer_has_consult_invite,
    consult_nudge_prompt_addon,
    plan_consult_nudge,
    record_consult_nudge_after_answer,
    topic_exhausted_after_this_chunk,
)
from session import get_consult_streak, reset_consult_streak


@pytest.fixture
def sid():
    s = f"test-consult-{uuid.uuid4().hex[:8]}"
    reset_consult_streak(s)
    return s


def test_prompt_addon_not_patient_canned_text():
    exhausted = consult_nudge_prompt_addon("exhausted")
    assert "Записать вас?" not in exhausted
    assert "консультаци" in exhausted.lower()


def test_streak_plan_on_third_turn(sid):
    meta = {"suggest_h3": ["a"]}
    tstate = {"covered_h3_ids": [], "doc_turn_count": 0}
    assert plan_consult_nudge(sid, "retrieval_chunk", topic_exhausted=False) is None
    record_consult_nudge_after_answer(sid, "retrieval_chunk", None, "Ответ один.")
    assert get_consult_streak(sid) == 1
    record_consult_nudge_after_answer(sid, "retrieval_chunk", None, "Ответ два.")
    assert get_consult_streak(sid) == 2
    assert plan_consult_nudge(sid, "retrieval_chunk", topic_exhausted=False) == "streak"


def test_exhausted_plan(sid):
    meta = {"suggest_h3": ["h3a"]}
    tstate = {"covered_h3_ids": [], "doc_turn_count": 0}
    assert topic_exhausted_after_this_chunk(meta, tstate, chunk_h3_id="h3a")
    assert plan_consult_nudge(sid, "retrieval_chunk", topic_exhausted=True) == "exhausted"


def test_record_resets_after_planned_nudge(sid):
    record_consult_nudge_after_answer(sid, "retrieval_chunk", None, "a")
    record_consult_nudge_after_answer(sid, "retrieval_chunk", None, "b")
    assert get_consult_streak(sid) == 2
    record_consult_nudge_after_answer(
        sid,
        "retrieval_chunk",
        "streak",
        "Ответ. Записаться на консультацию?",
    )
    assert get_consult_streak(sid) == 0


def test_skip_increment_when_invite_in_answer(sid):
    record_consult_nudge_after_answer(
        sid,
        "retrieval_chunk",
        None,
        "Можно записаться на бесплатную консультацию.",
    )
    assert get_consult_streak(sid) == 0
    assert answer_has_consult_invite("бесплатная консультация")
