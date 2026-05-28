from __future__ import annotations

from core.answer_lead import ensure_lead_before_list, starts_with_list_marker


def test_starts_with_list_marker() -> None:
    assert starts_with_list_marker("- Implantium — 76 200 ₽")
    assert starts_with_list_marker("1. Этап один")
    assert not starts_with_list_marker("Стоимость зависит от системы:\n\n- A")


def test_ensure_lead_before_list_adds_pricing_intro() -> None:
    raw = "- **Implantium** — **76 200 ₽**\n- **Impro** — **85 200 ₽**"
    out = ensure_lead_before_list(
        raw,
        user_question="Сколько стоит классическая имплантация?",
        h2="Цены на импланты",
        h3="Коротко",
        doc_id="implantation__pricing__implants",
    )
    assert out.startswith("Стоимость имплантации")
    assert "\n\n- **Implantium**" in out


def test_ensure_lead_skips_when_already_paragraph() -> None:
    raw = "В цену входит всё необходимое.\n\n- пункт"
    assert ensure_lead_before_list(raw, user_question="?") == raw
