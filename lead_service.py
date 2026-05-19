"""Приём лида: в демо-репозитории заявка не отправляется и не сохраняется."""
from __future__ import annotations

from typing import Any

from logging_setup import emit_bot_event, get_logger
from session import normalize_phone

logger = get_logger("bot")


def handle_lead(data: dict[str, Any]) -> tuple[dict[str, Any], int]:
    name = (data.get("name") or "").strip()
    phone = normalize_phone((data.get("phone") or "").strip() or "")
    intent = (data.get("intent") or "").strip()
    situation_note = (data.get("situation_note") or "").strip()

    if not phone:
        emit_bot_event(
            logger,
            "lead_submitted",
            status="bad_phone",
            details={"ok": False, "error_code": "bad_phone", "delivery": None},
        )
        return {"ok": False, "error_code": "bad_phone", "delivery": None}, 400

    # Демо-бот: без SMTP, без файлов в leads/, без записи в Postgres.
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
