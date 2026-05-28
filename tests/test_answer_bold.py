from __future__ import annotations

from core.answer_bold import normalize_answer_bold


def test_keeps_price_bold() -> None:
    raw = "- **Implantium (Южная Корея)** — **76 200 ₽**"
    out = normalize_answer_bold(raw)
    assert "**76 200 ₽**" in out
    assert "**Implantium" not in out
    assert "Implantium (Южная Корея)" in out


def test_keeps_duration_bold() -> None:
    assert "**3–4 месяца**" in normalize_answer_bold("между ними **3–4 месяца**.")


def test_log_style_price_first() -> None:
    raw = "**76 200 ₽** — Implantium (Южная Корея)"
    out = normalize_answer_bold(raw)
    assert out.startswith("**76 200 ₽**")
    assert "Implantium" in out and "**Implantium" not in out
