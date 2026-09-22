import json
import os
import sys
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from contracts import CALLER_HEADER, INTERNAL_KEY_HEADER, Caller, encode_caller
from fastapi.testclient import TestClient

# Workspace editable installs put backend/ ahead of services/gateway on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["PROJECT_NAME"] = "Ticketmaster"
os.environ["FRONTEND_HOST"] = "http://localhost:5173"
os.environ["USER_CRUD_URL"] = "http://user.test"
os.environ["EVENT_CRUD_URL"] = "http://event.test"
os.environ["INTERNAL_API_KEY"] = "test-internal-key"
os.environ["FASTAPI_ENV"] = "development"

from app.main import app

CALLER = Caller(
    id="11111111-1111-1111-1111-111111111111",
    is_active=True,
    is_superuser=False,
    display_name="Ada",
)
Handler = Callable[[httpx.Request], httpx.Response]


def _client(monkeypatch: pytest.MonkeyPatch, handler: Handler) -> TestClient:
    def http_client() -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr("app.forward.http_client", http_client)
    return TestClient(app)


def test_missing_token_on_me_makes_no_outbound_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200)

    response = _client(monkeypatch, handler).get("/api/v1/users/me")

    assert response.status_code == 403
    assert response.json()["detail"] == "Could not validate credentials"
    assert seen == []


def test_resolve_403_is_returned_and_events_are_not_called(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(403, json={"detail": "Could not validate credentials"})

    response = _client(monkeypatch, handler).post(
        "/api/v1/events",
        json={"name": "Show"},
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Could not validate credentials"
    assert [request.url.path for request in seen] == ["/internal/resolve-token"]


def test_resolve_400_inactive_user_is_returned_and_events_are_not_called(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(400, json={"detail": "Inactive user"})

    response = _client(monkeypatch, handler).post(
        "/api/v1/events",
        json={"name": "Show"},
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Inactive user"
    assert [request.url.path for request in seen] == ["/internal/resolve-token"]


def test_resolve_connection_error_is_service_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    response = _client(monkeypatch, handler).get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Service unavailable"


def test_resolve_timeout_is_gateway_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        raise httpx.ReadTimeout("timed out")

    response = _client(monkeypatch, handler).get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 504
    assert response.json()["detail"] == "Gateway timeout"
    assert seen == ["/internal/resolve-token"]


def test_create_event_forwards_body_and_caller_without_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/internal/resolve-token":
            return httpx.Response(200, json=CALLER.model_dump(mode="json"))
        return httpx.Response(200, json={"ok": True})

    response = _client(monkeypatch, handler).post(
        "/api/v1/events",
        json={"name": "Show"},
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    assert len(seen) == 2
    forwarded = seen[1]
    assert forwarded.url.host == "event.test"
    assert forwarded.url.path == "/events"
    assert json.loads(forwarded.content) == {"name": "Show"}
    assert forwarded.headers[INTERNAL_KEY_HEADER] == "test-internal-key"
    assert forwarded.headers[CALLER_HEADER] == encode_caller(CALLER)
    assert "authorization" not in forwarded.headers


def test_event_service_401_becomes_service_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/internal/resolve-token":
            return httpx.Response(200, json=CALLER.model_dump(mode="json"))
        return httpx.Response(401)

    response = _client(monkeypatch, handler).post(
        "/api/v1/events",
        json={"name": "Show"},
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Service unavailable"


def test_event_service_404_is_forwarded(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/internal/resolve-token":
            return httpx.Response(200, json=CALLER.model_dump(mode="json"))
        return httpx.Response(404, json={"detail": "Event not found"})

    response = _client(monkeypatch, handler).post(
        "/api/v1/events",
        json={"name": "Show"},
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Event not found"


def test_health_is_true_when_both_services_are_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/health"
        return httpx.Response(200, json=True)

    response = _client(monkeypatch, handler).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() is True


def test_health_is_unavailable_when_event_health_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "event.test":
            return httpx.Response(500)
        return httpx.Response(200, json=True)

    response = _client(monkeypatch, handler).get("/api/v1/health")

    assert response.status_code == 503


def test_login_forwards_without_caller(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"access_token": "t", "token_type": "bearer"})

    response = _client(monkeypatch, handler).post(
        "/api/v1/auth/login",
        json={"email": "ada@example.com", "password": "secret"},
    )

    assert response.status_code == 200
    assert len(seen) == 1
    assert seen[0].url.path == "/auth/login"
    assert seen[0].url.host == "user.test"
    assert json.loads(seen[0].content) == {
        "email": "ada@example.com",
        "password": "secret",
    }
    assert seen[0].headers[INTERNAL_KEY_HEADER] == "test-internal-key"
    assert CALLER_HEADER not in seen[0].headers


def test_development_openapi_lists_dev_users_and_hides_resolve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(request.url.path)

    response = _client(monkeypatch, handler).get("/api/v1/openapi.json")

    assert response.status_code == 200
    document = response.text
    assert "/api/v1/dev/users" in document
    assert "/internal/resolve-token" not in document
    schemes = response.json()["components"]["securitySchemes"]
    assert any(
        scheme.get("type") == "http" and scheme.get("scheme") == "bearer"
        for scheme in schemes.values()
    )
