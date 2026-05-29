from __future__ import annotations

import json
import math
from decimal import Decimal

from backend.api.shared import json_utils as api_json_utils
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
