"""Map request Host to client_id (prod subdomain routing)."""
from __future__ import annotations

import os

from config import ALLOWED_CLIENTS, resolve_client_id

APP_ENV = (os.getenv("APP_ENV") or "local").strip().lower()


def client_id_from_host(host: str | None) -> str | None:
    """Extract client_id from ``{id}.bot.<domain>`` hostnames."""
    if not host:
        return None
    h = host.strip().lower().split(":")[0]
    marker = ".bot."
    if marker not in h:
        return None
    sub = h.split(marker, 1)[0].strip()
    if sub and sub in ALLOWED_CLIENTS:
        return sub
    return None


def resolve_request_client_id(raw: str | None, *, host: str | None) -> str | None:
    """Resolve client_id from body/query with Host binding in prod."""
    if APP_ENV != "prod":
        return resolve_client_id(raw)

    host_cid = client_id_from_host(host)
    if not host_cid:
        return None

    explicit = (raw or "").strip()
    if explicit:
        explicit_cid = resolve_client_id(explicit)
        if explicit_cid is None or explicit_cid != host_cid:
            return None
    return host_cid
