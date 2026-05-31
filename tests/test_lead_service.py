from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.lead_email import normalize_recipients, send_lead_email, smtp_configured
from lead_service import handle_lead


def test_normalize_recipients_skips_placeholders() -> None:
    assert normalize_recipients(["admin@clinic.ru", "REPLACE_WITH_EMAIL"]) == ["admin@clinic.ru"]
    assert normalize_recipients([]) == []


def test_handle_lead_demo_stub() -> None:
    payload, status = handle_lead(
        {
            "client_id": "demo",
            "name": "Мария",
            "phone": "+79001234567",
            "intent": "lead",
        }
    )
    assert status == 200
    assert payload["delivery"] == "demo_stub"


@patch.dict(
    "os.environ",
    {
        "SMTP_HOST": "mail.artgents.ru",
        "SMTP_PORT": "465",
        "SMTP_USE_SSL": "1",
        "SMTP_FROM": "bot@artgents.ru",
        "SMTP_USER": "bot@artgents.ru",
        "SMTP_PASSWORD": "secret",
    },
    clear=False,
)
@patch("core.lead_email._connect_smtp")
def test_send_lead_email_ssl_success(mock_connect: MagicMock) -> None:
    mock_smtp = MagicMock()
    mock_connect.return_value.__enter__.return_value = mock_smtp

    ok, status = send_lead_email(
        client_id="cesi",
        lead_cfg={
            "recipients": ["admin@cesi.ru"],
            "subject_template": "Заявка с бота ЦЭСИ",
        },
        name="Иван",
        phone="+79001234567",
        intent="lead",
        situation_note="",
        sid="s1",
        request_id="r1",
        captured_at="2026-01-01T00:00:00+00:00",
    )

    assert ok is True
    assert status == "email"
    mock_connect.assert_called_once_with("mail.artgents.ru", 465)
    mock_smtp.login.assert_called_once_with("bot@artgents.ru", "secret")
    mock_smtp.send_message.assert_called_once()


@patch.dict(
    "os.environ",
    {
        "SMTP_HOST": "smtp.example.com",
        "SMTP_FROM": "bot@example.com",
        "SMTP_USER": "bot@example.com",
        "SMTP_PASSWORD": "secret",
    },
    clear=False,
)
@patch("core.lead_email._connect_smtp")
def test_send_lead_email_starttls_success(mock_connect: MagicMock) -> None:
    mock_smtp = MagicMock()
    mock_connect.return_value.__enter__.return_value = mock_smtp

    ok, status = send_lead_email(
        client_id="cesi",
        lead_cfg={
            "recipients": ["admin@cesi.ru"],
            "subject_template": "Заявка с бота ЦЭСИ",
        },
        name="Иван",
        phone="+79001234567",
        intent="lead",
        situation_note="",
        sid="s1",
        request_id="r1",
        captured_at="2026-01-01T00:00:00+00:00",
    )

    assert ok is True
    assert status == "email"
    mock_connect.assert_called_once()
    mock_smtp.login.assert_called_once()
    mock_smtp.send_message.assert_called_once()


def test_send_lead_email_no_recipients() -> None:
    ok, status = send_lead_email(
        client_id="cesi",
        lead_cfg={"recipients": ["REPLACE_WITH_CESI_ADMIN_EMAIL"]},
        name="",
        phone="+79001234567",
        intent="lead",
        situation_note="",
        sid="",
        request_id="",
        captured_at="2026-01-01T00:00:00+00:00",
    )
    assert ok is False
    assert status == "email_no_recipients"


@patch("pg_sink.enqueue_lead")
@patch("lead_service.send_lead_email", return_value=(True, "email"))
def test_handle_lead_cesi_email_and_pg(mock_send, mock_pg_enqueue) -> None:
    payload, status = handle_lead(
        {
            "client_id": "cesi",
            "name": "Анна",
            "phone": "+79007654321",
            "intent": "lead",
            "sid": "sid-1",
            "request_id": "req-1",
        }
    )
    assert status == 200
    assert payload["delivery"] == "email"
    assert payload["delivery_status"] == "email"
    mock_send.assert_called_once()
    mock_pg_enqueue.assert_called_once()
    row = mock_pg_enqueue.call_args[0][0]
    assert row["delivery_status"] == "email"
    assert row["phone"] == "+79007654321"


def test_smtp_configured_requires_host_and_from() -> None:
    with patch.dict("os.environ", {"SMTP_HOST": "", "SMTP_FROM": ""}, clear=False):
        assert smtp_configured() is False
