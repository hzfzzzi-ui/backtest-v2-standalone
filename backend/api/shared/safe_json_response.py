from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse

from backend.api.shared.json_utils import sanitize_for_json


class SafeJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return super().render(sanitize_for_json(content))


__all__ = ["SafeJSONResponse"]
