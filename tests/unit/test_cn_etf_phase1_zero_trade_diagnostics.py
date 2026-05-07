from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

import backend.research.cn_etf_phase1_zero_trade_diagnostics as diagnostics_module
from backend.research.cn_etf_phase1_zero_trade_diagnostics import _load_price_frame, write_cn_etf_phase1_zero_trade_diagnostics


def test_write_cn_etf_phase1_zero_trade_diagnostics_materializes_expected_outputs(tmp_path) -> None:
    exp_id = "exp_test_zero_trade"
    root = tmp_path / exp_id
    root.mkdir(parents=True, exist_ok=True)

    trading_days = pd.bdate_range("2025-01-02", periods=260)
    symbols = ["510300.SH", "510500.SH", "510050.SH", "512100.SH", "511010.SH"]
    price_rows = []
    for idx, day in enumerate(trading_days):
        for offset, symbol in enumerate(symbols, start=1):
            price_rows.append(
                {
                    "date": day.strftime("%Y-%m-%d"),
                    "symbol": symbol,
                    "close": 1.0 + float(offset) * 0.1 + 0.01 * idx,
                }
            )

    portfolio_rows = []
    for idx, day in enumerate(trading_days):
        next_day = trading_days[min(idx + 1, len(trading_days) - 1)]
        is_month_end = idx == len(trading_days) - 1 or day.month != next_day.month
        portfolio_rows.append(
            {
                "date": day.strftime("%Y-%m-%d"),
                "nav": 1000000.0,
                "cash": 1000000.0,
                "gross_exposure": 0.0,
                "turnover_pct": 0.0,
                "etf_target_exposure": 0.0,
                "etf_actual_exposure": 0.0,
                "etf_actual_risk_exposure": 0.0,
                "etf_actual_fallback_exposure": 0.0,
                "etf_actual_other_exposure": 0.0,
                "etf_deployability_gap": 0.0,
                "composed_buy_signal_count": 0,
                "composed_sell_signal_count": 0,
                "diagnostics_input_json": json.dumps(
                    {
                        "diagnostics": {
                            "etf_beta_rebalance_day": bool(is_month_end),
                            "etf_beta_deployable_slot_cap": 0,
                            "etf_beta_formal_view": {
                                "eligible_etfs": list(symbols),
                                "selected_etfs": [],
                                "targets": {},
                                "target_exposure": 0.0,
                                "target_exposure_source": "governor_sleeve_budget",
                                "target_selected_count": 0,
                            },
                            "etf_beta_research_view": {
                                "candidate_pool_symbols": list(symbols),
                                "requested_budget": 0.0,
                                "applied_budget": 0.0,
                                "runtime_reason_codes": ["ETF_BETA_SLOT_CAP_ZERO"],
                                "absolute_filter_reject_reason_counts": {},
                                "candidate_pool_reject_reason_counts": {},
                                "selection_chain_reject_reason_counts": {},
                                "cash_weight": 0.0,
                            },
                        }
                    },
                    ensure_ascii=False,
                ),
                "governor_budget_json": json.dumps(
                    {
                        "total_exposure_cap": 0.0,
                        "budget_reason_codes": ["ETF_BETA_SLOT_CAP_ACTIVE", "NO_DEPLOYABLE_SLOTS"],
                        "under_deploy_reason_codes": ["ETF_BETA_SLOT_CAP_ZERO"],
                    },
                    ensure_ascii=False,
                ),
            }
        )

    pd.DataFrame(portfolio_rows).to_csv(root / "portfolio_daily.csv", index=False)
    pd.DataFrame(columns=["date", "symbol", "side", "price", "qty", "reason_code", "entry_date"]).to_csv(
        root / "orders.csv",
        index=False,
    )
    pd.DataFrame(
        {
            "date": [day.strftime("%Y-%m-%d") for day in trading_days],
            "nav": [1000000.0] * len(trading_days),
        }
    ).to_csv(root / "nav.csv", index=False)
    pd.DataFrame(columns=["date", "symbol", "side", "fill_price", "reason_code", "entry_date"]).to_csv(
        root / "portfolio_trades.csv",
        index=False,
    )
    (root / "perf.json").write_text(
        json.dumps({"cagr": 0.0, "max_drawdown": 0.0, "sharpe": 0.0, "trades": 0}, ensure_ascii=False),
        encoding="utf-8",
    )
    (root / "config.json").write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")
    (root / "resolved_config.json").write_text(
        json.dumps(
            {
                "costs": {
                    "commission_rate": 0.0003,
                    "commission_min": 5.0,
                    "stamp_tax_rate": 0.001,
                    "slippage_bps": 2.0,
                },
                "governed_a_share": {
                    "etf_beta": {
                        "enabled": True,
                        "strategy_role": "phase1_allocation_engine",
                        "source_entry_type": "cn_etf_phase1_allocation_entry",
                        "research_rule_family": "phase1_allocation_engine_v1",
                        "governor_boundary_mode": "consume_governor_sleeve_budget",
                        "local_policy_mode": "phase1_bucket_allocation",
                        "allocation_engine_mode": "phase1_three_bucket_v1",
                        "bucket_policy_profile": "phase1_state_template_v1",
                        "absolute_filter_mode": "none",
                        "fallback_mode": "none",
                        "rebalance_frequency": "monthly",
                        "max_selected_symbols": 3,
                        "relative_strength_fast_window": 60,
                        "relative_strength_slow_window": 120,
                        "relative_strength_fast_weight": 0.4,
                        "relative_strength_slow_weight": 0.6,
                        "core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                        "limited_defense_candidates": ["511010.SH"],
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (root / "run_meta.json").write_text(
        json.dumps(
            {
                "data": {"asset_scope": "cn_etf"},
                "counters": {"orders": 0, "closed_trades": 0},
                "stage_pipeline": {"execution_shell": "stage_pipeline_shell_bridge"},
                "etf_beta": {
                    "formal_view": {
                        "target_exposure": 0.0,
                        "target_exposure_source": "governor_sleeve_budget",
                    },
                    "research_view": {
                        "requested_budget": 0.0,
                        "applied_budget": 0.0,
                    },
                    "formal_alignment_status": "formal_mainline",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    outputs = write_cn_etf_phase1_zero_trade_diagnostics(
        exp_id=exp_id,
        results_dir=root,
        price_frame=pd.DataFrame(price_rows),
    )

    assert Path(outputs["ops_dir"]).exists()
    assert pd.read_csv(outputs["rebalance_day_summary"]).shape[0] > 0
    assert pd.read_csv(outputs["ranking_detail"]).shape[0] > 0
    assert pd.read_csv(outputs["layer_compare"])["layer"].tolist() == [
        "buy_and_hold",
        "filter_only",
        "allocation_only",
        "filter_plus_allocation",
        "full_strategy",
    ]
    effective_parameters = json.loads(Path(outputs["effective_parameters"]).read_text(encoding="utf-8"))
    assert any(row["parameter"] == "absolute_filter_mode" and row["effective_value"] == "none" for row in effective_parameters["rows"])
    position_utilization = json.loads(Path(outputs["position_utilization"]).read_text(encoding="utf-8"))
    assert position_utilization["avg_exposure"] == 0.0
    assert position_utilization["empty_day_ratio"] == 1.0
    lineage = json.loads(Path(outputs["lineage_samples"]).read_text(encoding="utf-8"))
    assert lineage["sample_count"] == 5
    rootcause = json.loads(Path(outputs["rootcause_summary"]).read_text(encoding="utf-8"))
    assert "Governor" in rootcause["top_reasons"][0]["reason"]
    assert rootcause["top_reasons"][0]["evidence"]["budget_reason_counts"]["ETF_BETA_SLOT_CAP_ACTIVE"] > 0
    assert "BREADTH_CAP_ACTIVE" not in rootcause["top_reasons"][0]["evidence"]["budget_reason_counts"]


def test_load_price_frame_uses_provider_factory_and_preserves_data_source_overrides(monkeypatch) -> None:
    captured: dict[str, object] = {}

    cfg_obj = SimpleNamespace(
        data_source=SimpleNamespace(
            data_role="default_role",
            stocks_table="default_table",
        )
    )

    def _fake_load_config(_path: str):
        return cfg_obj, {}

    class _FakeProvider:
        def load_ohlcv_daily(self, symbols, start, end, source):
            captured["load_args"] = {
                "symbols": list(symbols),
                "start": start,
                "end": end,
                "source": source,
            }
            return pd.DataFrame(
                [
                    {"date": "2025-01-02", "symbol": "510300.SH", "close": 1.23},
                ]
            )

    def _fake_build_runtime_provider_from_config(cfg, rules_path, *, use_cache=False):
        captured["provider_cfg"] = cfg
        captured["rules_path"] = Path(rules_path)
        captured["use_cache"] = use_cache
        return _FakeProvider()

    monkeypatch.setattr(diagnostics_module, "load_config", _fake_load_config)
    monkeypatch.setattr(diagnostics_module, "build_runtime_provider_from_config", _fake_build_runtime_provider_from_config)

    frame = _load_price_frame(
        symbols=["510300.SH"],
        start_date="2025-01-02",
        end_date="2025-01-31",
        resolved_config={
            "data_source": {
                "data_role": "cn_etf_runtime",
                "stocks_table": "pams_cn_etf_daily",
            }
        },
    )

    assert frame["symbol"].tolist() == ["510300.SH"]
    assert cfg_obj.data_source.data_role == "cn_etf_runtime"
    assert cfg_obj.data_source.stocks_table == "pams_cn_etf_daily"
    assert captured["provider_cfg"] is cfg_obj
    assert captured["rules_path"].name == "instrument_rules_cn.csv"
    assert captured["use_cache"] is False
    assert captured["load_args"] == {
        "symbols": ["sh510300"],
        "start": pd.Timestamp("2025-01-02").date(),
        "end": pd.Timestamp("2025-01-31").date(),
        "source": "stocks",
    }


def test_research_sidecar_no_longer_directly_imports_pg_provider() -> None:
    text = Path("backend/research/cn_etf_phase1_zero_trade_diagnostics.py").read_text(encoding="utf-8")
    assert "from backend.core.data.pg_provider import PostgresDataProvider" not in text
    assert "build_runtime_provider_from_config(" in text
