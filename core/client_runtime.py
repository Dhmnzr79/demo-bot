"""Client pack paths and runtime resource resolution (M2 isolation)."""
from __future__ import annotations

import os

from core.client_config_loader import resolve_pack_client_id

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def client_pack_dir(client_id: str | None) -> str:
    """Absolute path to ``clients/{pack_id}/``."""
    pack = resolve_pack_client_id(client_id)
    return os.path.join(_REPO_ROOT, "clients", pack)


def client_md_dir(client_id: str | None) -> str:
    """Absolute path to ``clients/{pack_id}/md/``."""
    return os.path.join(client_pack_dir(client_id), "md")


def per_client_data_dir(client_id: str | None) -> str:
    """Absolute path to ``data/{pack_id}/``."""
    pack = resolve_pack_client_id(client_id)
    return os.path.join(_REPO_ROOT, "data", pack)


def sqlite_path_for_client(client_id: str | None) -> str:
    """Per-client SQLite sessions DB (``data/{pack_id}/bot.db``)."""
    return os.path.join(per_client_data_dir(client_id), "bot.db")


def corpus_paths(client_id: str | None) -> dict[str, str]:
    """Artifact paths for retrieval index of one client pack."""
    data_dir = per_client_data_dir(client_id)
    return {
        "corpus": os.path.join(data_dir, "corpus.jsonl"),
        "embeddings": os.path.join(data_dir, "embeddings.npy"),
        "alias_rows": os.path.join(data_dir, "alias_rows.jsonl"),
        "alias_embeddings": os.path.join(data_dir, "alias_embeddings.npy"),
    }


def effective_corpus_client_id(client_id: str | None) -> str:
    """Logical pack id used for retrieval / corpus row tag (no cross-client fallback)."""
    return resolve_pack_client_id(client_id)


def list_buildable_client_ids() -> list[str]:
    """Client pack directories with ``md/`` (excludes ``_template``)."""
    clients_root = os.path.join(_REPO_ROOT, "clients")
    if not os.path.isdir(clients_root):
        return []
    out: list[str] = []
    for name in sorted(os.listdir(clients_root)):
        if name.startswith("_"):
            continue
        md_dir = os.path.join(clients_root, name, "md")
        if os.path.isdir(md_dir):
            out.append(name)
    return out

