from __future__ import annotations

from backend.core.tools.experiment_runner import _apply_overrides


def test_apply_overrides_preserves_cn_etf_backend_runtime_benchmark() -> None:
    raw_cfg = {
        "universe": {"benchmark": "000300.SH"},
        "execution": {},
        "sizing": {},
        "data_source": {},
    }
    runtime_cfg = {
        "db": {"host": "pams-postgres"},
        "schema_mapping": {"stocks": "pams_cn_etf_daily"},
        "asset_context": {"asset_scope": "cn_etf"},
        "universe": {
            "benchmark": "510300.SH",
            "symbols": ["cn_etf_research_style_smart_beta_pool_v2"],
        },
        "execution": {},
        "sizing": {},
        "data_source": {},
    }

    resolved = _apply_overrides(
        raw_cfg,
        {
            "asset_scope": "cn_etf",
            "workbench_config": runtime_cfg,
        },
    )

    assert resolved["universe"]["benchmark"] == "510300.SH"
