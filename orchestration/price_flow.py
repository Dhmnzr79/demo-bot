from __future__ import annotations

from typing import Any

from flask import request

from contracts.ask_orchestration import AskOrchestrationResult
from contracts.source_route_result import SourceRouteResult
from logging_setup import get_logger, log_json
from retriever import get_chunk_by_ref
from session import set_last_catalog_service
from ux_builder import (
    build_price_clarify_payload,
    build_price_concern_payload,
    build_price_lookup_payload,
)

logger = get_logger("bot")


def price_matched_from_route(
    *,
    q: str,
    sid: str,
    client_id: str,
    price_route: dict,
    decision,
    decision_frame: dict[str, Any] | None,
) -> AskOrchestrationResult:
    intent = str(price_route.get("intent") or "other")
    request.ctx["effective_intent"] = str(intent)
    service = price_route.get("service") or {}
    service_id = str(price_route.get("matched_service_id") or "")
    match_score = float(price_route.get("match_score") or 0.0)
    route_source = str(price_route.get("route_source") or "catalog")
    if service_id:
        set_last_catalog_service(sid, service_id)
    if intent == "price_concern":
        concern_ref = str(service.get("concern_ref") or "").strip()
        if concern_ref:
            ch = get_chunk_by_ref(concern_ref, client_id=client_id)
            if ch:
                log_json(
                    logger,
                    "price_route",
                    intent="price_concern",
                    matched_service_id=service_id,
                    match_score=round(match_score, 4),
                    route_source="concern_ref",
                    concern_ref=concern_ref,
                    fallback_reason=None,
                )
                return AskOrchestrationResult(
                    kind="chunk",
                    q=q,
                    sid=sid,
                    client_id=client_id,
                    chosen_chunk=ch,
                    llm_question=q,
                    log_event="Answer generated from concern_ref",
                    chunk_route="price_concern",
                    decision_frame=decision_frame,
                )
        payload = build_price_concern_payload(
            sid=sid,
            client_id=client_id,
            service_id=service_id,
            service=service,
            match_score=match_score,
        )
        log_json(logger, "price_route", **payload.get("meta") or {})
        return AskOrchestrationResult(
            kind="service_reply",
            q=q,
            sid=sid,
            client_id=client_id,
            service_payload=payload,
            service_doc_id=None,
            service_track_user=True,
            service_route="price_concern",
            decision_frame=decision_frame,
        )
    if route_source == "price_ref" and price_route.get("price_ref"):
        ref_px = str(price_route.get("price_ref") or "").strip()
        ch = get_chunk_by_ref(ref_px, client_id=client_id)
        if ch:
            log_json(
                logger,
                "price_route",
                intent="price_lookup",
                matched_service_id=service_id,
                match_score=round(match_score, 4),
                route_source="price_ref",
                price_key=price_route.get("price_key"),
                price_ref=ref_px,
                fallback_reason=price_route.get("fallback_reason"),
            )
            q0 = (q or "").strip()
            llmq = (
                f"{q0}\n\n"
                "Ответь по ценам только из материала ниже. "
                "Без вступлений вроде «такая услуга есть», «стоимость составляет». "
                "Сразу по сути, цифры только из текста."
            )
            if str(price_route.get("fallback_reason") or "") == "context_session":
                svc_ctx = price_route.get("service") if isinstance(price_route.get("service"), dict) else {}
                ttl = str(svc_ctx.get("title") or price_route.get("matched_service_id") or "").strip()
                if ttl:
                    llmq = (
                        f"{llmq}\n\n"
                        f"Контекст: пользователь продолжает вопрос об услуге «{ttl}». "
                        "Упомяни в ответе это название или короткий синоним из каталога "
                        "(например all-on-4), чтобы было ясно, о какой услуге речь."
                    )
            return AskOrchestrationResult(
                kind="chunk",
                q=q,
                sid=sid,
                client_id=client_id,
                chosen_chunk=ch,
                llm_question=llmq,
                log_event="Answer generated from price_ref",
                chunk_route="price_lookup",
                decision_frame=decision_frame,
            )
    payload = build_price_lookup_payload(
        sid=sid,
        client_id=client_id,
        service_id=service_id,
        service=service,
        match_score=match_score,
        route_source=route_source,
        price_key=price_route.get("price_key"),
        price_ref=price_route.get("price_ref"),
        price_item=price_route.get("price_item"),
    )
    log_json(logger, "price_route", **payload.get("meta") or {})
    return AskOrchestrationResult(
        kind="service_reply",
        q=q,
        sid=sid,
        client_id=client_id,
        service_payload=payload,
        service_doc_id=None,
        service_track_user=True,
        service_route="price_lookup",
        decision_frame=decision_frame,
    )


def try_a3_price_route(
    *,
    q: str,
    sid: str,
    client_id: str,
    sr: SourceRouteResult,
    decision,
    decision_frame: dict[str, Any] | None,
) -> AskOrchestrationResult | None:
    if sr.source in ("price_card", "price_ref"):
        pr_inner = (sr.payload or {}).get("price_route") if isinstance(sr.payload, dict) else None
        if isinstance(pr_inner, dict):
            return price_matched_from_route(
                q=q,
                sid=sid,
                client_id=client_id,
                price_route=pr_inner,
                decision=decision,
                decision_frame=decision_frame,
            )
    if sr.source == "price_concern" and sr.ref:
        ch = get_chunk_by_ref(sr.ref, client_id=client_id)
        if ch:
            log_json(
                logger,
                "price_route",
                intent="price_concern",
                matched_service_id=sr.service_id,
                match_score=round(float(sr.match_score or 0.0), 4),
                route_source="concern_ref",
                concern_ref=str(sr.concern_ref or sr.ref),
                fallback_reason=str(sr.match_method),
            )
            return AskOrchestrationResult(
                kind="chunk",
                q=q,
                sid=sid,
                client_id=client_id,
                chosen_chunk=ch,
                llm_question=q,
                log_event="Answer generated from concern_ref",
                chunk_route="price_concern",
                decision_frame=decision_frame,
            )
    if sr.source == "price_lookup_clarify" and isinstance(sr.payload, dict):
        pr_cl = sr.payload.get("price_route")
        if isinstance(pr_cl, dict):
            request.ctx["effective_intent"] = "price_lookup"
            payload_cl = build_price_clarify_payload(
                sid=sid,
                client_id=client_id,
                intent=str(pr_cl.get("intent") or "price_lookup"),
                fallback_reason=str(pr_cl.get("fallback_reason") or "service_not_found"),
                question=q,
            )
            log_json(logger, "price_route", **payload_cl.get("meta") or {})
            return AskOrchestrationResult(
                kind="service_reply",
                q=q,
                sid=sid,
                client_id=client_id,
                service_payload=payload_cl,
                service_doc_id=None,
                service_track_user=True,
                service_route="price_lookup",
                decision_frame=decision_frame,
            )
    return None


def price_lookup_intent_fallback(
    *,
    q: str,
    sid: str,
    client_id: str,
    decision,
    decision_frame: dict[str, Any] | None,
    select_price_service_route,
) -> AskOrchestrationResult | None:
    price_route = select_price_service_route(
        q, client_id=client_id, sid=sid, intent_override="price_lookup"
    )
    if price_route.get("mode") == "clarify":
        payload = build_price_clarify_payload(
            sid=sid,
            client_id=client_id,
            intent=str(price_route.get("intent") or "other"),
            fallback_reason=str(price_route.get("fallback_reason") or "service_not_found"),
            question=q,
        )
        log_json(logger, "price_route", **payload.get("meta") or {})
        return AskOrchestrationResult(
            kind="service_reply",
            q=q,
            sid=sid,
            client_id=client_id,
            service_payload=payload,
            service_doc_id=None,
            service_track_user=True,
            service_route="price_lookup",
            decision_frame=decision_frame,
        )
    if price_route.get("mode") == "matched":
        return price_matched_from_route(
            q=q,
            sid=sid,
            client_id=client_id,
            price_route=price_route,
            decision=decision,
            decision_frame=decision_frame,
        )
    return None
