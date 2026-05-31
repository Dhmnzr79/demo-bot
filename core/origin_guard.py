"""Origin / Referer guard for widget embed endpoints (M1/M2)."""
from __future__ import annotations

import os
from urllib.parse import urlparse

from flask import request

from core.client_config_loader import load_widget_config

APP_ENV = (os.getenv("APP_ENV") or "local").strip().lower()

_LOCAL_DEV_HOSTS = frozenset({"localhost", "127.0.0.1"})


def _normalize_origin(value: str) -> str:
    v = (value or "").strip().rstrip("/")
    if not v:
        return ""
    if "://" not in v:
        v = f"https://{v}"
    parsed = urlparse(v)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def _origin_from_referer(referer: str) -> str:
    ref = (referer or "").strip()
    if not ref:
        return ""
    parsed = urlparse(ref)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def _hostname(origin: str) -> str:
    return (urlparse(origin).hostname or "").lower()


def _local_dev_hosts_from_allowed(allowed: set[str]) -> set[str]:
    hosts: set[str] = set()
    for item in allowed:
        h = _hostname(item)
        if h in _LOCAL_DEV_HOSTS:
            hosts.add(h)
    return hosts


def _origin_is_allowed(candidate: str, allowed: set[str], local_dev_hosts: set[str]) -> bool:
    if not candidate:
        return False
    if candidate in allowed:
        return True
    host = _hostname(candidate)
    if host in local_dev_hosts and host in _LOCAL_DEV_HOSTS:
        return True
    return False


def validate_widget_origin(client_id: str | None) -> str | None:
    """Return error code if Origin/Referer is present but not allowed; else None."""
    cfg = load_widget_config(client_id)
    allowed_raw = cfg.get("allowed_origins") or []
    allowed = {_normalize_origin(str(x)) for x in allowed_raw if str(x).strip()}
    allowed.discard("")
    if not allowed:
        return None

    local_dev_hosts = _local_dev_hosts_from_allowed(allowed)
    origin = _normalize_origin(request.headers.get("Origin") or "")
    referer_origin = _origin_from_referer(request.headers.get("Referer") or "")
    if APP_ENV == "prod" and allowed and not origin and not referer_origin:
        return "origin_required"
    if not origin and not referer_origin:
        return None

    if _origin_is_allowed(origin, allowed, local_dev_hosts):
        return None
    if _origin_is_allowed(referer_origin, allowed, local_dev_hosts):
        return None
    return "origin_not_allowed"
