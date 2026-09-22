import json
from typing import Annotated

import httpx
from contracts import CALLER_HEADER, INTERNAL_KEY_HEADER, Caller, encode_caller
from fastapi import Depends, HTTPException, Request
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

_TIMEOUT = 10.0
_bearer = HTTPBearer(auto_error=False)


def http_client() -> httpx.Client:
    return httpx.Client(timeout=_TIMEOUT)


def _send(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: str | None = None,
    content: bytes | None = None,
) -> httpx.Response:
    try:
        with http_client() as client:
            return client.request(
                method,
                url,
                timeout=_TIMEOUT,
                headers=headers,
                params=params,
                content=content,
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Gateway timeout") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="Service unavailable") from exc


def _detail(response: httpx.Response) -> object:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return response.text
    if isinstance(payload, dict) and "detail" in payload:
        return payload["detail"]
    return response.text


def resolve_caller(token: str) -> Caller:
    response = _send(
        "POST",
        f"{settings.USER_CRUD_URL.rstrip('/')}/internal/resolve-token",
        headers={
            INTERNAL_KEY_HEADER: settings.INTERNAL_API_KEY,
            "Content-Type": "application/json",
        },
        content=json.dumps({"token": token}).encode(),
    )
    if response.status_code == 200:
        return Caller.model_validate(response.json())
    if response.status_code == 401:
        raise HTTPException(status_code=503, detail="Service unavailable")
    raise HTTPException(status_code=response.status_code, detail=_detail(response))


def require_caller(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Caller:
    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not credentials.credentials
    ):
        raise HTTPException(status_code=403, detail="Could not validate credentials")
    return resolve_caller(credentials.credentials)


CallerDep = Annotated[Caller, Depends(require_caller)]


def forward(
    method: str,
    path: str,
    query: str,
    body: bytes,
    *,
    service_url: str,
    caller: Caller | None,
) -> Response:
    headers = {INTERNAL_KEY_HEADER: settings.INTERNAL_API_KEY}
    if caller is not None:
        headers[CALLER_HEADER] = encode_caller(caller)
    if body:
        headers["Content-Type"] = "application/json"
    response = _send(
        method,
        f"{service_url.rstrip('/')}{path}",
        params=query or None,
        content=body or None,
        headers=headers,
    )
    if response.status_code == 401:
        raise HTTPException(status_code=503, detail="Service unavailable")
    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type=response.headers.get("content-type"),
    )


def get_status(url: str) -> int:
    return _send("GET", url).status_code


async def proxy(request: Request, service_url: str, caller: Caller | None) -> Response:
    path = request.url.path.removeprefix("/api/v1") or "/"
    return forward(
        request.method,
        path,
        request.url.query,
        await request.body(),
        service_url=service_url,
        caller=caller,
    )
