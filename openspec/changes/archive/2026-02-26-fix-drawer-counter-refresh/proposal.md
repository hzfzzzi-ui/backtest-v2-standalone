## Why

全量回测运行后，Drawer 面板中 Exit Stats（`wbExitStats`）和 Constraint Stats（`wbConstraintStats`）全部显示 "—"，未刷新。原因是数据管道中有三处断裂：引擎产出的计数器字段在 `experiment_runner.py` 返回时被丢弃；`ensure_standard_artifacts()` 写出的 `run_meta.json` 缺少 `counters` 字段；已有的完整提取函数 `_extract_trigger_counters()` 是死代码，从未被调用。

## What Changes

- **修复 `experiment_runner.py` 返回值**：将 `bt_result.metrics` 中的 `avg_positions`、`trend_slope_block_count`、`mf_rank_applied_rate`、`mf_gate_on_rate` 等计数器字段透传到返回的 result dict 中
- **修复 `ensure_standard_artifacts()` 的 `run_meta.json` 写入**：从 result dict 和 results_dir 下已有的产物文件（`portfolio_trades.csv`、`portfolio_candidates.csv`）中提取完整 counters，写入 `run_meta.json` 的 `counters` 字段
- **激活或内联 `_extract_trigger_counters()` 的逻辑**：将 exit reason 计数（`reversal_exit_count`、`time_exit_count`、`atr_stop_exit_count`、`atr_trail_exit_count`）从 trades CSV 中派生；将 constraint 计数（`cap_hit_single`、`cap_hit_industry`、`cash_skip_count`、`lot_skip_count`）从 candidates CSV 中派生
- **清理死代码**：确认 `_extract_trigger_counters()` 逻辑被正确复用或内联后，移除未使用的残留

## Capabilities

### New Capabilities

（无新增能力）

### Modified Capabilities

- `exit-stats-display`：当前 spec 要求"回测完成后显示 exit trigger counts"，但实际数据管道未满足此要求；需确保 `run_meta.json` 的 `counters` 包含全部 5 个 exit 计数器
- `constraint-stats-display`：当前 spec 要求"回测完成后显示 constraint trigger counts"，但实际数据管道未满足此要求；需确保 `run_meta.json` 的 `counters` 包含全部 6 个 constraint 计数器
- `single-run-pipeline`：当前 spec 要求 result.artifacts 包含 `run_meta` 键，但未规定 `run_meta.json` 内部须含 `counters`；需补充此要求

## Impact

- **后端文件**：
  - `backend/core/tools/experiment_runner.py` — 扩展返回 dict
  - `backend/api/endpoints/backtest_v2_artifacts.py` `ensure_standard_artifacts()` — 补充 counters 提取与写入
  - `backend/api/endpoints/backtest_v2.py` `_extract_trigger_counters()` — 复用或清理
- **前端**：无需改动（现有 `renderExplainPanel()` 的 fallback 逻辑 `art?.run_meta?.counters || row` 已经正确，只要 counters 存在即可）
- **产物协议**：`run_meta.json` 新增 `counters` 字段（向后兼容，前端已有 fallback）
