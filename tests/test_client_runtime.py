"""Tests for transitional corpus client_id resolution."""
from __future__ import annotations

import os

from core.client_runtime import effective_corpus_client_id


def test_effective_corpus_client_id_legacy_default():
    assert effective_corpus_client_id(None) == "default"
    assert effective_corpus_client_id("") == "default"
    assert effective_corpus_client_id("default") == "default"


def test_effective_corpus_client_id_shared_index_until_per_client_data():
    assert effective_corpus_client_id("demo") == "default"
    assert effective_corpus_client_id("cesi") == "default"
    assert effective_corpus_client_id("nikadent") == "default"


def test_effective_corpus_client_id_uses_per_client_index_when_present(tmp_path, monkeypatch):
    import core.client_runtime as cr

    data_cesi = tmp_path / "data" / "cesi"
    data_cesi.mkdir(parents=True)
    (data_cesi / "corpus.jsonl").write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(cr, "_REPO_ROOT", str(tmp_path))
    assert effective_corpus_client_id("cesi") == "cesi"
    assert effective_corpus_client_id("demo") == "default"
