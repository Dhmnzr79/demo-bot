from __future__ import annotations

import json
import os
from typing import Any

from flask import request

from core.client_config_loader import load_ui_bundle, ui_menu_to_payload
from logging_setup import emit_bot_event, get_logger
from query_selector import compute_retrieval_scope_with_conflict_guard
from retriever import chunk_info
from ux_builder import format_price_answer_from_item

logger = get_logger("bot")


def decision_dump(decision) -> dict[str, Any] | None:
    return decision.model_dump() if decision is not None else None


def get_last_content_ui_payload_compat(sid: str) -> dict | None:
    import session as session_mod

    fn = getattr(session_mod, "get_last_content_ui_payload", None)
    if callable(fn):
        return fn(sid)
    return None


def with_default_anchor(md_entry_ref: str) -> str:
    ref = (md_entry_ref or "").strip()
    if not ref:
        return ""
    return ref if "#" in ref else f"{ref}#korotko"


def load_prices_for_client(client_id: str | None) -> dict:
    from core.client_runtime import client_pack_dir

    p = os.path.join(client_pack_dir(client_id), "prices.json")
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def service_price_line_for_content(service: dict, client_id: str | None) -> str | None:
    if not isinstance(service, dict):
        return None
    if str(service.get("price_display") or "").strip().lower() != "always":
        return None
    price_key = str(service.get("price_key") or "").strip()
    if not price_key:
        return None
    prices = load_prices_for_client(client_id)
    price_item = prices.get(price_key) if isinstance(prices, dict) else None
    if not isinstance(price_item, dict):
        return None
    title = str(service.get("title") or price_key).strip()
    return format_price_answer_from_item(price_item, title_fallback=title)


def apply_content_retrieval_scope_ctx(
    scope_topic_candidate: str | None,
    q: str,
    client_id: str,
) -> str | None:
    eff, gr = compute_retrieval_scope_with_conflict_guard(
        scope_topic_candidate=scope_topic_candidate,
        q=q,
        client_id=client_id,
    )
    request.ctx["retrieval_scope_topic"] = eff
    request.ctx["retrieval_scope_guard_reason"] = gr
    return eff


def guided_menu_payload(sid: str, client_id: str | None) -> dict:
    ui = load_ui_bundle(client_id)
    return ui_menu_to_payload(ui.guided_menu, sid=sid, client_id=client_id)


def ru_doctor_count_word(n: int) -> str:
    n_abs = abs(int(n))
    n10 = n_abs % 10
    n100 = n_abs % 100
    if n10 == 1 and n100 != 11:
        return "врач"
    if n10 in (2, 3, 4) and n100 not in (12, 13, 14):
        return "врача"
    return "врачей"


def slim_content_arbiter_details(details: dict) -> dict:
    if not isinstance(details, dict):
        return {}
    out = dict(details)
    cands = out.get("candidates")
    if isinstance(cands, dict):
        c2 = dict(cands)
        ret = c2.get("retrieval_candidate")
        if isinstance(ret, dict):
            r2 = dict(ret)
            r2.pop("chunk", None)
            c2["retrieval_candidate"] = r2
        alias_c = c2.get("alias_candidate")
        if isinstance(alias_c, dict):
            a2 = dict(alias_c)
            leader = a2.get("leader")
            if isinstance(leader, dict):
                leader2 = dict(leader)
                leader2.pop("text", None)
                a2["leader"] = leader2
            a2.pop("leader_chunk", None)
            c2["alias_candidate"] = a2
        out["candidates"] = c2
    return out


def log_selection(
    *,
    q: str,
    chosen_chunk: dict,
    chosen_score,
    original_top_score,
    rerank_applied: bool,
) -> None:
    chosen = chunk_info(chosen_chunk, chosen_score)
    from logging_setup import log_json

    log_json(
        logger,
        "selection",
        question=q[:200],
        original_top_score=(
            round(float(original_top_score), 4) if original_top_score is not None else None
        ),
        rerank_applied=bool(rerank_applied),
        chosen=chosen,
    )
    emit_bot_event(
        logger,
        "retrieval_selected",
        status="chunk",
        details={
            "question_preview": (q or "")[:200],
            "original_top_score": (
                round(float(original_top_score), 4) if original_top_score is not None else None
            ),
            "rerank_applied": bool(rerank_applied),
            "chosen": chosen,
        },
    )
