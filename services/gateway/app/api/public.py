import inspect
import re
from typing import assert_never
from uuid import UUID

from contracts import PUBLIC_ROUTES, Caller, PublicRoute
from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.core.config import settings
from app.forward import CallerDep, proxy

# ponytail: every public path param is a UUID. Upgrade: a type on PublicRoute.
_PATH_PARAM = re.compile(r"\{([^}/]+)}")


def _service_url(route: PublicRoute) -> str:
    match route.service:
        case "user":
            return settings.USER_CRUD_URL
        case "event":
            return settings.EVENT_CRUD_URL
        case _ as unreachable:
            assert_never(unreachable)


def _proxy_endpoint(route: PublicRoute):
    async def endpoint(request: Request, **kwargs: object) -> Response:
        caller = kwargs.get("caller")
        return await proxy(
            request,
            _service_url(route),
            caller if isinstance(caller, Caller) else None,
        )

    parameters = [
        inspect.Parameter(
            "request",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=Request,
        )
    ]
    for name in _PATH_PARAM.findall(route.path):
        parameters.append(
            inspect.Parameter(
                name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=UUID,
            )
        )
    if route.body is not None:
        parameters.append(
            inspect.Parameter(
                "body",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=route.body,
            )
        )
    if route.caller:
        parameters.append(
            inspect.Parameter(
                "caller",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=CallerDep,
            )
        )
    if route.paged:
        parameters.append(
            inspect.Parameter(
                "skip",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=0,
                annotation=int,
            )
        )
        parameters.append(
            inspect.Parameter(
                "limit",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=100,
                annotation=int,
            )
        )
    endpoint.__signature__ = inspect.Signature(parameters)  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
    endpoint.__name__ = route.name
    return endpoint


def public_router(*, include_dev: bool) -> APIRouter:
    router = APIRouter()
    for route in PUBLIC_ROUTES:
        if route.dev_only and not include_dev:
            continue
        router.add_api_route(
            route.path,
            _proxy_endpoint(route),
            methods=[route.method],
            response_model=route.response,
            name=route.name,
            tags=[route.tag],
        )
    return router
