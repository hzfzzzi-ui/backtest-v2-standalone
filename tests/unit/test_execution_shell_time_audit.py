from __future__ import annotations

import json
from pathlib import Path

from backend.core.audit.research_audit import evaluate_timing_alignment
from backend.core.tools.locked_candidate_presets import _build_static_t1_guard


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_locked_candidate_static_t1_guard_confirms_price_signal_contract() -> None:
    guard = _build_static_t1_guard()

    assert guard["audit_mode"] == "static_code_contract"
    assert guard["t1_execution_confirmed"] is True
    assert (
        "portfolio_simulator_strict.py" in guard["provider_signal_ref"]
        or "strict_runtime_impl.py" in guard["provider_signal_ref"]
    )
    assert "breakout_signal_provider.py" in guard["provider_regime_ref"]


def test_evaluate_timing_alignment_marks_fundamental_inputs_as_not_pit_safe(tmp_path: Path) -> None:
    results_dir = tmp_path / "exp_timing_financial"
    results_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        results_dir / "compiled_plan.json",
        {
            "runtime_config": {
                "execution": {"t_plus_one": True},
                "strategy": {"name": "breakout_trend", "params": {"enable_sector_gate": False}},
                "financial": {"quality_factor": "roe_ttm"},
            }
        },
    )
    _write_json(
        results_dir / "input_config.json",
        {
            "strategy_pack": "BREAKOUT_TREND",
            "fundamental": {"quality_factor": "roe_ttm"},
            "position_risk": {"cost_model": {"matching": "next_open"}},
        },
    )

    gate = evaluate_timing_alignment(
        stage_summary={
            "execution_shell": "stage_pipeline_shell_bridge",
            "daily_loop_mode": "single_day_loop",
            "route_id": "provider_breakout_runtime",
        },
        stage_pipeline={
            "execution_shell": "stage_pipeline_shell_bridge",
            "daily_loop_mode": "single_day_loop",
            "route_id": "provider_breakout_runtime",
        },
        results_dir=results_dir,
    )

    assert gate["status"] == "UNKNOWN"
    assert gate["metrics"]["contract_proved"] is True
    assert gate["metrics"]["pit_safe"] is False
    assert gate["metrics"]["uses_fundamental_data"] is True
    assert gate["evidence"]["signal_observation_bar"] == "t_close"
    assert gate["evidence"]["execution_bar"] == "t_plus_1_open"


def test_static_time_audits_cover_rank_market_state_and_industry_history_paths() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    generic_text = (repo_root / "backend/core/engine_vector/generic_signal_provider.py").read_text(encoding="utf-8")
    route_runtime_text = (repo_root / "backend/core/stage_pipeline/adapters/route_runtime.py").read_text(encoding="utf-8")
    breakout_text = (repo_root / "backend/core/engine_vector/breakout_signal_provider.py").read_text(encoding="utf-8")

    assert 'prev = fdf.groupby("symbol")["close"].shift(p)' in generic_text
    assert 'groupby("date")["ret"].rank(method="average", pct=True)' in generic_text
    assert ".shift(-" not in generic_text

    assert "bench_close.rolling(200, min_periods=200).mean()" in route_runtime_text
    assert "ma_fast = bench_close.rolling(fast, min_periods=fast).mean()" in route_runtime_text
    assert ".shift(-" not in route_runtime_text

    assert "_build_industry_assignment_matrices" in breakout_text
    assert "industry_history=industry_history if isinstance(industry_history, pd.DataFrame) else None" in breakout_text
    assert ".bfill(" not in breakout_text
