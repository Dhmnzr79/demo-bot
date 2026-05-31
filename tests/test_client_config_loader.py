"""Tests for client pack config loader."""
from __future__ import annotations

from core.client_config_loader import (
    admin_client_options,
    admin_enabled,
    consult_nudge_enabled,
    list_admin_client_ids,
    load_ui_bundle,
    postgres_events_enabled,
    resolve_pack_client_id,
    tone_to_txt_dict,
)


def test_resolve_pack_default_to_demo():
    assert resolve_pack_client_id("default") == "demo"
    assert resolve_pack_client_id("cesi") == "cesi"


def test_tone_demo_has_submit_ok():
    txt = tone_to_txt_dict("demo")
    assert "демо-бот" in txt["lead_submit_ok"].lower()


def test_tone_cesi_no_demo_disclaimer():
    txt = tone_to_txt_dict("cesi")
    assert "демо-бот" not in txt["lead_submit_ok"].lower()


def test_ui_cesi_low_score_differs_from_demo():
    demo = load_ui_bundle("demo")
    cesi = load_ui_bundle("cesi")
    assert demo.low_score.answer != cesi.low_score.answer
    assert "бесплатная" in demo.low_score.answer.lower()
    assert "бесплатная" not in cesi.low_score.answer.lower()
    assert "бесплатн" not in cesi.anti_spam_soft_redirect.lower()


def test_postgres_events_demo_off():
    assert postgres_events_enabled("demo") is False
    assert postgres_events_enabled("cesi") is True


def test_consult_nudge_enabled_default():
    assert consult_nudge_enabled("demo") is True


def test_admin_enabled_prod_clients():
    assert admin_enabled("demo") is False
    assert admin_enabled("cesi") is True
    assert admin_enabled("nikadent") is True


def test_list_admin_client_ids():
    ids = list_admin_client_ids()
    assert "cesi" in ids
    assert "nikadent" in ids
    assert "demo" not in ids


def test_admin_client_options_labels():
    opts = admin_client_options()
    by_id = {item["client_id"]: item["label"] for item in opts}
    assert by_id.get("cesi") == "ЦЭСИ"
    assert by_id.get("nikadent") == "НикаДент"
