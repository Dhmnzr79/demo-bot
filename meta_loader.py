# meta_loader.py — doc frontmatter from client packs (M2)
from __future__ import annotations

import os
import re
from os.path import abspath

import yaml

from core.client_config_loader import resolve_pack_client_id
from core.client_runtime import client_md_dir

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.S)


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def _parse_front_matter(text: str) -> dict:
    m = _FM_RE.match(text)
    if not m:
        return {}
    try:
        fm = yaml.safe_load(m.group(1)) or {}
        if not isinstance(fm, dict):
            return {}
        return fm
    except Exception:
        return {}


def _meta_item(pack_id: str, name: str, fm: dict) -> dict:
    return {
        "client_id": pack_id,
        "doc_id": fm.get("doc_id"),
        "doc_type": fm.get("doc_type"),
        "subtype": fm.get("subtype"),
        "topic": fm.get("topic"),
        "subtopic": fm.get("subtopic"),
        "cta_text": fm.get("cta_text"),
        "cta_action": fm.get("cta_action"),
        "cta_from_turn": _safe_int(fm.get("cta_from_turn", 0), 0),
        "verbatim_ids": fm.get("verbatim_ids") or [],
        "aliases": fm.get("aliases") or [],
        "suggest_h3": fm.get("suggest_h3") or [],
        "suggest_refs": fm.get("suggest_refs") or [],
        "situation_allowed": bool(fm.get("situation_allowed", False)),
        "video_key": fm.get("video_key"),
        "empathy_enabled": bool(fm.get("empathy_enabled", False)),
        "empathy_tag": fm.get("empathy_tag"),
    }


def load_doc_meta_for_pack(pack_id: str) -> tuple[dict, dict]:
    """Return (meta_by_name, paths_by_name) for one client pack."""
    meta: dict = {}
    paths: dict = {}
    md_root = client_md_dir(pack_id)
    if not os.path.isdir(md_root):
        return meta, paths
    for root, _, files in os.walk(md_root):
        for name in files:
            if not name.endswith(".md"):
                continue
            path = os.path.join(root, name)
            fm = _parse_front_matter(_read_file(path))
            item = _meta_item(pack_id, name, fm)
            meta[name] = item
            paths[name] = abspath(path)
    return meta, paths


_DOC_META_BY_PACK: dict[str, dict] = {}
_DOC_PATHS_BY_PACK: dict[str, dict] = {}


def _ensure_pack_loaded(client_id: str | None) -> str:
    pack = resolve_pack_client_id(client_id)
    if pack not in _DOC_META_BY_PACK:
        meta, paths = load_doc_meta_for_pack(pack)
        _DOC_META_BY_PACK[pack] = meta
        _DOC_PATHS_BY_PACK[pack] = paths
    return pack


def get_doc_path(doc_name: str, client_id: str | None = None):
    pack = _ensure_pack_loaded(client_id)
    return _DOC_PATHS_BY_PACK.get(pack, {}).get(doc_name)


def get_doc_meta(doc_name: str, client_id: str | None = None) -> dict:
    pack = _ensure_pack_loaded(client_id)
    meta_map = _DOC_META_BY_PACK.get(pack, {})
    item = meta_map.get(doc_name)
    if item:
        return item
    wanted_doc_id = os.path.splitext(doc_name)[0]
    for cand in meta_map.values():
        if isinstance(cand, dict) and cand.get("doc_id") == wanted_doc_id:
            return cand
    return {}
