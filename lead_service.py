"""Приём лида: режим из features.yaml + lead_config.yaml per client."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.client_config_loader import (
    leads_enabled,
    leads_mode,
    load_lead_config,
    tone_to_txt_dict,
)
from logging_setup import emit_bot_event, get_logger
from session import normalize_phone

logger = get_logger("bot")


def _success_message(client_id: str | None) -> str:
    lead_cfg = load_lead_config(client_id)
    key = str(lead_cfg.get("success_message_key") or "lead_submit_ok").strip()
    txt = tone_to_txt_dict(client_id)
    if key in txt:
        return txt[key]
    return txt.get("lead_submit_ok") or "Спасибо! Администратор свяжется с вами."


def handle_lead(data: dict[str, Any]) -> tuple[dict[str, Any], int]:
    client_id = (data.get("client_id") or "").strip() or None
    name = (data.get("name") or "").strip()
    phone = normalize_phone((data.get("phone") or "").strip() or "")
    intent = (data.get("intent") or "").strip()
    situation_note = (data.get("situation_note") or "").strip()
    sid = (data.get("sid") or "").strip()
    request_id = (data.get("request_id") or "").strip()

    if not phone:
        emit_bot_event(
            logger,
            "lead_submitted",
            status="bad_phone",
            details={"ok": False, "error_code": "bad_phone", "delivery": None},
        )
        return {"ok": False, "error_code": "bad_phone", "delivery": None}, 400

    mode = leads_mode(client_id)
    if not leads_enabled(client_id):
        mode = "demo_stub"

    if mode == "demo_stub":
        emit_bot_event(
            logger,
            "lead_submitted",
            status="ok",
            details={
                "ok": True,
                "delivery": "demo_stub",
                "error_code": None,
                "intent": intent,
                "has_name": bool(name),
                "has_situation_note": bool(situation_note),
            },
        )
        return {"ok": True, "error_code": None, "delivery": "demo_stub"}, 200

    lead_cfg = load_lead_config(client_id)
    store_pg = bool(lead_cfg.get("store_in_postgres", True))
    delivery_status = "queued"

    if store_pg:
        try:
            from pg_sink import enqueue_lead

            enqueue_lead(
                {
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "request_id": request_id or None,
                    "sid": sid or None,
                    "client_id": client_id,
                    "name": name or None,
                    "phone": phone,
                    "topic": intent or None,
                    "cta_action": "lead",
                    "turns_to_lead": None,
                    "delivery_status": delivery_status,
                }
            )
        except Exception:
            delivery_status = "pg_enqueue_failed"

    emit_bot_event(
        logger,
        "lead_submitted",
        status="ok",
        details={
            "ok": True,
            "delivery": mode,
            "delivery_status": delivery_status,
            "error_code": None,
            "intent": intent,
            "has_name": bool(name),
            "has_situation_note": bool(situation_note),
        },
    )
    return {"ok": True, "error_code": None, "delivery": mode}, 200
