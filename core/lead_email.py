"""SMTP delivery for clinic leads (M3). Secrets in .env; recipients in lead_config.yaml."""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Any

import yaml

from core.client_runtime import client_pack_dir
from logging_setup import get_logger

logger = get_logger("bot")


def _env_bool(name: str, default: bool = True) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def smtp_configured() -> bool:
    return bool((os.getenv("SMTP_HOST") or "").strip() and (os.getenv("SMTP_FROM") or "").strip())


def normalize_recipients(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        addr = item.strip()
        if not addr or "@" not in addr:
            continue
        if "REPLACE_" in addr.upper():
            continue
        out.append(addr)
    return out


def _clinic_name(client_id: str | None) -> str:
    path = os.path.join(client_pack_dir(client_id), "brand.yaml")
    if not os.path.isfile(path):
        return (client_id or "clinic").strip()
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        name = raw.get("clinic_name") if isinstance(raw, dict) else None
        if isinstance(name, str) and name.strip():
            return name.strip()
    except (OSError, yaml.YAMLError):
        pass
    return (client_id or "clinic").strip()


def _subject(lead_cfg: dict[str, Any], client_id: str | None) -> str:
    tpl = str(lead_cfg.get("subject_template") or "").strip()
    if tpl:
        return tpl
    return f"Заявка с бота {_clinic_name(client_id)}"


def _build_body(
    *,
    client_id: str | None,
    name: str,
    phone: str,
    intent: str,
    situation_note: str,
    sid: str,
    request_id: str,
    captured_at: str,
) -> str:
    clinic = _clinic_name(client_id)
    lines = [
        f"Новая заявка с бота {clinic}",
        "",
        f"Имя: {name or '—'}",
        f"Телефон: {phone}",
        f"Тема: {intent or '—'}",
        f"Ситуация: {situation_note or '—'}",
        "",
        f"client_id: {client_id or '—'}",
        f"sid: {sid or '—'}",
        f"request_id: {request_id or '—'}",
        f"Время (UTC): {captured_at}",
    ]
    return "\n".join(lines)


def _smtp_use_ssl(port: int) -> bool:
    if _env_bool("SMTP_USE_SSL", default=False):
        return True
    raw = (os.getenv("SMTP_USE_SSL") or "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    return port == 465


def _connect_smtp(host: str, port: int):
    if _smtp_use_ssl(port):
        return smtplib.SMTP_SSL(host, port, timeout=30)
    smtp = smtplib.SMTP(host, port, timeout=30)
    if _env_bool("SMTP_USE_TLS", default=True):
        smtp.starttls()
    return smtp


def send_lead_email(
    *,
    client_id: str | None,
    lead_cfg: dict[str, Any],
    name: str,
    phone: str,
    intent: str,
    situation_note: str,
    sid: str,
    request_id: str,
    captured_at: str,
) -> tuple[bool, str]:
    """Send lead email. Returns (ok, delivery_status for PG/admin)."""
    recipients = normalize_recipients(lead_cfg.get("recipients"))
    if not recipients:
        logger.warning("lead_email_no_recipients client_id=%s", client_id)
        return False, "email_no_recipients"

    if not smtp_configured():
        logger.warning("lead_email_smtp_not_configured client_id=%s", client_id)
        return False, "email_smtp_not_configured"

    host = (os.getenv("SMTP_HOST") or "").strip()
    port = int((os.getenv("SMTP_PORT") or "587").strip() or "587")
    from_addr = (os.getenv("SMTP_FROM") or "").strip()
    user = (os.getenv("SMTP_USER") or "").strip() or from_addr
    password = (os.getenv("SMTP_PASSWORD") or "").strip()

    msg = EmailMessage()
    msg["Subject"] = _subject(lead_cfg, client_id)
    msg["From"] = from_addr
    msg["To"] = ", ".join(recipients)
    msg.set_content(
        _build_body(
            client_id=client_id,
            name=name,
            phone=phone,
            intent=intent,
            situation_note=situation_note,
            sid=sid,
            request_id=request_id,
            captured_at=captured_at,
        )
    )

    try:
        with _connect_smtp(host, port) as smtp:
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)
        logger.info(
            "lead_email_sent client_id=%s recipients=%s",
            client_id,
            len(recipients),
        )
        return True, "email"
    except Exception as e:
        logger.warning(
            "lead_email_failed client_id=%s err=%s",
            client_id,
            str(e)[:200],
        )
        return False, "email_failed"
