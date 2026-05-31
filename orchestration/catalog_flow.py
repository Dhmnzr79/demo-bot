from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from flask import request

from contracts.ask_orchestration import AskOrchestrationResult
from contracts.source_route_result import SourceRouteResult
from doctors_lookup import build_doctors_list_llm_question, build_synthetic_doctors_list_chunk
from logging_setup import emit_bot_event, get_logger, log_json
from orchestration.helpers import ru_doctor_count_word, service_price_line_for_content
from retriever import get_chunk_by_ref
from session import set_last_catalog_service
from ux_builder import build_service_facts_card_payload

logger = get_logger("bot")


@dataclass(frozen=True)
class CatalogMdPriority:
    ref: str | None = None
    service_id: str | None = None
    match_score: float | None = None


def try_a3_doctor_route(
    *,
    q: str,
    sid: str,
    client_id: str,
    sr: SourceRouteResult,
    decision_frame: dict[str, Any] | None,
) -> AskOrchestrationResult | None:
    if sr.source != "doctor":
        return None
    doc_hit = (sr.payload or {}).get("doctor") if isinstance(sr.payload, dict) else None
    routing = str(doc_hit.get("routing") or "doc") if isinstance(doc_hit, dict) else "doc"
    if routing == "cards" and isinstance(doc_hit, dict):
        cards_raw = doc_hit.get("cards") or []
        if (
            isinstance(cards_raw, list)
            and len(cards_raw) >= 2
            and isinstance(cards_raw[0], dict)
            and cards_raw[0].get("name_full")
        ):
            syn = build_synthetic_doctors_list_chunk(client_id=client_id, facts=cards_raw)
            llmq_cards = build_doctors_list_llm_question(user_question=q or "", client_id=client_id)
            return AskOrchestrationResult(
                kind="chunk",
                q=q,
                sid=sid,
                client_id=client_id,
                chosen_chunk=syn,
                llm_question=llmq_cards,
                log_event="Answer generated from doctors_lookup (LLM list)",
                chunk_route="doctors_list",
                decision_frame=decision_frame,
            )
    if sr.ref:
        ch = get_chunk_by_ref(sr.ref, client_id=client_id)
        if ch:
            llmq = q or f"Информация о враче ({sr.ref})"
            if routing == "overview" and isinstance(doc_hit, dict):
                n_tot = doc_hit.get("matching_doctors_total")
                if isinstance(n_tot, int) and n_tot >= 4:
                    w = ru_doctor_count_word(n_tot)
                    llmq = (
                        f"{llmq}\n\nКонтекст: упомяни, что услугу делают ровно {n_tot} {w} "
                        "(точное число), без перечисления каждого по имени. "
                        "Предложи записаться на консультацию для подбора врача."
                    )
                elif n_tot == 0:
                    llmq = (
                        f"{llmq}\n\nКонтекст: узких врачей по этому направлению в карточках "
                        "сейчас нет — ответь по общему обзору клиники из материала."
                    )
            return AskOrchestrationResult(
                kind="chunk",
                q=q,
                sid=sid,
                client_id=client_id,
                chosen_chunk=ch,
                llm_question=llmq,
                log_event="Answer generated from doctors_lookup",
                chunk_route="retrieval_chunk",
                decision_frame=decision_frame,
            )
    return None


def try_a3_catalog_facts(
    *,
    q: str,
    sid: str,
    client_id: str,
    sr: SourceRouteResult,
    decision_frame: dict[str, Any] | None,
    route_label: str = "catalog_facts_a3",
) -> AskOrchestrationResult | None:
    if sr.source != "catalog_facts" or not sr.payload:
        return None
    svc = (sr.payload.get("service") or {}) if isinstance(sr.payload, dict) else {}
    sid_svc = str(sr.service_id or sr.payload.get("matched_service_id") or "")
    payload = build_service_facts_card_payload(
        sid=sid,
        client_id=client_id,
        service_id=sid_svc,
        service=svc,
        match_score=float(sr.match_score or 0.0),
        user_question=q,
    )
    price_line = service_price_line_for_content(svc, client_id)
    price_applied = False
    if price_line:
        base = (payload.get("answer") or "").strip()
        payload["answer"] = f"{base}\n\n{price_line}" if base else price_line
        payload.setdefault("meta", {})["price_display_applied"] = "always"
        price_applied = True
    log_json(
        logger,
        "catalog_route",
        route="facts",
        matched_service_id=sid_svc,
        match_score=sr.match_score,
    )
    if sid_svc:
        set_last_catalog_service(sid, sid_svc)
    emit_bot_event(
        logger,
        "content_arbiter_price_injection",
        status="ok",
        details={
            "selected_route": route_label,
            "price_line_applied": bool(price_applied),
            "matched_service_id": sid_svc,
        },
    )
    return AskOrchestrationResult(
        kind="service_reply",
        q=q,
        sid=sid,
        client_id=client_id,
        service_payload=payload,
        service_doc_id=None,
        service_track_user=True,
        service_route="catalog_facts",
        decision_frame=decision_frame,
    )


def catalog_md_priority_from_a3(sr: SourceRouteResult) -> CatalogMdPriority | None:
    if sr.source != "catalog_md" or not sr.ref:
        return None
    if str(sr.match_method or "") == "session_fallback":
        request.ctx["a3_catalog_md_session_hint"] = True
    return CatalogMdPriority(
        ref=sr.ref,
        service_id=sr.service_id,
        match_score=float(sr.match_score or 0.0),
    )
