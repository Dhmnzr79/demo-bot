"""Tests for Host → client_id resolution."""
from __future__ import annotations

import core.client_host as client_host
from core.client_host import client_id_from_host, resolve_request_client_id


def test_client_id_from_bot_subdomain():
    assert client_id_from_host("cesi.bot.artgents.ru") == "cesi"
    assert client_id_from_host("nikadent.bot.artgents.ru:443") == "nikadent"
    assert client_id_from_host("demo.bot.artgents.ru") == "demo"


def test_client_id_from_marketing_domain_not_api():
    assert client_id_from_host("artgents.ru") is None
    assert client_id_from_host("demo.artgents.ru") is None


def test_client_id_from_localhost_none():
    assert client_id_from_host("localhost:9001") is None


def test_resolve_request_local_uses_body():
    assert resolve_request_client_id("cesi", host="localhost:9001") == "cesi"


def test_resolve_request_prod_host_only(monkeypatch):
    monkeypatch.setattr(client_host, "APP_ENV", "prod")
    assert resolve_request_client_id(None, host="cesi.bot.artgents.ru") == "cesi"
    assert resolve_request_client_id("", host="cesi.bot.artgents.ru") == "cesi"


def test_resolve_request_prod_host_and_matching_body(monkeypatch):
    monkeypatch.setattr(client_host, "APP_ENV", "prod")
    assert resolve_request_client_id("cesi", host="cesi.bot.artgents.ru") == "cesi"


def test_resolve_request_prod_host_body_mismatch(monkeypatch):
    monkeypatch.setattr(client_host, "APP_ENV", "prod")
    assert resolve_request_client_id("nikadent", host="cesi.bot.artgents.ru") is None


def test_resolve_request_prod_demo_host(monkeypatch):
    monkeypatch.setattr(client_host, "APP_ENV", "prod")
    assert resolve_request_client_id(None, host="demo.bot.artgents.ru") == "demo"
    monkeypatch.setattr(client_host, "APP_ENV", "prod")
    assert resolve_request_client_id("cesi", host="localhost:9001") is None
    assert resolve_request_client_id(None, host="localhost:9001") is None
