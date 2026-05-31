from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from core.clinic_hours import is_clinic_open_now
from core.client_config_loader import tone_to_txt_dict
from lead_service import resolve_lead_submit_message


def _dt(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    tz = ZoneInfo("Asia/Kamchatka")
    return datetime(year, month, day, hour, minute, tzinfo=tz).astimezone(timezone.utc)


def test_cesi_open_on_weekday_morning() -> None:
    assert is_clinic_open_now("cesi", now=_dt(2026, 6, 1, 10)) is True


def test_cesi_closed_on_sunday() -> None:
    assert is_clinic_open_now("cesi", now=_dt(2026, 6, 7, 12)) is False


def test_cesi_closed_after_hours() -> None:
    assert is_clinic_open_now("cesi", now=_dt(2026, 6, 2, 21)) is False


def test_nikadent_saturday_afternoon_open() -> None:
    assert is_clinic_open_now("nikadent", now=_dt(2026, 6, 6, 14)) is True


def test_nikadent_saturday_evening_closed() -> None:
    assert is_clinic_open_now("nikadent", now=_dt(2026, 6, 6, 16)) is False


def test_demo_has_no_hours_config() -> None:
    assert is_clinic_open_now("demo") is None


def test_resolve_lead_submit_message_after_hours() -> None:
    txt = tone_to_txt_dict("cesi")
    with patch("lead_service.is_clinic_open_now", return_value=True):
        msg = resolve_lead_submit_message("cesi", txt)
    assert "администратор" in msg.lower()

    with patch("lead_service.is_clinic_open_now", return_value=False):
        msg = resolve_lead_submit_message("cesi", txt)
    assert "не работает" in msg.lower()


def test_resolve_lead_submit_message_demo_ignores_hours() -> None:
    txt = tone_to_txt_dict("demo")
    with patch("lead_service.is_clinic_open_now", return_value=False):
        msg = resolve_lead_submit_message("demo", txt)
    assert "демо-бот" in msg.lower()
