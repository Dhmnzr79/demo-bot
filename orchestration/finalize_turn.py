from __future__ import annotations

import time
from typing import Any

from flask import request

from logging_setup import emit_bot_event, get_logger, redact_text
from session import get_topic_state, mem_get, record_last_bot_payload

logger = get_logger("bot")


def verifier_trace_flat(v: Any) -> dict[str, Any]:
    """Поля A7 для bot_event details (без лишних ключей)."""
    if not isinstance(v, dict):
        return {}
    return {k: val for k, val in v.items() if str(k).startswith("verifier_")}


def infer_route_from_payload(payload: dict) -> str:
    """Telemetry route для PG/JSONL (не smoke contract)."""
    meta = payload.get("meta") or {}
    if meta.get("error") == "rate_limited":
        return "rate_limited"
    if bool(meta.get("low_score")):
        return "low_score_fallback"
    if bool(meta.get("lead_flow")):
        return "lead_flow"
    ingress_route = str(meta.get("ingress_route") or "").strip().lower()
    if ingress_route and ingress_route != "normal":
        return f"ingress_{ingress_route}"
    if bool(meta.get("handoff_filter")):
        return "handoff_filter"
    intent = str(meta.get("intent") or "").strip().lower()
    if intent == "catalog_facts":
        return "catalog_facts"
    if intent == "offtopic":
        return "offtopic"
    return "retrieval_chunk"


def finalize_ask(
    payload: dict,
    sid: str,
    q: str,
    *,
    doc_id: str | None = None,
    turn_meta: dict | None = None,
    route: str | None = None,
) -> dict:
    record_last_bot_payload(sid, payload)
    st = mem_get(sid)
    meta = payload.setdefault("meta", {})
    session_turn_count = int(st.get("session_turn_count") or 0)
    if doc_id:
        tstate = get_topic_state(sid, doc_id)
        meta["turn_count"] = int(tstate.get("doc_turn_count") or 0)
    else:
        meta["turn_count"] = session_turn_count
    meta["session_turn_count"] = session_turn_count

    if turn_meta and turn_meta.get("interaction") == "user_message":
        emit_bot_event(logger, "user_turn_completed", status="ok", details=turn_meta)
    effective_route = str(route or request.ctx.get("route") or infer_route_from_payload(payload))
    request.ctx["route"] = effective_route
    pmeta = payload.get("meta") or {}
    answer_text = str(payload.get("answer") or "")
    user_text_redacted = redact_text((q or ""), max_len=8000)
    user_preview_redacted = redact_text((q or ""), max_len=200)
    bot_text_redacted = redact_text(answer_text, max_len=8000)
    emit_bot_event(
        logger,
        "bot_reply_completed",
        status="ok",
        details={
            "answer_chars": len(answer_text),
            "doc_id": doc_id or pmeta.get("doc_id"),
            "low_score": bool(pmeta.get("low_score")),
            "handoff_filter": bool(pmeta.get("handoff_filter")),
            "lead_flow": bool(pmeta.get("lead_flow")),
            "intent": pmeta.get("intent"),
            "meta_error": pmeta.get("error"),
            "route": effective_route,
            "resolver_used": bool(request.ctx.get("resolver_used")),
            "safety_net_used": bool(request.ctx.get("safety_net_used")),
            **verifier_trace_flat(request.ctx.get("verifier_turn")),
        },
    )
    if turn_meta and turn_meta.get("interaction") == "user_message":
        t0 = request.ctx.get("turn_t0_monotonic")
        lat_ms = None
        if isinstance(t0, (int, float)):
            lat_ms = max(0, int((time.monotonic() - float(t0)) * 1000))
        emit_bot_event(
            logger,
            "turn_complete",
            status="ok",
            details={
                "turn_number": int(meta.get("session_turn_count") or 0),
                "user_text_redacted": user_text_redacted,
                "user_preview_redacted": user_preview_redacted,
                "bot_text_redacted": bot_text_redacted,
                "intent": pmeta.get("intent"),
                "doc_id": doc_id or pmeta.get("doc_id"),
                "route": effective_route,
                "low_score": bool(pmeta.get("low_score")),
                "lead_flow": bool(pmeta.get("lead_flow")),
                "handoff_filter": bool(pmeta.get("handoff_filter")),
                "answer_chars": len(answer_text),
                "latency_ms": lat_ms,
                "fallback_reason": pmeta.get("fallback_reason"),
                "resolver_used": bool(request.ctx.get("resolver_used")),
                "safety_net_used": bool(request.ctx.get("safety_net_used")),
                "retrieval_scope_topic": request.ctx.get("retrieval_scope_topic"),
                "retrieval_scope_guard_reason": str(
                    request.ctx.get("retrieval_scope_guard_reason") or "none"
                ),
                "retrieval_scope_widen_fallback": bool(
                    request.ctx.get("retrieval_scope_widen_fallback")
                ),
                "legacy_intent": request.ctx.get("legacy_intent"),
                "effective_intent": str(request.ctx.get("effective_intent") or ""),
                "source_route_decision": request.ctx.get("source_route_decision"),
                **verifier_trace_flat(request.ctx.get("verifier_turn")),
            },
        )
    cta = payload.get("cta")
    if isinstance(cta, dict) and (cta.get("action") or cta.get("text")):
        emit_bot_event(
            logger,
            "cta_shown",
            details={
                "action": str(cta.get("action") or ""),
                "text_preview": str(cta.get("text") or "")[:120],
            },
        )
    return payload
