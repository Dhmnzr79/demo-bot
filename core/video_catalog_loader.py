"""Каталог медиа по video_key клиента — URL и заголовки для виджета / API."""

from __future__ import annotations

import os
import threading
from typing import Any
from urllib.parse import quote

import yaml

from core.client_config_loader import resolve_pack_client_id

_LOCK = threading.Lock()
_CACHE: dict[str, dict[str, dict[str, str]] | None] = {}


def _catalog_path(client_id: str) -> str:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(root, "clients", client_id, "video_catalog.yaml")


def load_video_catalog(client_id: str) -> dict[str, dict[str, str]]:
    """Словарь video_key → {src, title}. src — внешний URL из YAML."""
    cid = resolve_pack_client_id(client_id)
    with _LOCK:
        if cid in _CACHE:
            cached = _CACHE[cid]
            return {k: dict(v) for k, v in (cached or {}).items()}
    path = _catalog_path(cid)
    parsed: dict[str, dict[str, str]] = {}
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            raw: Any = yaml.safe_load(f) or {}
        videos = raw.get("videos") if isinstance(raw, dict) else None
        if isinstance(videos, dict):
            for key_raw, body in videos.items():
                vk = str(key_raw or "").strip()
                if not vk or not isinstance(body, dict):
                    continue
                src = str(body.get("src") or "").strip()
                if not src:
                    continue
                title = str(body.get("title") or "").strip()
                parsed[vk] = {"src": src, "title": title}
    with _LOCK:
        _CACHE[cid] = dict(parsed)
    return dict(parsed)


def media_play_path(client_id: str, video_key: str) -> str:
    """Same-origin URL для video (прокси /api/media, без CORS S3)."""
    cid = resolve_pack_client_id(client_id)
    vk = quote(str(video_key or "").strip(), safe="")
    cqp = quote(cid, safe="")
    return f"/api/media/{vk}?client_id={cqp}"


def get_external_video_src(*, client_id: str, video_key: str) -> str | None:
    vk = str(video_key or "").strip()
    if not vk:
        return None
    meta = load_video_catalog(client_id).get(vk)
    if not meta:
        return None
    src = str(meta.get("src") or "").strip()
    return src or None


def catalog_for_widget(client_id: str) -> dict[str, dict[str, str]]:
    """Каталог с play-URL через прокси приложения."""
    cid = resolve_pack_client_id(client_id)
    out: dict[str, dict[str, str]] = {}
    for vk, meta in load_video_catalog(cid).items():
        out[vk] = {
            "src": media_play_path(cid, vk),
            "title": str(meta.get("title") or ""),
        }
    return out


def resolve_video_payload(
    *, client_id: str, video_key: str | None
) -> dict[str, str] | None:
    """{key, src, title} для UI; src — прокси same-origin."""
    vk = str(video_key or "").strip()
    if not vk:
        return None
    cat = load_video_catalog(client_id)
    meta = cat.get(vk)
    if not meta or not meta.get("src"):
        return None
    cid = resolve_pack_client_id(client_id)
    return {
        "key": vk,
        "src": media_play_path(cid, vk),
        "title": str(meta.get("title") or ""),
    }
