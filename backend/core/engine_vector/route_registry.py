from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Type

from backend.core.config.asset_profiles import canonical_asset_scope
from backend.core.engine_vector.breakout_signal_provider import BreakoutTrendProvider
from backend.core.engine_vector.generic_signal_provider import GenericSignalProvider
from backend.core.engine_vector.multi_alpha_signal_provider import MultiAlphaSignalProvider
from backend.core.engine_vector.regime_router_signal_provider import RegimeRouterSignalProvider
from backend.core.engine_vector.signal_provider import SignalProvider
from backend.core.engine_vector.sma_signal_provider import SMASignalProvider
from backend.core.strategies.breakout_trend import BreakoutTrendStrategy
from backend.core.strategies.composite_strategy import CompositeStrategy
from backend.core.strategies.multi_alpha_strategy import MultiAlphaStrategy
from backend.core.strategies.regime_router import RegimeRouter


@dataclass(frozen=True, slots=True)
class RouteBinding:
    route_id: str
    provider_cls: Type[SignalProvider]
    extension_path: str

    def build_provider(self) -> SignalProvider:
        return self.provider_cls()


def resolve_route_binding(strategy: Any, asset_context: dict[str, Any] | None = None) -> RouteBinding:
    if isinstance(asset_context, dict) and asset_context:
        canonical_asset_scope(asset_context.get("asset_scope"))
    if isinstance(strategy, BreakoutTrendStrategy):
        return RouteBinding(
            route_id="provider_breakout_runtime",
            provider_cls=BreakoutTrendProvider,
            extension_path="provider",
        )
    if isinstance(strategy, MultiAlphaStrategy):
        return RouteBinding(
            route_id="multi_alpha_inline_runtime",
            provider_cls=MultiAlphaSignalProvider,
            extension_path="provider",
        )
    if isinstance(strategy, CompositeStrategy):
        return RouteBinding(
            route_id="generic_inline_runtime",
            provider_cls=GenericSignalProvider,
            extension_path="provider",
        )
    if isinstance(strategy, RegimeRouter):
        return RouteBinding(
            route_id="regime_router_inline_runtime",
            provider_cls=RegimeRouterSignalProvider,
            extension_path="provider",
        )
    return RouteBinding(
        route_id="strict_inline_runtime",
        provider_cls=SMASignalProvider,
        extension_path="provider",
    )


def resolve_runtime_route_id(strategy: Any) -> str:
    return resolve_route_binding(strategy).route_id


def build_signal_provider_for_strategy(strategy: Any, asset_context: dict[str, Any] | None = None) -> tuple[str, SignalProvider]:
    binding = resolve_route_binding(strategy, asset_context=asset_context)
    return binding.route_id, binding.build_provider()
