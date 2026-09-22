from contracts import PUBLIC_ROUTES


def test_public_routes_have_unique_operation_ids_and_methods() -> None:
    operation_ids = [f"{route.tag}-{route.name}" for route in PUBLIC_ROUTES]
    assert len(operation_ids) == len(set(operation_ids))
    methods = [(route.method, route.path) for route in PUBLIC_ROUTES]
    assert len(methods) == len(set(methods))
