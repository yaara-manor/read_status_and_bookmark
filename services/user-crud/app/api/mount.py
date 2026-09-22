from collections.abc import Callable, Mapping, Sequence
from typing import Any

from contracts.routes import PUBLIC_ROUTES, ServiceName, Tag
from fastapi import APIRouter, params


def mount_catalog(
    router: APIRouter,
    handlers: Mapping[str, Callable[..., Any]],
    *,
    service: ServiceName,
    tag: Tag,
    extra: Mapping[str, Sequence[params.Depends]] | None = None,
) -> None:
    for route in PUBLIC_ROUTES:
        if route.service != service or route.tag != tag:
            continue
        dependencies: list[params.Depends] = []
        if extra is not None and route.name in extra:
            dependencies = list(extra[route.name])
        router.add_api_route(
            route.path,
            handlers[route.name],
            methods=[route.method],
            response_model=route.response,
            name=route.name,
            tags=[route.tag],
            dependencies=dependencies,
        )
