"""Per-client retrieval index cache (corpus, embeddings, alias artifacts)."""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from core.client_runtime import corpus_paths, effective_corpus_client_id
from logging_setup import get_logger, log_json

logger = get_logger("bot")


@dataclass
class ClientIndex:
    client_id: str
    corpus: list[dict[str, Any]] = field(default_factory=list)
    embeddings: np.ndarray | None = None
    emb_load_error: str | None = None
    alias_emb_matrix: np.ndarray | None = None
    alias_row_corpus_idx: np.ndarray | None = None
    alias_row_client: list[str] = field(default_factory=list)
    alias_artifacts_error: str = ""
    corpus_path: str = ""
    embeddings_path: str = ""


_CACHE_LOCK = threading.RLock()
_CACHE: dict[str, ClientIndex] = {}


def _mtime_bundle(paths: dict[str, str]) -> tuple[float, ...]:
    mt: list[float] = []
    for key in ("corpus", "embeddings", "alias_rows", "alias_embeddings"):
        p = paths.get(key) or ""
        try:
            mt.append(os.path.getmtime(p) if p and os.path.isfile(p) else 0.0)
        except OSError:
            mt.append(0.0)
    return tuple(mt)


def _load_corpus_file(path: str, client_id: str) -> list[dict[str, Any]]:
    if not os.path.isfile(path):
        log_json(
            logger,
            "client_corpus_missing",
            client_id=client_id,
            corpus_path=path,
        )
        return []
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _load_embeddings(path: str, client_id: str) -> tuple[np.ndarray | None, str | None]:
    if not os.path.isfile(path):
        return None, "missing_embeddings"
    try:
        emb = np.load(path)
        return emb, None
    except Exception as e:
        log_json(
            logger,
            "client_embeddings_load_failed",
            client_id=client_id,
            emb_path=path,
            err=str(e)[:200],
        )
        return None, str(e)


def _embedding_dim_for_empty_alias_matrix(embeddings: np.ndarray | None) -> int:
    if embeddings is not None and embeddings.ndim == 2 and embeddings.shape[1] > 0:
        return int(embeddings.shape[1])
    return 1536


def _load_alias_artifacts(
    paths: dict[str, str],
    *,
    client_id: str,
    embeddings: np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray, list[str], str]:
    dim0 = _embedding_dim_for_empty_alias_matrix(embeddings)
    alias_emb_path = paths["alias_embeddings"]
    alias_rows_path = paths["alias_rows"]
    empty_emb = np.zeros((0, dim0), dtype=np.float32)
    empty_idx = np.array([], dtype=np.int32)
    try:
        if not os.path.isfile(alias_emb_path) or not os.path.isfile(alias_rows_path):
            return empty_emb, empty_idx, [], "missing_alias_files"
        emb = np.load(alias_emb_path)
        clients: list[str] = []
        idxs: list[int] = []
        with open(alias_rows_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                idxs.append(int(obj["corpus_idx"]))
                clients.append(str(obj.get("client_id") or ""))
        if emb.shape[0] != len(idxs):
            return (
                np.zeros((0, int(emb.shape[1]) if emb.ndim == 2 else dim0), dtype=np.float32),
                empty_idx,
                [],
                "alias_rows_emb_shape_mismatch",
            )
        if emb.shape[0] == 0:
            return emb.astype(np.float32), empty_idx, [], ""
        return emb.astype(np.float32), np.array(idxs, dtype=np.int32), clients, ""
    except Exception as e:
        return empty_emb, empty_idx, [], str(e)


def _load_client_index_unlocked(client_id: str) -> ClientIndex:
    paths = corpus_paths(client_id)
    corpus = _load_corpus_file(paths["corpus"], client_id)
    embeddings, emb_err = _load_embeddings(paths["embeddings"], client_id)
    alias_emb, alias_idx, alias_clients, alias_err = _load_alias_artifacts(
        paths, client_id=client_id, embeddings=embeddings
    )
    return ClientIndex(
        client_id=client_id,
        corpus=corpus,
        embeddings=embeddings,
        emb_load_error=emb_err,
        alias_emb_matrix=alias_emb,
        alias_row_corpus_idx=alias_idx,
        alias_row_client=alias_clients,
        alias_artifacts_error=alias_err,
        corpus_path=paths["corpus"],
        embeddings_path=paths["embeddings"],
    )


def get_client_index(client_id: str | None) -> ClientIndex:
    """Cached retrieval bundle for one client pack."""
    cid = effective_corpus_client_id(client_id)
    paths = corpus_paths(cid)
    mt = _mtime_bundle(paths)
    with _CACHE_LOCK:
        hit = _CACHE.get(cid)
        if hit is not None and getattr(hit, "_mtime", None) == mt:
            return hit
        idx = _load_client_index_unlocked(cid)
        idx._mtime = mt  # type: ignore[attr-defined]
        _CACHE[cid] = idx
        return idx


def invalidate_client_index(client_id: str | None = None) -> None:
    with _CACHE_LOCK:
        if client_id is None:
            _CACHE.clear()
            return
        cid = effective_corpus_client_id(client_id)
        _CACHE.pop(cid, None)
