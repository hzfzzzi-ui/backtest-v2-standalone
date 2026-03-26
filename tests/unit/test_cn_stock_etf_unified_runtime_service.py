from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from backend.core.services.cn_stock_etf_unified_runtime_service import run_cn_stock_etf_unified_runtime


class _Request:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_component_result(root: Path, *, exp_id: str, asset_scope: str, benchmark: str) -> dict:
    exp_dir = root / exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    nav = pd.DataFrame(
        [
            {"date": "2024-01-02", "nav": 1.0},
            {"date": "2024-01-03", "nav": 1.02 if asset_scope == "cn_a_equity" else 1.01},
            {"date": "2024-01-04", "nav": 1.03 if asset_scope == "cn_a_equity" else 1.015},
        ]
    )
    nav.to_csv(exp_dir / "nav.csv", index=False)
    _write_json(
        exp_dir / "perf.json",
        {
            "total_return": float(nav["nav"].iloc[-1] - 1.0),
            "cagr": 0.1 if asset_scope == "cn_a_equity" else 0.03,
            "max_drawdown": -0.05,
            "sharpe": 0.8,
            "trades": 4 if asset_scope == "cn_a_equity" else 2,
            "turnover": 0.12 if asset_scope == "cn_a_equity" else 0.04,
        },
    )
    _write_json(
        exp_dir / "run_meta.json",
        {
            "data": {"asset_scope": asset_scope, "benchmark": benchmark},
            "regime": {
                "latest_state": {
                    "base_state": "BULL",
                    "effective_state": "BULL" if asset_scope == "cn_a_equity" else "LIGHT",
                    "coarse_state": "RISK_ON",
                    "effective_coarse_state": "RISK_ON" if asset_scope == "cn_a_equity" else "NEUTRAL",
                    "reason_codes": ["OK"],
                    "manual_override": {"active": False, "scope": None, "reason": None, "actor": None},
                }
            },
            "governed_snapshot": {
                "budget_owner": "global_portfolio_governor",
                "budget_consumer_sleeve_id": "cn_stock_trend_alpha_core" if asset_scope == "cn_a_equity" else "cn_etf_beta",
                "budget_consumer_system_role": "stock_alpha_sleeve" if asset_scope == "cn_a_equity" else "market_beta_sleeve",
                "total_risk_budget": 0.8 if asset_scope == "cn_a_equity" else 0.2,
                "total_exposure_cap": 0.5 if asset_scope == "cn_a_equity" else 0.2,
                "actual_exposure": 0.45 if asset_scope == "cn_a_equity" else 0.15,
                "actual_risk_exposure": 0.45 if asset_scope == "cn_a_equity" else 0.15,
                "actual_fallback_exposure": 0.0,
                "actual_other_exposure": 0.0,
                "budget_reason_codes": ["OK"],
                "sleeve_budgets": {
                    "cn_stock_trend_alpha_core" if asset_scope == "cn_a_equity" else "cn_etf_beta": {
                        "slot_cap": 4 if asset_scope == "cn_a_equity" else 2,
                        "available_slots": 1,
                        "candidate_count": 3 if asset_scope == "cn_a_equity" else 2,
                        "selected_count": 2 if asset_scope == "cn_a_equity" else 1,
                        "system_role": "stock_alpha_sleeve" if asset_scope == "cn_a_equity" else "market_beta_sleeve",
                    }
                },
            },
            "counters": {
                "orders": 8 if asset_scope == "cn_a_equity" else 3,
                "closed_trades": 4 if asset_scope == "cn_a_equity" else 2,
            },
        },
    )
    pd.DataFrame(
        [
            {
                "date": "2024-01-03",
                "gross_exposure": 0.45 if asset_scope == "cn_a_equity" else 0.15,
                "cash": 0.55 if asset_scope == "cn_a_equity" else 0.85,
                "positions_count": 2 if asset_scope == "cn_a_equity" else 1,
            }
        ]
    ).to_csv(exp_dir / "portfolio_daily.csv", index=False)
    pd.DataFrame(
        [
            {
                "date": "2024-01-03",
                "symbol": "sh600000" if asset_scope == "cn_a_equity" else "sh510300",
                "side": "BUY",
                "qty": 100,
                "price": 10.0,
            }
        ]
    ).to_csv(exp_dir / "portfolio_trades.csv", index=False)
    pd.DataFrame(
        [
            {
                "date": "2024-01-03",
                "symbol": "sh600000" if asset_scope == "cn_a_equity" else "sh510300",
                "side": "BUY",
                "qty": 100,
                "price": 10.0,
                "reason_code": "ENTRY",
            }
        ]
    ).to_csv(exp_dir / "orders.csv", index=False)
    _write_json(exp_dir / "audit.json", {"status": "PASS"})
    return {"exp_id": exp_id, "results_dir": str(exp_dir), "status": "OK"}


def test_run_cn_stock_etf_unified_runtime_writes_combo_artifacts(tmp_path: Path) -> None:
    bt_root = tmp_path
    experiments_root = bt_root / "outputs" / "experiments"
    experiments_root.mkdir(parents=True, exist_ok=True)
    stock_result = _build_component_result(experiments_root, exp_id="exp_stock_component", asset_scope="cn_a_equity", benchmark="000300.SH")
    etf_result = _build_component_result(experiments_root, exp_id="exp_etf_component", asset_scope="cn_etf", benchmark="510300.SH")

    payload_queue = [stock_result, etf_result]

    def _run_request_body(_body, _hook):
        return payload_queue.pop(0)

    semantic_compile = {
        "input_config": {"flow_script": {"script_id": "cn_stock_etf_v1"}},
        "resolved_config": {"config_json": {"governed_a_share": {"enabled": True}}},
        "compiled_plan": {"unified_runtime": {"enabled": True}},
        "unified_runtime": {
            "enabled": True,
            "sleeves": {
                "stock_alpha_core": {"semantic_config": {"asset_scope": "cn_a_equity"}},
                "etf_beta": {"semantic_config": {"asset_scope": "cn_etf"}},
            },
        },
    }

    result = run_cn_stock_etf_unified_runtime(
        bt_root=bt_root,
        body=_Request(preset="single", workbench_mode="desktop", fast_mode=True),
        base_cfg={"asset_scope": "cn_a_equity"},
        semantic_compile=semantic_compile,
        requested_preset="single",
        resolved_config_id="cfg_cn_stock_etf_v1",
        resolved_config_hash="abc123",
        resolved_config_meta={"source_type": "frontend_semantic"},
        conflict_policy="config_json_preferred",
        run_request_body=_run_request_body,
        request_model=_Request,
    )

    results_dir = Path(str(result["results_dir"]))
    assert results_dir.is_dir()
    run_meta = json.loads((results_dir / "run_meta.json").read_text(encoding="utf-8"))
    manifest = json.loads((results_dir / "manifest.json").read_text(encoding="utf-8"))
    perf = json.loads((results_dir / "perf.json").read_text(encoding="utf-8"))
    audit = json.loads((results_dir / "audit.json").read_text(encoding="utf-8"))
    assert run_meta["data"]["asset_role"] == "unified_multi_sleeve_combo"
    assert run_meta["data"]["system_asset_scope"] == "cn_a_multi_sleeve"
    assert run_meta["combo_components"]["stock_component"]["exp_id"] == "exp_stock_component"
    assert run_meta["combo_components"]["etf_component"]["exp_id"] == "exp_etf_component"
    assert run_meta["sleeves"]["stock_alpha_core"]["asset_scope"] == "cn_a_equity"
    assert run_meta["sleeves"]["etf_beta"]["asset_scope"] == "cn_etf"
    assert run_meta["regime"]["latest_state"]["effective_state"] == "LIGHT"
    assert run_meta["governed_snapshot"]["budget_owner"] == "global_portfolio_governor"
    assert set(run_meta["governed_snapshot"]["sleeve_budgets"].keys()) == {"cn_stock_trend_alpha_core", "cn_etf_beta"}
    assert run_meta["attribution"]["summary"]["sleeve_log_count"] == 2
    assert run_meta["counters"]["orders"] == 11
    assert manifest["stage_pipeline"]["execution_shell"] == "unified_combo_phase1"
    assert perf["analysis_mode"] == "cn_stock_etf_unified_runtime_phase1"
    assert audit["gates"]["unified_runtime_completeness"]["status"] == "PASS"
    assert (results_dir / "input_config.json").exists()
    assert (results_dir / "resolved_config.json").exists()
    assert (results_dir / "compiled_plan.json").exists()
    assert (results_dir / "portfolio_daily.csv").exists()
    assert (results_dir / "portfolio_trades.csv").exists()
    assert (results_dir / "orders.csv").exists()
    assert (results_dir / "regime_audit_summary.json").exists()
    assert (results_dir / "attribution_audit.json").exists()
