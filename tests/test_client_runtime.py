"""Tests for transitional corpus client_id resolution."""
from __future__ import annotations

from core.client_config_loader import resolve_pack_client_id
from core.client_runtime import effective_corpus_client_id


def test_effective_corpus_client_id_maps_to_pack():
    assert effective_corpus_client_id(None) == "demo"
    assert effective_corpus_client_id("") == "demo"
    assert effective_corpus_client_id("default") == "demo"
    assert effective_corpus_client_id("demo") == "demo"
    assert effective_corpus_client_id("cesi") == "cesi"
    assert effective_corpus_client_id("nikadent") == "nikadent"


def test_resolve_pack_client_id_alias():
    assert resolve_pack_client_id("default") == "demo"
