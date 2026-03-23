from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


class UnsupportedAssetScopeError(ValueError):
    pass


_DEFAULT_ASSET_SCOPE = "cn_a_equity"
_ASSET_SCOPE_ALIASES = {
    "cn_a_equity": "cn_a_equity",
    "cn_a": "cn_a_equity",
    "cn_a_stock": "cn_a_equity",
    "a_share": "cn_a_equity",
    "a_shares": "cn_a_equity",
    "cn_etf": "cn_etf",
    "a_share_etf": "cn_etf",
    "a_shares_etf": "cn_etf",
    "cn_fund_etf": "cn_etf",
    "us_equity": "us_equity",
    "us_stock": "us_equity",
    "us_stocks": "us_equity",
    "us_equities": "us_equity",
}


@dataclass(frozen=True, slots=True)
class MarketProfile:
    profile_id: str
    market_key: str
    venue: str
    timezone: str
    currency: str
    benchmark_symbol: str
    industry_model: str
    symbol_namespace: str


@dataclass(frozen=True, slots=True)
class ExecutionProfile:
    profile_id: str
    signal_clock: str
    execution_clock: str
    settlement_cycle: str
    lot_size: int
    price_adjust_default: str
    long_only: bool = True


@dataclass(frozen=True, slots=True)
class AssetProfile:
    asset_scope: str
    asset_profile_id: str
    asset_family: str
    asset_class: str
    market_profile: MarketProfile
    execution_profile: ExecutionProfile
    tags: tuple[str, ...] = field(default_factory=tuple)

    def to_asset_context(self) -> dict[str, Any]:
        return {
            "asset_scope": self.asset_scope,
            "asset_profile_id": self.asset_profile_id,
            "asset_family": self.asset_family,
            "asset_class": self.asset_class,
            "market_profile_id": self.market_profile.profile_id,
            "execution_profile_id": self.execution_profile.profile_id,
            "market_profile": asdict(self.market_profile),
            "execution_profile": asdict(self.execution_profile),
            "tags": list(self.tags),
        }


_ASSET_PROFILES: dict[str, AssetProfile] = {
    "cn_a_equity": AssetProfile(
        asset_scope="cn_a_equity",
        asset_profile_id="cn_a_equity_mainline",
        asset_family="equity",
        asset_class="equity",
        market_profile=MarketProfile(
            profile_id="cn_a_mainland_equity_market",
            market_key="CN_A",
            venue="SSE_SZSE",
            timezone="Asia/Shanghai",
            currency="CNY",
            benchmark_symbol="000300.SH",
            industry_model="sw_l1",
            symbol_namespace="cn_equity",
        ),
        execution_profile=ExecutionProfile(
            profile_id="cn_a_tplus1_next_open",
            signal_clock="POST_CLOSE",
            execution_clock="NEXT_OPEN",
            settlement_cycle="T+1",
            lot_size=100,
            price_adjust_default="hfq",
            long_only=True,
        ),
        tags=("current_mainline", "a_share"),
    ),
    "cn_etf": AssetProfile(
        asset_scope="cn_etf",
        asset_profile_id="cn_etf_first_wave_research",
        asset_family="fund",
        asset_class="etf",
        market_profile=MarketProfile(
            profile_id="cn_etf_mainland_fund_market",
            market_key="CN_A",
            venue="SSE_SZSE",
            timezone="Asia/Shanghai",
            currency="CNY",
            benchmark_symbol="",
            industry_model="none",
            symbol_namespace="cn_etf",
        ),
        execution_profile=ExecutionProfile(
            profile_id="cn_etf_tplus1_next_open",
            signal_clock="POST_CLOSE",
            execution_clock="NEXT_OPEN",
            settlement_cycle="T+1",
            lot_size=100,
            price_adjust_default="none",
            long_only=True,
        ),
        tags=("research_entry", "cn_etf", "first_wave"),
    ),
    "us_equity": AssetProfile(
        asset_scope="us_equity",
        asset_profile_id="us_equity_prepare_mainline",
        asset_family="equity",
        asset_class="equity",
        market_profile=MarketProfile(
            profile_id="us_equity_primary_market",
            market_key="US_EQUITY",
            venue="NASDAQ_NYSE",
            timezone="America/New_York",
            currency="USD",
            benchmark_symbol="SPY",
            industry_model="gics_l1",
            symbol_namespace="us_equity",
        ),
        execution_profile=ExecutionProfile(
            profile_id="us_equity_tplus1_next_open",
            signal_clock="POST_CLOSE",
            execution_clock="NEXT_OPEN",
            settlement_cycle="T+1",
            lot_size=1,
            price_adjust_default="none",
            long_only=True,
        ),
        tags=("prepared_only", "unsupported_runtime", "us_equity"),
    ),
}


def supported_asset_scopes() -> tuple[str, ...]:
    return tuple(sorted(_ASSET_PROFILES))


def canonical_asset_scope(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return _DEFAULT_ASSET_SCOPE
    canonical = _ASSET_SCOPE_ALIASES.get(text)
    if canonical:
        return canonical
    raise UnsupportedAssetScopeError(f"unsupported asset_scope: {value}")


def extract_asset_scope(config_json: dict[str, Any] | None) -> str | None:
    if not isinstance(config_json, dict):
        return None
    for candidate in (
        config_json.get("asset_scope"),
        (config_json.get("asset_context") or {}).get("asset_scope") if isinstance(config_json.get("asset_context"), dict) else None,
    ):
        text = str(candidate or "").strip()
        if text:
            return canonical_asset_scope(text)
    return None


def resolve_asset_profile(
    asset_scope: Any | None = None,
    *,
    config_json: dict[str, Any] | None = None,
    baseline_id: str | None = None,
    metadata_scope: Any | None = None,
) -> AssetProfile:
    scope_candidates = [
        asset_scope,
        extract_asset_scope(config_json),
        metadata_scope,
    ]
    if baseline_id and str(baseline_id).strip():
        scope_candidates.append(_DEFAULT_ASSET_SCOPE)

    canonical_scope = _DEFAULT_ASSET_SCOPE
    for candidate in scope_candidates:
        text = str(candidate or "").strip()
        if not text:
            continue
        canonical_scope = canonical_asset_scope(text)
        break

    profile = _ASSET_PROFILES.get(canonical_scope)
    if profile is None:
        raise UnsupportedAssetScopeError(f"unsupported asset_scope: {canonical_scope}")
    return profile


def build_asset_context(
    asset_scope: Any | None = None,
    *,
    profile: AssetProfile | None = None,
    config_json: dict[str, Any] | None = None,
    baseline_id: str | None = None,
    metadata_scope: Any | None = None,
) -> dict[str, Any]:
    resolved = profile or resolve_asset_profile(
        asset_scope,
        config_json=config_json,
        baseline_id=baseline_id,
        metadata_scope=metadata_scope,
    )
    return resolved.to_asset_context()


__all__ = [
    "AssetProfile",
    "ExecutionProfile",
    "MarketProfile",
    "UnsupportedAssetScopeError",
    "build_asset_context",
    "canonical_asset_scope",
    "extract_asset_scope",
    "resolve_asset_profile",
    "supported_asset_scopes",
]
