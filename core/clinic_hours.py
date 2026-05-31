"""Clinic working hours from clinic_policies.yaml (per-client timezone)."""
from __future__ import annotations

import os
import threading
from datetime import datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from core.client_config_loader import resolve_pack_client_id

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LOCK = threading.Lock()
_HOURS_CACHE: dict[str, dict[str, Any] | None] = {}

_WEEKDAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _policies_path(client_id: str | None) -> str:
    pack = resolve_pack_client_id(client_id)
    return os.path.join(_REPO_ROOT, "clients", pack, "clinic_policies.yaml")


def _parse_hhmm(raw: str) -> time | None:
    text = (raw or "").strip()
    if not text or ":" not in text:
        return None
    parts = text.split(":", 1)
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return time(hour=hour, minute=minute)


def _parse_day_slot(raw: Any) -> tuple[time, time] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        return None
    start = _parse_hhmm(str(raw.get("start") or raw.get("open") or ""))
    end = _parse_hhmm(str(raw.get("end") or raw.get("close") or ""))
    if start is None or end is None or start >= end:
        return None
    return start, end


def _load_hours_config(client_id: str | None) -> dict[str, Any] | None:
    pack = resolve_pack_client_id(client_id)
    with _LOCK:
        if pack in _HOURS_CACHE:
            return _HOURS_CACHE[pack]

    path = _policies_path(client_id)
    cfg: dict[str, Any] | None = None
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            if isinstance(raw, dict):
                hours_raw = raw.get("hours")
                contact = raw.get("contact") if isinstance(raw.get("contact"), dict) else {}
                tz_name = ""
                weekly_raw: dict[str, Any] = {}
                if isinstance(hours_raw, dict):
                    tz_name = str(hours_raw.get("timezone") or "").strip()
                    weekly_raw = hours_raw.get("weekly") if isinstance(hours_raw.get("weekly"), dict) else {}
                if not tz_name:
                    tz_name = str(contact.get("timezone") or "").strip()

                weekly: dict[str, tuple[time, time] | None] = {}
                for key in _WEEKDAY_KEYS:
                    weekly[key] = _parse_day_slot(weekly_raw.get(key))

                if tz_name and any(weekly.values()):
                    cfg = {"timezone": tz_name, "weekly": weekly}
        except (OSError, yaml.YAMLError):
            cfg = None

    with _LOCK:
        _HOURS_CACHE[pack] = cfg
    return cfg


def is_clinic_open_now(client_id: str | None, *, now: datetime | None = None) -> bool | None:
    """Return True if open, False if closed, None if hours are not configured."""
    cfg = _load_hours_config(client_id)
    if not cfg:
        return None

    try:
        tz = ZoneInfo(str(cfg["timezone"]))
    except Exception:
        return None

    utc_now = now if now is not None else datetime.now(timezone.utc)
    if utc_now.tzinfo is None:
        utc_now = utc_now.replace(tzinfo=timezone.utc)
    local_now = utc_now.astimezone(tz)
    day_key = _WEEKDAY_KEYS[local_now.weekday()]
    slot = cfg["weekly"].get(day_key)
    if slot is None:
        return False

    start, end = slot
    current = local_now.time().replace(second=0, microsecond=0)
    return start <= current < end
