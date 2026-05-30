"""Orchestration: chunk → LLM answer → policy → session side-effects → HTTP payload."""

from __future__ import annotations

import inspect
import json as _json
import os
from typing import Any, Callable

from core.consult_nudge import (
    plan_consult_nudge,
    record_consult_nudge_after_answer,
    topic_exhausted_after_this_chunk,
)
from core.md_clean import strip_alias_comments
from core.stream_answer_text import AnswerFormatContext, StreamTextAccumulator, format_answer_for_display

import session as session_mod
from llm import LLM_FALLBACK_ANSWER, generate_answer_stream, generate_answer_with_empathy
from logging_setup import log_json
from verifier import build_turn_trace_prefix, schedule_verifier_shadow_if_needed
from meta_loader import get_doc_meta
from policy import apply_response_policy
from session import (
    defer_refs,
    get_topic_state,
    increment_doc_turn_if_contentful,
    is_active_lead_flow,
    mark_h3_covered,
    mark_situation_offered,
    mark_video_pending,
    mark_video_shown,
    mem_add_bot,
    mem_add_user,
    mem_get,
    pop_deferred_ref,
    set_cta_shown,
    set_current_doc,
)
from ux_builder import build_ask_response, normalize_policy_payload

_APPLY_POLICY_PARAMS = inspect.signature(apply_response_policy).parameters


def _planned_consult_nudge_for_chunk(
    *,
    sid: str,
    route: str,
    meta: dict,
    chunk: dict,
    topic_state: dict,
    client_id: str | None = None,
) -> str | None:
    if is_active_lead_flow(mem_get(sid)):
        return None
    exhausted = topic_exhausted_after_this_chunk(
        meta,
        topic_state,
        chunk_h3_id=chunk.get("h3_id"),
    )
    kind = plan_consult_nudge(
        sid, route, topic_exhausted=exhausted, client_id=client_id
    )
    if kind:
        meta["consult_nudge"] = kind
    return kind


def _mark_suggest_ref_used_compat(sid: str, doc_id: str, used: bool = True) -> None:
    fn = getattr(session_mod, "mark_suggest_ref_used", None)
    if callable(fn):
        fn(sid, doc_id, used)


def _increment_doc_turn_with_pre(
    sid: str,
    doc_id: str | None,
    *,
    contentful: bool,
    is_low_score: bool,
    is_error: bool,
    lead_flow_active: bool,
) -> int | None:
    pre_turn = increment_doc_turn_if_contentful(
        sid,
        doc_id,
        contentful=contentful,
        is_low_score=is_low_score,
        is_error=is_error,
        lead_flow_active=lead_flow_active,
    )
    if pre_turn is not None or not doc_id:
        return pre_turn
    if contentful and not is_low_score and not is_error and not lead_flow_active:
        cur = int((get_topic_state(sid, doc_id) or {}).get("doc_turn_count") or 0)
        if cur > 0:
            return cur - 1
    return None


def _apply_response_policy_compat(
    payload: dict,
    session_state: dict,
    q: str,
    *,
    topic_state: dict,
    doc_meta: dict,
    pre_doc_turn_count: int | None,
    session_id: str | None = None,
    client_id: str | None = None,
) -> dict:
    kw: dict = {
        "payload": payload,
        "session_state": session_state,
        "q": q,
        "topic_state": topic_state,
        "doc_meta": doc_meta,
    }
    if "pre_doc_turn_count" in _APPLY_POLICY_PARAMS:
        kw["pre_doc_turn_count"] = pre_doc_turn_count
    if "session_id" in _APPLY_POLICY_PARAMS:
        kw["session_id"] = session_id
    if "client_id" in _APPLY_POLICY_PARAMS:
        kw["client_id"] = client_id
    return apply_response_policy(**kw)


def chunk_context_md_for_llm(chunk: dict) -> str:
    """Контент для генерации: H2 + H3 + тело чанка (имя врача и т.п. часто только в h2)."""
    parts: list[str] = []
    h2 = (chunk.get("h2") or "").strip()
    h3 = (chunk.get("h3") or "").strip()
    body = strip_alias_comments((chunk.get("text") or "").strip())
    if h2:
        parts.append(h2)
    if h3:
        parts.append(h3)
    if body:
        parts.append(body)
    return "\n\n".join(parts) if parts else ""


def source_ref_from_chunk(chunk: dict) -> str:
    """Единственный ref источника для Generator (basename.md#anchor)."""
    meta = chunk.get("meta") or {}
    if not isinstance(meta, dict):
        meta = {}
    file = str(chunk.get("file") or "")
    base = os.path.basename(file)
    if not base:
        return ""
    if not base.lower().endswith(".md"):
        base = f"{base}.md"
    h3 = str(chunk.get("h3_id") or meta.get("h3_id") or "").strip()
    h2 = str(chunk.get("h2_id") or meta.get("h2_id") or "").strip()
    anchor = (h3 or h2 or "korotko").strip().lower() or "korotko"
    return f"{base}#{anchor}"


def build_generator_source_from_chunk(chunk: dict, meta: dict) -> dict:
    """Один элемент sources[] для LLM (длина 1)."""
    m = meta if isinstance(meta, dict) else {}
    doc_id = str(m.get("doc_id") or "").strip()
    if not doc_id:
        doc_id = os.path.splitext(os.path.basename(str(chunk.get("file") or "")))[0]
    return {
        "ref": source_ref_from_chunk(chunk),
        "content": chunk_context_md_for_llm(chunk),
        "doc_id": doc_id or None,
        "doc_type": str(m.get("doc_type") or chunk.get("doc_type") or "") or None,
        "subtype": str(m.get("subtype") or chunk.get("subtype") or "") or None,
    }


def _append_generator_append_text(answer: str, append_text: str | None) -> str:
    at = (append_text or "").strip()
    if not at:
        return answer
    base = (answer or "").strip()
    if at in base:
        return answer
    return f"{base}\n\n{at}" if base else at


def verifier_effective_source_body(*, chunk_md_body: str, generator_append_text: str | None) -> str:
    """Текст «разрешённых фактов» для A7: чанк + детерминированный хвост (цены и т.д.), если был."""
    base = (chunk_md_body or "").strip()
    at = (generator_append_text or "").strip()
    if not at:
        return base
    return (
        f"{base}\n\n---\n"
        "Ниже — детерминированное дополнение к ответу пользователю (не из LLM-генератора по чанку). "
        "Для verifier это часть разрешённого контекста фактов наравне с основным источником:\n\n"
        f"{at}"
    )


def ensure_answer(answer: str, chunk: dict) -> str:
    if isinstance(answer, str) and answer.strip():
        return answer
    return (
        "Сейчас не получилось сформулировать ответ. "
        "Попробуйте переформулировать вопрос или выберите тему ниже."
    )


def _answer_format_context(
    *,
    user_question: str,
    chunk: dict,
    meta: dict | None = None,
) -> AnswerFormatContext:
    m = meta if isinstance(meta, dict) else {}
    doc_id = str(m.get("doc_id") or "").strip()
    if not doc_id:
        doc_id = os.path.splitext(os.path.basename(str(chunk.get("file") or "")))[0]
    return AnswerFormatContext(
        user_question=user_question,
        h2=str(chunk.get("h2") or "") or None,
        h3=str(chunk.get("h3") or "") or None,
        doc_id=doc_id or None,
    )


def format_generator_answer(
    answer: str,
    *,
    user_question: str,
    chunk: dict,
    meta: dict | None = None,
) -> str:
    """Пост-оформление ответа Generator (вводная перед списком в начале)."""
    ctx = _answer_format_context(user_question=user_question, chunk=chunk, meta=meta)
    return format_answer_for_display(answer, ctx)


def meta_for_chunk(chunk: dict, client_id: str | None = None) -> dict:
    meta = get_doc_meta(
        os.path.basename(chunk.get("file", "") or ""),
        client_id=client_id or chunk.get("client_id"),
    ) or {}
    meta = dict(meta)
    if not meta.get("doc_id"):
        meta["doc_id"] = os.path.splitext(os.path.basename(chunk.get("file", "") or ""))[0]
    return meta


def respond_from_chunk(
    *,
    chunk: dict,
    q: str,
    sid: str,
    client_id: str | None,
    finalize_ask: Callable[..., dict],
    safe_jsonify: Callable[[dict], Any],
    logger,
    llm_question: str | None = None,
    log_event: str = "Answer generated",
    route: str = "retrieval_chunk",
    generator_append_text: str | None = None,
):
    if (q or "").strip():
        mem_add_user(sid, q)
    meta = meta_for_chunk(chunk, client_id=client_id)
    if client_id is not None:
        meta["client_id"] = client_id
    doc_id = meta.get("doc_id")
    if doc_id:
        set_current_doc(sid, doc_id)

    sources = [build_generator_source_from_chunk(chunk, meta)]
    s0 = sources[0]
    generator_input = {
        "source_ref": s0.get("ref"),
        "source_count": 1,
        "route": route,
        "doc_id": s0.get("doc_id"),
        "doc_type": s0.get("doc_type"),
        "subtype": s0.get("subtype"),
        "h2_id": chunk.get("h2_id"),
        "h3_id": chunk.get("h3_id"),
    }

    tstate_pre = get_topic_state(sid, doc_id) if doc_id else {}
    planned_nudge = _planned_consult_nudge_for_chunk(
        sid=sid,
        route=route,
        meta=meta,
        chunk=chunk,
        topic_state=tstate_pre,
        client_id=client_id,
    )

    answer, profile = generate_answer_with_empathy(
        llm_question or q, sources, meta, sid
    )
    answer = ensure_answer(answer, chunk)
    answer = format_generator_answer(
        answer, user_question=llm_question or q, chunk=chunk, meta=meta
    )
    answer = _append_generator_append_text(answer, generator_append_text)

    st = mem_get(sid)
    lead_flow_active = is_active_lead_flow(st)
    pre_turn = _increment_doc_turn_with_pre(
        sid,
        doc_id,
        contentful=bool(answer.strip()),
        is_low_score=False,
        is_error=False,
        lead_flow_active=lead_flow_active,
    )
    tstate = get_topic_state(sid, doc_id) if doc_id else {}
    suggest_h3 = set(meta.get("suggest_h3") or [])
    h3_id = chunk.get("h3_id")
    if h3_id and h3_id in suggest_h3:
        mark_h3_covered(sid, doc_id, h3_id)
        tstate = get_topic_state(sid, doc_id)

    consult_meta = record_consult_nudge_after_answer(
        sid, route, planned_nudge, answer
    )

    payload = build_ask_response(
        answer=answer,
        top=chunk,
        meta=meta,
        sid=sid,
        profile=profile,
        client_id=client_id,
        topic_state=tstate,
    )
    if route:
        payload.setdefault("meta", {})["orch_route"] = route
    if route == "price_concern":
        payload.setdefault("meta", {})["intent"] = "price_concern"
    if consult_meta:
        payload.setdefault("meta", {}).update(consult_meta)
    payload = _apply_response_policy_compat(
        payload,
        st,
        q,
        topic_state=tstate,
        doc_meta=meta,
        pre_doc_turn_count=pre_turn,
        session_id=sid,
        client_id=client_id,
    )
    refs_before_ui = list(payload.get("quick_replies") or [])
    payload = normalize_policy_payload(payload)
    payload.setdefault("meta", {})["generator_input"] = generator_input
    pdec = (payload.get("meta") or {}).get("policy_decision") or {}
    ui_dropped = set((payload.get("meta") or {}).get("ui_dropped") or [])
    if doc_id:
        if bool(pdec.get("show_video")):
            mark_video_shown(sid, doc_id)
        elif meta.get("video_key") and not bool(get_topic_state(sid, doc_id).get("video_shown")):
            mark_video_pending(sid, doc_id, pending=True)

        sit = payload.get("situation") or {}
        if sit.get("show") and sit.get("mode") == "normal":
            mark_situation_offered(sid, doc_id)

        if bool(pdec.get("defer_refs")):
            defer_refs(sid, doc_id, pdec.get("refs_to_defer") or [])
        elif "refs_with_two_followups_conflict" in ui_dropped and refs_before_ui:
            defer_refs(sid, doc_id, refs_before_ui[:1])
        elif payload.get("quick_replies"):
            _mark_suggest_ref_used_compat(sid, doc_id, True)
            tstate_after = get_topic_state(sid, doc_id)
            if tstate_after.get("refs_deferred"):
                pop_deferred_ref(sid, doc_id)

    if payload.get("cta") and doc_id:
        set_cta_shown(sid, doc_id, shown=True)

    verifier_src = verifier_effective_source_body(
        chunk_md_body=str(s0.get("content") or ""),
        generator_append_text=generator_append_text,
    )
    v_trace = build_turn_trace_prefix(
        answer=str(payload.get("answer") or answer),
        source_ref=str(generator_input.get("source_ref") or ""),
        source_text=verifier_src,
    )
    v_trace["verifier_source_has_deterministic_append"] = bool((generator_append_text or "").strip())
    try:
        from flask import has_request_context, request

        if has_request_context():
            request.ctx["verifier_turn"] = v_trace
    except Exception:
        pass
    final_answer = str(payload.get("answer") or answer)
    schedule_verifier_shadow_if_needed(
        answer=final_answer,
        source_text=verifier_src,
        source_ref=str(generator_input.get("source_ref") or ""),
        sid=sid,
        client_id=client_id,
        route=route,
        logger_=logger,
        trace_prefix=v_trace,
    )

    log_json(
        logger,
        log_event,
        file=chunk.get("file"),
        score=round(float(chunk.get("_score", 0.0)), 3),
        answer_length=len(final_answer),
        generator_input=generator_input,
        verifier_triggered=v_trace.get("verifier_triggered"),
        verifier_trigger_reason=v_trace.get("verifier_trigger_reason"),
    )
    qs = (q or "").strip()
    turn_meta = (
        {"interaction": "user_message", "question_len": len(qs), "preview": qs[:120]}
        if qs
        else None
    )
    out = finalize_ask(payload, sid, q, doc_id=doc_id, turn_meta=turn_meta, route=route)
    bot_text = str(out.get("answer") or answer).strip()
    if bot_text:
        mem_add_bot(sid, bot_text)
    return safe_jsonify(out)


def respond_from_chunk_stream(
    *,
    chunk: dict,
    q: str,
    sid: str,
    client_id: str | None,
    finalize_ask: Callable[..., dict],
    logger,
    llm_question: str | None = None,
    log_event: str = "Answer generated",
    route: str = "retrieval_chunk",
    generator_append_text: str | None = None,
):
    """Generator yielding SSE strings: typing → text_delta → ui → done.

    Используй с Flask: Response(respond_from_chunk_stream(...), mimetype='text/event-stream')
    Полностью зеркалит respond_from_chunk, но стримит токены ответа.
    """
    yield 'event: typing\ndata: {"phase": "searching"}\n\n'
    if (q or "").strip():
        mem_add_user(sid, q)
    meta = meta_for_chunk(chunk, client_id=client_id)
    if client_id is not None:
        meta["client_id"] = client_id
    doc_id = meta.get("doc_id")
    if doc_id:
        set_current_doc(sid, doc_id)

    sources = [build_generator_source_from_chunk(chunk, meta)]
    s0 = sources[0]
    generator_input = {
        "source_ref": s0.get("ref"),
        "source_count": 1,
        "route": route,
        "doc_id": s0.get("doc_id"),
        "doc_type": s0.get("doc_type"),
        "subtype": s0.get("subtype"),
        "h2_id": chunk.get("h2_id"),
        "h3_id": chunk.get("h3_id"),
    }

    tstate_pre = get_topic_state(sid, doc_id) if doc_id else {}
    planned_nudge = _planned_consult_nudge_for_chunk(
        sid=sid,
        route=route,
        meta=meta,
        chunk=chunk,
        topic_state=tstate_pre,
        client_id=client_id,
    )

    fmt_ctx = _answer_format_context(
        user_question=llm_question or q, chunk=chunk, meta=meta
    )
    stream_acc = StreamTextAccumulator(ctx=fmt_ctx)
    full_text = ""
    profile: dict = {}
    writing_phase_sent = False

    def _yield_delta(display_delta: str) -> str:
        return (
            f"event: text_delta\ndata: "
            f"{_json.dumps({'delta': display_delta}, ensure_ascii=False)}\n\n"
        )

    try:
        for event_type, value in generate_answer_stream(
            llm_question or q, sources, meta, sid
        ):
            if event_type == "delta":
                full_text += value
                if not writing_phase_sent:
                    writing_phase_sent = True
                    yield 'event: typing\ndata: {"phase": "writing"}\n\n'
                out = stream_acc.ingest_llm_delta(value)
                if out:
                    yield _yield_delta(out)
            elif event_type == "done":
                full_text, profile = value
    except Exception as e:
        log_json(logger, "stream_chunk_failed", sid=sid, err=str(e)[:300])
        if not full_text.strip():
            full_text = LLM_FALLBACK_ANSWER

    raw_final = ensure_answer(full_text, chunk)
    if not writing_phase_sent and (raw_final or "").strip():
        writing_phase_sent = True
        yield 'event: typing\ndata: {"phase": "writing"}\n\n'

    tail = stream_acc.finalize(raw_final)
    if tail:
        yield _yield_delta(tail)

    answer_base = format_answer_for_display(raw_final, fmt_ctx)
    answer = _append_generator_append_text(answer_base, generator_append_text)
    append_delta = answer[stream_acc.display_sent_len :]
    if append_delta:
        yield _yield_delta(append_delta)
        stream_acc.display_sent_len = len(answer)

    # Все session side-effects — идентично respond_from_chunk
    st = mem_get(sid)
    lead_flow_active = is_active_lead_flow(st)
    pre_turn = _increment_doc_turn_with_pre(
        sid,
        doc_id,
        contentful=bool(answer.strip()),
        is_low_score=False,
        is_error=False,
        lead_flow_active=lead_flow_active,
    )
    tstate = get_topic_state(sid, doc_id) if doc_id else {}
    suggest_h3 = set(meta.get("suggest_h3") or [])
    h3_id = chunk.get("h3_id")
    if h3_id and h3_id in suggest_h3:
        mark_h3_covered(sid, doc_id, h3_id)
        tstate = get_topic_state(sid, doc_id)

    consult_meta = record_consult_nudge_after_answer(
        sid, route, planned_nudge, answer
    )

    payload = build_ask_response(
        answer=answer,
        top=chunk,
        meta=meta,
        sid=sid,
        profile=profile,
        client_id=client_id,
        topic_state=tstate,
    )
    if route:
        payload.setdefault("meta", {})["orch_route"] = route
    if route == "price_concern":
        payload.setdefault("meta", {})["intent"] = "price_concern"
    if consult_meta:
        payload.setdefault("meta", {}).update(consult_meta)
    payload = _apply_response_policy_compat(
        payload,
        st,
        q,
        topic_state=tstate,
        doc_meta=meta,
        pre_doc_turn_count=pre_turn,
        session_id=sid,
        client_id=client_id,
    )
    refs_before_ui = list(payload.get("quick_replies") or [])
    payload = normalize_policy_payload(payload)
    payload.setdefault("meta", {})["generator_input"] = generator_input
    pdec = (payload.get("meta") or {}).get("policy_decision") or {}
    ui_dropped = set((payload.get("meta") or {}).get("ui_dropped") or [])

    if doc_id:
        if bool(pdec.get("show_video")):
            mark_video_shown(sid, doc_id)
        elif meta.get("video_key") and not bool(get_topic_state(sid, doc_id).get("video_shown")):
            mark_video_pending(sid, doc_id, pending=True)
        sit = payload.get("situation") or {}
        if sit.get("show") and sit.get("mode") == "normal":
            mark_situation_offered(sid, doc_id)
        if bool(pdec.get("defer_refs")):
            defer_refs(sid, doc_id, pdec.get("refs_to_defer") or [])
        elif "refs_with_two_followups_conflict" in ui_dropped and refs_before_ui:
            defer_refs(sid, doc_id, refs_before_ui[:1])
        elif payload.get("quick_replies"):
            _mark_suggest_ref_used_compat(sid, doc_id, True)
            tstate_after = get_topic_state(sid, doc_id)
            if tstate_after.get("refs_deferred"):
                pop_deferred_ref(sid, doc_id)

    if payload.get("cta") and doc_id:
        set_cta_shown(sid, doc_id, shown=True)

    verifier_src = verifier_effective_source_body(
        chunk_md_body=str(s0.get("content") or ""),
        generator_append_text=generator_append_text,
    )
    v_trace = build_turn_trace_prefix(
        answer=str(payload.get("answer") or answer),
        source_ref=str(generator_input.get("source_ref") or ""),
        source_text=verifier_src,
    )
    v_trace["verifier_source_has_deterministic_append"] = bool((generator_append_text or "").strip())
    try:
        from flask import has_request_context, request

        if has_request_context():
            request.ctx["verifier_turn"] = v_trace
    except Exception:
        pass
    final_answer = str(payload.get("answer") or answer)
    schedule_verifier_shadow_if_needed(
        answer=final_answer,
        source_text=verifier_src,
        source_ref=str(generator_input.get("source_ref") or ""),
        sid=sid,
        client_id=client_id,
        route=route,
        logger_=logger,
        trace_prefix=v_trace,
    )

    log_json(
        logger,
        log_event,
        file=chunk.get("file"),
        score=round(float(chunk.get("_score", 0.0)), 3),
        answer_length=len(final_answer),
        generator_input=generator_input,
        verifier_triggered=v_trace.get("verifier_triggered"),
        verifier_trigger_reason=v_trace.get("verifier_trigger_reason"),
    )
    qs = (q or "").strip()
    turn_meta = (
        {"interaction": "user_message", "question_len": len(qs), "preview": qs[:120]}
        if qs
        else None
    )
    final = finalize_ask(payload, sid, q, doc_id=doc_id, turn_meta=turn_meta, route=route)
    bot_text = str(final.get("answer") or final_answer).strip()
    if bot_text:
        mem_add_bot(sid, bot_text)
    yield f"event: ui\ndata: {_json.dumps(final, ensure_ascii=False, default=_sse_default)}\n\n"
    yield "event: done\ndata: {}\n\n"


def _sse_default(obj):
    """JSON default для SSE — обрабатывает numpy типы из retrieval."""
    try:
        import numpy as np
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
    except ImportError:
        pass
    if isinstance(obj, set):
        return list(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
