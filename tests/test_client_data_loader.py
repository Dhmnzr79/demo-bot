"""Tests for M2 client runtime and data loader."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from core.client_data_loader import get_client_index, invalidate_client_index
from core.client_runtime import (
    client_md_dir,
    corpus_paths,
    effective_corpus_client_id,
    sqlite_path_for_client,
)


def test_effective_corpus_client_id_maps_default_to_demo_pack():
    assert effective_corpus_client_id(None) == "demo"
    assert effective_corpus_client_id("default") == "demo"
    assert effective_corpus_client_id("cesi") == "cesi"


def test_paths_per_client_pack():
    assert client_md_dir("cesi").endswith("clients\\cesi\\md") or client_md_dir("cesi").endswith(
        "clients/cesi/md"
    )
    assert sqlite_path_for_client("nikadent").endswith("data/nikadent/bot.db") or sqlite_path_for_client(
        "nikadent"
    ).endswith("data\\nikadent\\bot.db")


def test_client_index_loads_isolated_corpus(tmp_path, monkeypatch):
    import core.client_runtime as cr
    import core.client_data_loader as cdl

    data_cesi = tmp_path / "data" / "cesi"
    data_cesi.mkdir(parents=True)
    row = {
        "doc": "clinic__info__contacts",
        "file": "clinic__info__contacts.md",
        "client_id": "cesi",
        "h2": "Адрес",
        "h3": "Коротко",
        "h3_id": "korotko",
        "text": "Елизово тест",
        "aliases": ["контакты"],
    }
    (data_cesi / "corpus.jsonl").write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    np.save(data_cesi / "embeddings.npy", np.zeros((1, 8), dtype=np.float32))
    (data_cesi / "alias_rows.jsonl").write_text("", encoding="utf-8")
    np.save(data_cesi / "alias_embeddings.npy", np.zeros((0, 8), dtype=np.float32))

    monkeypatch.setattr(cr, "_REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(cdl, "corpus_paths", cr.corpus_paths)
    invalidate_client_index()

    idx = get_client_index("cesi")
    assert len(idx.corpus) == 1
    assert idx.corpus[0]["client_id"] == "cesi"
    assert "Елизово" in idx.corpus[0]["text"]

    paths = corpus_paths("demo")
    assert paths["corpus"].replace("\\", "/").endswith("data/demo/corpus.jsonl")
