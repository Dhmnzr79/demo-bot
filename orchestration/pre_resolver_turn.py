from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import request

from config import (
    ANTI_SPAM_BURST_MESSAGES,
    ANTI_SPAM_BURST_WINDOW_SEC,
    INPUT_MAX_CHARS,
)
from contracts.ask_orchestration import AskOrchestrationResult
from flow_handlers import handle_flows, resume_active_lead_flow
from ingress_gate import build_ingress_payload, classify_ingress, ingress_service_route
from logging_setup import get_logger, log_json
from orchestration.context import AskTurnContext
from orchestration.helpers import decision_dump
from orchestration.lead_flow import lead_flow_orchestration_result
from orchestration.route_guards import (
    check_rate_limit,
    continuation_clarify_payload,
    duplicate_payload,
    is_duplicate_question,
    is_message_burst,
    is_obvious_noise,
    is_short_contextual,
    normalize_question_text,
    obvious_noise_ingress_result,
    rate_limited_response_payload,
    should_soft_redirect_no_intent,
    soft_redirect_payload,
)
from policy import continuation_only_phrase, continuation_without_context
from retriever import get_chunk_by_ref
from session import (
    get_topic_state,
    is_active_lead_flow,
    mem_get,
    mem_reset,
    set_anti_spam_redirect_shown,
    sid_from_body,
)
from ux_builder import empty_question_response

logger = get_logger("bot")


def run_pre_resolver_turn(
    data: dict,
    *,
    resolve_client_id: Callable[..., str | None],
    bind_chat_ctx: Callable[[str, str], None],
    resolve_ip: Callable[[], str],
    client_txt: Callable[[str | None], dict[str, str]],
    service_payload: Callable[..., dict],
    get_last_content_ui_payload: Callable[[str], dict | None],
) -> AskOrchestrationResult | AskTurnContext:
    """
    Pre-Resolver pipeline: client/reset/rate/noise/ingress/flows/guards/ref/continuation.
    Extracted from app._orchestrate_ask_turn (Phase 3d).
    """
    decision = None
    client_id = resolve_client_id(data.get("client_id"), host=request.host)
    if client_id is None:
        return AskOrchestrationResult(
            kind="unknown_client",
            client_error={"error": "unknown_client"},
            http_status=403,
        )

    q_raw = data.get("q") or ""
    q = (q_raw or "").strip()
    ref = (data.get("ref") or "").strip()
    sid = sid_from_body(data)

    if q and q.lower() in ("/reset", "/новая"):
        bind_chat_ctx(sid, client_id)
        mem_reset(sid)
        return AskOrchestrationResult(kind="reset_session", q=q, sid=sid, client_id=client_id)

    q, truncated = normalize_question_text(q_raw)
    bind_chat_ctx(sid, client_id)
    request.ctx["retrieval_scope_topic"] = None
    request.ctx["retrieval_scope_guard_reason"] = "none"
    request.ctx["retrieval_scope_widen_fallback"] = False
    request.ctx["legacy_intent"] = None
    request.ctx["effective_intent"] = None

    if truncated:
        log_json(
            logger,
            "input_truncated",
            sid=sid,
            client_id=client_id,
            original_len=len((q_raw or "").strip()),
            max_len=INPUT_MAX_CHARS,
        )

    ip = resolve_ip()
    if not check_rate_limit(ip):
        log_json(logger, "rate_limited", sid=sid, client_id=client_id, ip=ip)
        return AskOrchestrationResult(
            kind="service_reply",
            q=q,
            sid=sid,
            client_id=client_id,
            service_payload=rate_limited_response_payload(),
            service_route="rate_limited",
            http_status=429,
        )

    st = mem_get(sid)
    decision_frame = decision_dump(decision)

    if is_obvious_noise(q) and not is_active_lead_flow(st):
        noise_res = obvious_noise_ingress_result()
        log_json(logger, "obvious_noise_short_circuit", sid=sid, client_id=client_id)
        return AskOrchestrationResult(
            kind="service_reply",
            q=q,
            sid=sid,
            client_id=client_id,
            service_payload=build_ingress_payload(
                noise_res, sid=sid, client_id=client_id, question=q
            ),
            service_doc_id=None,
            service_track_user=True,
            service_route=ingress_service_route(noise_res),
            decision_frame=decision_frame,
        )

    ingress_skip = (
        bool(ref)
        or is_active_lead_flow(st)
        or bool(st.get("situation_pending"))
        or bool(st.get("pending_lead_offer"))
    )
    if q and not ingress_skip:
        ingress_res = classify_ingress(q, client_id=client_id, sid=sid, skip=False)
        log_json(
            logger,
            "ingress_gate",
            sid=sid,
            client_id=client_id,
            route=ingress_res.route,
            reason=ingress_res.reason[:64],
            confidence=round(float(ingress_res.confidence), 4),
            source=ingress_res.source,
        )
        if ingress_res.route != "normal":
            return AskOrchestrationResult(
                kind="service_reply",
                q=q,
                sid=sid,
                client_id=client_id,
                service_payload=build_ingress_payload(
                    ingress_res, sid=sid, client_id=client_id, question=q
                ),
                service_doc_id=None,
                service_track_user=True,
                service_route=ingress_service_route(ingress_res),
                decision_frame=decision_frame,
            )

    flow_result = handle_flows(
        data=data,
        st=st,
        sid=sid,
        q=q,
        client_id=client_id,
        txt=client_txt(client_id),
        service_payload=service_payload,
        get_last_content_ui_payload=get_last_content_ui_payload,
        get_topic_state=get_topic_state,
    )
    if flow_result is not None:
        return lead_flow_orchestration_result(
            q=q, sid=sid, client_id=client_id, flow_result=flow_result, decision=decision
        )

    st = mem_get(sid)
    if is_active_lead_flow(st) and (q or "").strip():
        flow_result = resume_active_lead_flow(
            data=data,
            sid=sid,
            q=q,
            client_id=client_id,
            txt=client_txt(client_id),
            service_payload=service_payload,
        )
        if flow_result is not None:
            log_json(logger, "lead_flow_resume", sid=sid, client_id=client_id)
            return lead_flow_orchestration_result(
                q=q, sid=sid, client_id=client_id, flow_result=flow_result, decision=decision
            )

    if is_duplicate_question(st, q):
        snap = get_last_content_ui_payload(sid)
        log_json(logger, "duplicate_short_circuit", sid=sid, client_id=client_id)
        return AskOrchestrationResult(
            kind="service_reply",
            q=q,
            sid=sid,
            client_id=client_id,
            service_payload=duplicate_payload(sid, client_id, snap),
            service_doc_id=None,
            service_track_user=True,
            service_route="duplicate_short_circuit",
            decision_frame=decision_frame,
        )

    if not is_active_lead_flow(st):
        if is_message_burst(st):
            set_anti_spam_redirect_shown(sid, True)
            log_json(
                logger,
                "anti_spam_burst_redirect",
                sid=sid,
                client_id=client_id,
                burst_window_sec=ANTI_SPAM_BURST_WINDOW_SEC,
                burst_messages=ANTI_SPAM_BURST_MESSAGES,
            )
            return AskOrchestrationResult(
                kind="service_reply",
                q=q,
                sid=sid,
                client_id=client_id,
                service_payload=soft_redirect_payload(sid, client_id),
                service_doc_id=None,
                service_track_user=True,
                service_route="booking_flow",
                decision_frame=decision_frame,
            )
        if should_soft_redirect_no_intent(st):
            set_anti_spam_redirect_shown(sid, True)
            log_json(
                logger,
                "anti_spam_soft_redirect",
                sid=sid,
                client_id=client_id,
                session_turn_count=int(st.get("session_turn_count") or 0),
            )
            return AskOrchestrationResult(
                kind="service_reply",
                q=q,
                sid=sid,
                client_id=client_id,
                service_payload=soft_redirect_payload(sid, client_id),
                service_doc_id=None,
                service_track_user=True,
                service_route="booking_flow",
                decision_frame=decision_frame,
            )

    if ref:
        ch = get_chunk_by_ref(ref, client_id=client_id)
        if ch:
            return AskOrchestrationResult(
                kind="chunk",
                q=q,
                sid=sid,
                client_id=client_id,
                chosen_chunk=ch,
                llm_question=q or f"Информация из {ref}",
                log_event="Answer generated from ref",
                chunk_route="retrieval_chunk",
                decision_frame=decision_frame,
            )

    if not q:
        return AskOrchestrationResult(
            kind="service_reply",
            q=q,
            sid=sid,
            client_id=client_id,
            service_payload=empty_question_response(client_id),
            service_doc_id=None,
            service_track_user=False,
            service_route="error",
            decision_frame=decision_frame,
        )

    if continuation_without_context(q, st):
        log_json(logger, "continuation_no_context", sid=sid, client_id=client_id)
        return AskOrchestrationResult(
            kind="service_reply",
            q=q,
            sid=sid,
            client_id=client_id,
            service_payload=continuation_clarify_payload(sid, client_id),
            service_doc_id=None,
            service_track_user=True,
            service_route="continuation_clarify",
            decision_frame=decision_frame,
        )

    current_doc_id = (st.get("current_doc_id") or "").strip()
    if current_doc_id and continuation_only_phrase(q):
        ch = get_chunk_by_ref(f"{current_doc_id}#korotko", client_id=client_id)
        if ch:
            return AskOrchestrationResult(
                kind="chunk",
                q=q,
                sid=sid,
                client_id=client_id,
                chosen_chunk=ch,
                llm_question=q,
                log_event="Answer from continuation topic fallback",
                chunk_route="retrieval_chunk",
                decision_frame=decision_frame,
            )

    if is_short_contextual(q, st) and current_doc_id:
        ch = get_chunk_by_ref(f"{current_doc_id}#korotko", client_id=client_id)
        if ch:
            return AskOrchestrationResult(
                kind="chunk",
                q=q,
                sid=sid,
                client_id=client_id,
                chosen_chunk=ch,
                llm_question=q,
                log_event="Answer from short_contextual fallback",
                chunk_route="retrieval_chunk",
                decision_frame=decision_frame,
            )

    return AskTurnContext(q=q, sid=sid, client_id=client_id, ref=ref, data=data, st=st)
