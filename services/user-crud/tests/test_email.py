import pytest

from app.core.config import settings
from app.email import (
    generate_new_account_email,
    generate_password_reset_token,
    generate_reset_password_email,
    render_email_template,
    send_email,
    verify_password_reset_token,
)


def test_render_email_template_fills_reset_password() -> None:
    html = render_email_template(
        template_name="reset_password.html",
        context={
            "project_name": "Ticketmaster",
            "username": "Ada",
            "email": "ada@example.com",
            "valid_hours": 48,
            "link": "http://localhost:5173/reset-password?token=tok",
        },
    )
    assert "Ticketmaster" in html
    assert "Ada" in html
    assert "48" in html
    assert "token=tok" in html


def test_generate_reset_password_email_returns_subject_and_html() -> None:
    email_data = generate_reset_password_email(
        email_to="ada@example.com", email="ada@example.com", token="tok"
    )
    assert settings.PROJECT_NAME in email_data.subject
    assert "ada@example.com" in email_data.subject
    assert (
        f"{settings.FRONTEND_HOST}/reset-password?token=tok" in email_data.html_content
    )


def test_generate_new_account_email_returns_subject_and_html() -> None:
    email_data = generate_new_account_email(
        email_to="ada@example.com", username="Ada", password="secret"
    )
    assert "Ada" in email_data.subject
    assert settings.PROJECT_NAME in email_data.subject
    assert "secret" in email_data.html_content
    assert settings.FRONTEND_HOST in email_data.html_content


def test_generate_and_verify_password_reset_token_round_trip() -> None:
    token = generate_password_reset_token(email="ada@example.com")
    assert verify_password_reset_token(token) == "ada@example.com"


def test_verify_password_reset_token_rejects_garbage() -> None:
    assert verify_password_reset_token("not-a-token") is None


def test_send_email_without_smtp_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SMTP_HOST", None)
    with pytest.raises(
        AssertionError, match="no provided configuration for email variables"
    ):
        send_email(email_to="ada@example.com", subject="Hi", html_content="<p>Hi</p>")


def test_send_email_uses_tls_user_and_password(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict[str, object]] = []

    def _send(
        _self: object,
        to: str | None = None,
        smtp: dict[str, object] | None = None,
        **_kwargs: object,
    ) -> str:
        sent.append({"to": to, "smtp": smtp})
        return "ok"

    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_PORT", 2525)
    monkeypatch.setattr(settings, "SMTP_TLS", True)
    monkeypatch.setattr(settings, "SMTP_SSL", False)
    monkeypatch.setattr(settings, "SMTP_USER", "user")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "secret")
    monkeypatch.setattr(settings, "EMAILS_FROM_EMAIL", "from@example.com")
    monkeypatch.setattr(settings, "EMAILS_FROM_NAME", "Box Office")
    monkeypatch.setattr("emails.message.Message.send", _send)

    send_email(email_to="ada@example.com", subject="Hi", html_content="<p>Hi</p>")

    assert len(sent) == 1
    assert sent[0]["to"] == "ada@example.com"
    smtp = sent[0]["smtp"]
    assert isinstance(smtp, dict)
    assert smtp["host"] == "smtp.example.com"
    assert smtp["port"] == 2525
    assert smtp["tls"] is True
    assert "ssl" not in smtp
    assert smtp["user"] == "user"
    assert smtp["password"] == "secret"


def test_send_email_uses_ssl_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, object]] = []

    def _send(
        _self: object,
        _to: str | None = None,
        smtp: dict[str, object] | None = None,
        **_kwargs: object,
    ) -> str:
        sent.append({"smtp": smtp})
        return "ok"

    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_TLS", False)
    monkeypatch.setattr(settings, "SMTP_SSL", True)
    monkeypatch.setattr(settings, "SMTP_USER", None)
    monkeypatch.setattr(settings, "SMTP_PASSWORD", None)
    monkeypatch.setattr(settings, "EMAILS_FROM_EMAIL", "from@example.com")
    monkeypatch.setattr(settings, "EMAILS_FROM_NAME", "Box Office")
    monkeypatch.setattr("emails.message.Message.send", _send)

    send_email(email_to="ada@example.com", subject="Hi", html_content="<p>Hi</p>")

    smtp = sent[0]["smtp"]
    assert isinstance(smtp, dict)
    assert smtp["ssl"] is True
    assert "tls" not in smtp
    assert "user" not in smtp
    assert "password" not in smtp
