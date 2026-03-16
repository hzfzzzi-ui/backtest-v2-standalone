from __future__ import annotations

from typing import Any

from backend.api.shared.json_utils import sanitize_json
from backend.core.config.asset_profiles import build_asset_context, canonical_asset_scope


def apply_asset_runtime_cfg(
    cfg: dict[str, Any],
    body: Any,
    wb_cfg: dict[str, Any] | None,
) -> dict[str, Any]:
    body_scope = getattr(body, "asset_scope", None)
    existing_scope = cfg.get("asset_scope")
    context = build_asset_context(
        body_scope,
        config_json=wb_cfg if isinstance(wb_cfg, dict) else None,
        metadata_scope=existing_scope,
    )
    cfg["asset_scope"] = canonical_asset_scope(context.get("asset_scope"))
    cfg["asset_context"] = sanitize_json(context)
    return sanitize_json(context)


__all__ = ["apply_asset_runtime_cfg"]
