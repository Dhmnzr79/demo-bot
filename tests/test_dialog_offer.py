"""Tests for deterministic dialog offer / continuation guards."""
from __future__ import annotations

from dialog_offer import (
    detect_explicit_lead_offer_in_answer,
    parse_lead_offer_no,
    parse_lead_offer_yes,
    sanitize_ungrounded_continuation_invites,
)


def test_parse_lead_offer_yes_strict():
    assert parse_lead_offer_yes("Да")
    assert parse_lead_offer_yes("ок")
    assert parse_lead_offer_yes("хорошо")
    assert not parse_lead_offer_yes("ага")
    assert not parse_lead_offer_yes("хочу")
    assert not parse_lead_offer_yes("да, но сколько стоит?")


def test_parse_lead_offer_no_strict():
    assert parse_lead_offer_no("нет")
    assert parse_lead_offer_no("не надо")
    assert not parse_lead_offer_no("не знаю")


def test_detect_explicit_lead_offer():
    assert detect_explicit_lead_offer_in_answer("Хотите записаться?")
    assert detect_explicit_lead_offer_in_answer("Записать вас на консультацию?")
    assert not detect_explicit_lead_offer_in_answer(
        "На консультации можно обсудить подробнее."
    )


def test_strip_continuation_without_followups():
    raw = (
        "Одномоментная и классическая отличаются по этапам.\n\n"
        "Если хотите, могу еще коротко сравнить их по срокам и этапам."
    )
    cleaned = sanitize_ungrounded_continuation_invites(raw, has_structural_followups=False)
    assert "могу еще" not in cleaned.lower()
    assert "отличаются" in cleaned

    kept = sanitize_ungrounded_continuation_invites(raw, has_structural_followups=True)
    assert kept == raw
