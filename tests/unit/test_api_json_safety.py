from __future__ import annotations

import json
import math
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.backtest_v2.router import router as backtest_v2_router
from backend.api.mobile.router import router as mobile_router
from backend.api.shared import json_utils as api_json_utils
from backend.api.shared.safe_json_response import SafeJSONResponse
from backend.core.shared import json_utils as core_json_utils


def test_api_json_utils_reexport_core_owner() -> None:
    assert api_json_utils.sanitize_json is core_json_utils.sanitize_json
    assert api_json_utils.sanitize_for_json is core_json_utils.sanitize_for_json
    assert api_json_utils.hash_json is core_json_utils.hash_json
    assert api_json_utils.load_json_file is core_json_utils.load_json_file
    assert api_json_utils.coerce_number is core_json_utils.coerce_number


def test_api_json_sanitizer_removes_nonfinite_values() -> None:
    payload = {
        "float_nan": float("nan"),
        "float_inf": float("inf"),
        "float_neg_inf": float("-inf"),
        "decimal_nan": Decimal("NaN"),
        "decimal_inf": Decimal("Infinity"),
        "nested": [1.0, {"bad": float("nan")}],
    }

    sanitized = api_json_utils.sanitize_for_json(payload)

    assert sanitized == {
        "float_nan": None,
        "float_inf": None,
        "float_neg_inf": None,
        "decimal_nan": None,
        "decimal_inf": None,
        "nested": [1.0, {"bad": None}],
    }
    assert math.isnan(payload["float_nan"])
    json.dumps(sanitized, allow_nan=False)


def test_safe_json_response_renders_nonfinite_values_as_null() -> None:
    response = SafeJSONResponse({"bad": float("nan"), "nested": [float("inf")]})

    assert response.body == b'{"bad":null,"nested":[null]}'
    json.loads(response.body)


def test_formal_api_routers_use_safe_json_response() -> None:
    assert backtest_v2_router.default_response_class is SafeJSONResponse
    assert mobile_router.default_response_class is SafeJSONResponse


def test_backtest_v2_router_sanitizes_service_payload(monkeypatch) -> None:
    from backend.api.backtest_v2.routes import market_data

    monkeypatch.setattr(market_data.impl, "get_industries", lambda: {"bad": float("nan")})
    app = FastAPI()
    app.include_router(backtest_v2_router)

    response = TestClient(app).get("/api/backtest_v2/industries")

    assert response.status_code == 200
    assert response.json() == {"bad": None}


def test_mobile_router_sanitizes_service_payload(monkeypatch) -> None:
    from backend.api.mobile.routes import dashboard

    monkeypatch.setattr(dashboard.impl, "get_mobile_dashboard", lambda request: {"bad": float("-inf")})
    app = FastAPI()
    app.include_router(mobile_router)

    response = TestClient(app).get("/api/mobile/dashboard")

    assert response.status_code == 200
    assert response.json() == {"bad": None}
