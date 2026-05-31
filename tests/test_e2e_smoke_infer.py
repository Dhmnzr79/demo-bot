from __future__ import annotations

from evals.v5.run_e2e_smoke import _infer_route_from_response


def test_infer_route_service_route_wins() -> None:
    resp = {
        "answer": "ok",
        "meta": {"service_route": "continuation_clarify"},
        "quick_replies": [{"label": "x", "ref": "y"}],
    }
    assert _infer_route_from_response(resp) == "continuation_clarify"


def test_infer_route_bare_affirmative() -> None:
    resp = {"answer": "ok", "meta": {"service_route": "bare_affirmative"}}
    assert _infer_route_from_response(resp) == "bare_affirmative"


def test_infer_route_lead_flow_from_meta_flag() -> None:
    resp = {"answer": "ok", "meta": {"lead_flow": True, "service_route": "lead_flow"}}
    assert _infer_route_from_response(resp) == "lead_flow"
