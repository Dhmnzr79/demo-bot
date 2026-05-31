from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import request

from contracts.ask_orchestration import AskOrchestrationResult
from logging_setup import emit_bot_event, get_logger
from orchestration.catalog_flow import (
    catalog_md_priority_from_a3,
    try_a3_catalog_facts,
    try_a3_doctor_route,
)
from orchestration.helpers import decision_dump
from orchestration.price_flow import price_lookup_intent_fallback, try_a3_price_route
from orchestration.retrieval_flow import run_content_arbiter_path, run_selection_fallback
from policy import contacts_intent, pick_contacts_chunk
from query_selector import select_price_service_route
from retriever import get_chunk_by_ref, normalize_retrieval_query, retrieve
from source_routing import route_source, slim_source_route_payload

logger = get_logger("bot")


def orchestrate_routing_after_resolver(
    *,
    q: str,
    sid: str,
    client_id: str,
    intent: str,
    decision,
    scope_topic_candidate: str | None,
    resolver_bypassed_env: bool,
    data: dict,
    client_txt: Callable[[str | None], dict[str, str]],
    service_payload: Callable[..., dict],
    lead_flow_from_result: Callable[..., AskOrchestrationResult],
    apply_response_policy: Callable[..., dict],
) -> AskOrchestrationResult:
    """
    Post-Resolver routing: contacts overlay → A3 source_routing → price fallback → content/retrieval.
    Extracted from app._orchestrate_ask_turn (Phase 3c).
    """
    decision_frame = decision_dump(decision)

    qp_loc = normalize_retrieval_query(q) or (q or "")
    if contacts_intent(qp_loc.strip()) or contacts_intent((q or "").strip()):
        intent = "contacts"
        scope_topic_candidate = None
        request.ctx["retrieval_scope_topic"] = None
        request.ctx["retrieval_scope_guard_reason"] = "none"
        request.ctx["effective_intent"] = "contacts"

    if intent == "contacts":
        cands = retrieve(q, topk=24, client_id=client_id, scope_topic=None)
        picked = pick_contacts_chunk(cands)
        if picked is None:
            picked = get_chunk_by_ref("clinic__info__contacts.md#korotko", client_id=client_id)
        if picked:
            return AskOrchestrationResult(
                kind="chunk",
                q=q,
                sid=sid,
                client_id=client_id,
                chosen_chunk=picked,
                llm_question=q,
                log_event="Answer generated from contacts intent",
                chunk_route="contacts_chunk",
                decision_frame=decision_frame,
            )

    md_catalog_priority_ref = None
    md_catalog_priority_sid = None
    md_catalog_priority_score = None

    if intent != "contacts":
        sr = route_source(q, sid=sid, client_id=client_id, decision=decision, app_intent=intent)
        srd = slim_source_route_payload(sr)
        request.ctx["source_route_decision"] = srd
        emit_bot_event(logger, "source_route_decision", status="ok", details=srd)

        doc_result = try_a3_doctor_route(
            q=q,
            sid=sid,
            client_id=client_id,
            sr=sr,
            decision_frame=decision_frame,
        )
        if doc_result is not None:
            return doc_result

        facts_result = try_a3_catalog_facts(
            q=q,
            sid=sid,
            client_id=client_id,
            sr=sr,
            decision_frame=decision_frame,
        )
        if facts_result is not None:
            return facts_result

        md_prio = catalog_md_priority_from_a3(sr)
        if md_prio is not None:
            md_catalog_priority_ref = md_prio.ref
            md_catalog_priority_sid = md_prio.service_id
            md_catalog_priority_score = md_prio.match_score

        price_result = try_a3_price_route(
            q=q,
            sid=sid,
            client_id=client_id,
            sr=sr,
            decision=decision,
            decision_frame=decision_frame,
        )
        if price_result is not None:
            return price_result
    else:
        request.ctx["source_route_decision"] = {
            "source": "contacts",
            "ref": None,
            "service_id": None,
            "concern_ref": None,
            "match_method": "none",
            "match_score": 0.0,
        }

    if intent == "price_lookup":
        price_fb = price_lookup_intent_fallback(
            q=q,
            sid=sid,
            client_id=client_id,
            decision=decision,
            decision_frame=decision_frame,
            select_price_service_route=select_price_service_route,
        )
        if price_fb is not None:
            return price_fb

    if intent == "content" or md_catalog_priority_ref:
        return run_content_arbiter_path(
            q=q,
            sid=sid,
            client_id=client_id,
            intent=intent,
            decision=decision,
            decision_frame=decision_frame,
            scope_topic_candidate=scope_topic_candidate,
            resolver_bypassed_env=resolver_bypassed_env,
            md_catalog_priority_ref=md_catalog_priority_ref,
            md_catalog_priority_sid=md_catalog_priority_sid,
            md_catalog_priority_score=md_catalog_priority_score,
            data=data,
            client_txt=client_txt,
            service_payload=service_payload,
            lead_flow_from_result=lead_flow_from_result,
            apply_response_policy=apply_response_policy,
        )

    return run_selection_fallback(
        q=q,
        sid=sid,
        client_id=client_id,
        decision_frame=decision_frame,
        scope_topic_candidate=scope_topic_candidate,
        apply_response_policy=apply_response_policy,
    )
