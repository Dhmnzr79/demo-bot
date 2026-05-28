from __future__ import annotations

from core.stream_answer_text import (
    AnswerFormatContext,
    StreamTextAccumulator,
    prebuffer_ready,
)


def test_prebuffer_ready_on_list_start() -> None:
    assert prebuffer_ready("- Implantium — 76 200 ₽\n- Impro", stream_ended=False)


def test_prebuffer_blocks_until_enough_for_paragraph() -> None:
    short = "Стоимость зависит от системы"
    assert not prebuffer_ready(short, stream_ended=False)
    long = short + " " + "x" * 90 + ". Далее текст."
    assert prebuffer_ready(long, stream_ended=False)


def test_stream_accumulator_prepends_lead_before_first_emit() -> None:
    ctx = AnswerFormatContext(
        user_question="Сколько стоят импланты?",
        doc_id="implantation__pricing__implants",
        h3="Коротко",
    )
    acc = StreamTextAccumulator(ctx=ctx)
    d1 = acc.ingest_llm_delta("- **A** — 1\n- **B** — 2\n- **C** — 3\n")
    assert d1
    assert d1.startswith("Стоимость")
    assert "- A" in d1
    assert "**A**" not in d1
    d2 = acc.ingest_llm_delta("хвост")
    assert "хвост" in d2
    assert acc.display_sent_len == len(acc.display_text())


def test_stream_prefix_stable_when_more_tokens_arrive() -> None:
    ctx = AnswerFormatContext(user_question="цены", doc_id="implantation__pricing__implants")
    acc = StreamTextAccumulator(ctx=ctx)
    first = acc.ingest_llm_delta("- a\n- b\n- c\n")
    second = acc.ingest_llm_delta("")
    third = acc.finalize("- a\n- b\n- c\n")
    assert first.startswith(acc.display_text()[:20])
    assert not third or third == ""
