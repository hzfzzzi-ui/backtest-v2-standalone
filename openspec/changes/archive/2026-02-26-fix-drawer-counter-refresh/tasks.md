## 1. 扩展 experiment_runner 返回值

- [x] 1.1 在 `backend/core/tools/experiment_runner.py` 的 `run_experiment()` 返回 dict 中增加以下字段：`avg_positions`、`max_positions`、`trend_slope_block_count`、`mf_rank_applied_rate`、`mf_gate_on_rate`、`candidate_diag_reason_counts`（从 `bt_result.metrics` 透传）

## 2. 在 ensure_standard_artifacts 中构建 counters

- [x] 2.1 在 `backend/api/endpoints/backtest_v2_artifacts.py` 中新增 `_build_counters(result: dict, results_dir: Path) -> dict` 辅助函数，负责：
  - 从 result dict 提取引擎已有字段（`avg_positions`、`max_positions`、`trend_slope_block_count`、`mf_rank_applied_rate`、`mf_gate_on_rate`、`raw_signal`、`blocked`、`orders`、`skipped`、`closed_trades`）
  - 从 `results_dir/portfolio_trades.csv` 的 `reason_code` 列聚合 exit 计数（`atr_stop_exit_count`、`atr_trail_exit_count`、`reversal_exit_count`、`time_exit_count`）
  - 从 `results_dir/portfolio_trades.csv` 的 `triggered_rule` 列推导 `atr_trail_update_count`
  - 从 result dict 的 `candidate_diag_reason_counts` 提取 constraint 计数（`cash_skip_count` ← SKIP_CASH_INSUFFICIENT、`lot_skip_count` ← SKIP_LOT_TOO_SMALL、`cap_hit_single` ← BLOCK_SINGLE_CAP、`cap_hit_industry` ← BLOCK_INDUSTRY_CAP）
  - 计算 `slots_left = max_positions - avg_positions`
  - 所有字段缺失时默认为 0（int 字段）或 0.0（float 字段）

- [x] 2.2 在 `ensure_standard_artifacts()` 的 `run_meta_obj` 中增加 `"counters": _build_counters(result, results_dir)` 字段

## 3. 验证端到端数据流

- [ ] 3.1 启动后端，通过前端触发一次单次运行，确认 `run_meta.json` 包含 `counters` 对象且各字段有实际数值
- [ ] 3.2 确认前端 Drawer 的 Exit Stats 和 Constraint Stats 面板在运行完成后显示实际数值而非 "—"
