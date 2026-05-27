"""Catalog service match: typo tolerance via char-trigrams (no per-typo aliases)."""
from __future__ import annotations

from query_selector import match_service_from_catalog, select_price_service_route
from session import set_last_catalog_service


def test_typo_obelivanie_matches_whitening_price():
    m = match_service_from_catalog("сколько стоит обеливание?", client_id="default")
    assert m.get("matched_service_id") == "professional_whitening"
    assert float(m.get("match_score") or 0) >= 0.62
    assert m.get("is_confident") is True


def test_typo_after_implant_session_not_wrong_price():
    sid = "test_typo_whitening_session"
    set_last_catalog_service(sid, "classic")
    pr = select_price_service_route(
        "А сколько стоит обеливания?",
        client_id="default",
        sid=sid,
        intent_override="price_lookup",
    )
    assert pr.get("mode") == "matched"
    assert pr.get("matched_service_id") == "professional_whitening"
    assert pr.get("fallback_reason") != "context_session"
