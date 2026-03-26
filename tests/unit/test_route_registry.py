from __future__ import annotations

from types import SimpleNamespace

from backend.core.engine_vector.route_registry import (
    build_signal_provider_for_strategy,
    resolve_route_binding,
    resolve_runtime_route_id,
)
from backend.core.strategies.breakout_trend import BreakoutTrendStrategy
from backend.core.strategies.composite_strategy import CompositeStrategy
from backend.core.strategies.multi_alpha_strategy import MultiAlphaStrategy
from backend.core.strategies.regime_router import RegimeRouter


def test_route_registry_resolves_provider_bindings() -> None:
    breakout = BreakoutTrendStrategy.__new__(BreakoutTrendStrategy)
    multi_alpha = MultiAlphaStrategy.__new__(MultiAlphaStrategy)
    composite = CompositeStrategy.__new__(CompositeStrategy)
    regime_router = RegimeRouter.__new__(RegimeRouter)

    breakout_binding = resolve_route_binding(breakout)
    multi_alpha_binding = resolve_route_binding(multi_alpha)
    composite_binding = resolve_route_binding(composite)
    regime_binding = resolve_route_binding(regime_router)
    fallback_binding = resolve_route_binding(SimpleNamespace())

    assert breakout_binding.route_id == "provider_breakout_runtime"
    assert multi_alpha_binding.route_id == "multi_alpha_inline_runtime"
    assert composite_binding.route_id == "generic_inline_runtime"
    assert regime_binding.route_id == "regime_router_inline_runtime"
    assert fallback_binding.route_id == "strict_inline_runtime"
    assert breakout_binding.extension_path == "provider"


def test_route_registry_builds_provider_instances_and_runtime_route_ids() -> None:
    breakout = BreakoutTrendStrategy.__new__(BreakoutTrendStrategy)

    route_id, provider = build_signal_provider_for_strategy(breakout)

    assert route_id == "provider_breakout_runtime"
    assert provider.__class__.__name__ == "BreakoutTrendProvider"
    assert resolve_runtime_route_id(SimpleNamespace()) == "strict_inline_runtime"


def test_route_registry_uses_cn_etf_beta_provider_for_cn_etf_breakout_strategy() -> None:
    breakout = BreakoutTrendStrategy.__new__(BreakoutTrendStrategy)

    binding = resolve_route_binding(breakout, asset_context={"asset_scope": "cn_etf"})
    route_id, provider = build_signal_provider_for_strategy(breakout, asset_context={"asset_scope": "cn_etf"})

    assert binding.route_id == "provider_breakout_runtime"
    assert binding.provider_cls.__name__ == "CNETFBetaSignalProvider"
    assert route_id == "provider_breakout_runtime"
    assert provider.__class__.__name__ == "CNETFBetaSignalProvider"
