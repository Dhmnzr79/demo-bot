"""Tests for admin visit segmentation."""
from __future__ import annotations

from datetime import datetime, timezone

from admin_dashboard.dialog_segments import build_visit_item, group_turns_into_visits


def _turn(ts: str, user: str, route: str = "chunk") -> tuple:
    dt = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
    return (dt, "ok", 1, user, "bot reply", route, None, 100.0)


def test_split_visits_after_lead():
    t1 = _turn("2026-05-31T13:16:52+00:00", "имплант")
    t2 = _turn("2026-05-31T13:18:53+00:00", "+7phone")
    t3 = _turn("2026-05-31T13:19:44+00:00", "all-on-4")
    t4 = _turn("2026-05-31T13:23:23+00:00", "+7phone2")
    lead1 = datetime.fromisoformat("2026-05-31T13:18:53+00:00").replace(tzinfo=timezone.utc)
    lead2 = datetime.fromisoformat("2026-05-31T13:23:23+00:00").replace(tzinfo=timezone.utc)
    visits = group_turns_into_visits([t1, t2, t3, t4], [lead1, lead2], gap_minutes=30)
    assert len(visits) == 2
    assert len(visits[0]) == 2
    assert len(visits[1]) == 2


def test_build_visit_item_status():
    turns = [_turn("2026-05-31T13:16:52+00:00", "вопрос")]
    lead = datetime.fromisoformat("2026-05-31T13:18:53+00:00").replace(tzinfo=timezone.utc)
    item = build_visit_item("sid1", "cesi", 0, 1, turns, [lead])
    assert item["visit_index"] == 0
    assert item["turns"] == 1
    assert item["first_user_text"] == "вопрос"
