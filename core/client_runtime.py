"""Client pack paths and transitional corpus client_id (M1 → M2).

Until ``data/{client_id}/corpus.jsonl`` exists, the shared index rows stay tagged
``default`` — API ``client_id`` (demo / cesi / nikadent) still applies for catalog,
policies, and logging; retrieval filter uses :func:`effective_corpus_client_id`.
"""
from __future__ import annotations

import os

_LEGACY_CORPUS_CLIENT_ID = "default"
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def client_pack_dir(client_id: str) -> str:
    """Absolute path to ``clients/{client_id}/``."""
    cid = (client_id or "").strip() or _LEGACY_CORPUS_CLIENT_ID
    return os.path.join(_REPO_ROOT, "clients", cid)


def per_client_data_dir(client_id: str) -> str:
    """Absolute path to ``data/{client_id}/`` (M2 target)."""
    cid = (client_id or "").strip() or _LEGACY_CORPUS_CLIENT_ID
    return os.path.join(_REPO_ROOT, "data", cid)


def effective_corpus_client_id(client_id: str | None) -> str | None:
    """Corpus row tag for retrieval filter (not the API/logical client_id)."""
    raw = (client_id or "").strip()
    if not raw:
        return _LEGACY_CORPUS_CLIENT_ID
    if raw == _LEGACY_CORPUS_CLIENT_ID:
        return raw
    per_client_corpus = os.path.join(per_client_data_dir(raw), "corpus.jsonl")
    if os.path.isfile(per_client_corpus):
        return raw
    return _LEGACY_CORPUS_CLIENT_ID
