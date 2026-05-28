from __future__ import annotations

from core.md_clean import strip_alias_comments
from chunk_responder import chunk_context_md_for_llm


def test_strip_alias_comments_removes_html_comment_lines() -> None:
    raw = (
        "Цена под ключ.\n"
        '<!-- aliases: ["цена", "стоимость"] -->\n'
        "- Implantium — 76 200 ₽"
    )
    assert "<!--" not in strip_alias_comments(raw)
    assert "Implantium" in strip_alias_comments(raw)


def test_chunk_context_md_for_llm_omits_alias_comments() -> None:
    chunk = {
        "h2": "Цены",
        "h3": "Коротко",
        "text": (
            "Список:\n"
            '<!-- aliases: ["тест"] -->\n'
            "- **A** — 1 ₽"
        ),
    }
    ctx = chunk_context_md_for_llm(chunk)
    assert "<!--" not in ctx
    assert "**A**" in ctx
    assert "Цены" in ctx


def test_build_messages_stream_includes_plain_answer_rule() -> None:
    from llm import build_messages_for_gpt

    messages, _, _ = build_messages_for_gpt(
        "Сколько стоят импланты?",
        [{"ref": "implantation__pricing__implants.md#korotko", "content": "тест"}],
        {},
        "test-sid",
        force_text=True,
    )
    system = messages[0]["content"]
    assert "безопасный поднабор Markdown" in system
    assert "Без JSON-обёртки" in system
    assert "Никогда не начинай ответ сразу со списка" in system
