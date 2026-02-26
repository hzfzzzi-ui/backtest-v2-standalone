## Context

当前单次运行数据管道：

```
Engine (portfolio_builder)
  │ metrics: avg_positions, mf_gate_on_rate, trend_slope_block_count...
  │          但 NOT: reversal_exit_count, time_exit_count, cap_hit_*, cash_skip_count...
  ▼
experiment_runner.py  ← 只透传 7 个 perf 字段 + 5 个 funnel 字段
  │                      ❌ 丢弃 avg_positions 等
  ▼
stabilize_experiment_result() → ensure_standard_artifacts()
  │ 写 run_meta.json = { exp_id, status, data, code }
  │ ❌ 无 counters 字段
  ▼
Frontend loadActiveArtifacts()
  │ art.run_meta.counters → undefined
  │ fallback → row (raw result) → 也缺少大部分 counter 字段
  ▼
Drawer 面板全显示 "—"
```

另存在 `_extract_trigger_counters()` 函数（backtest_v2.py:701），可从 group_dir 文件中派生所有 11 个 counter 字段，但为死代码。

## Goals / Non-Goals

**Goals**
- 修复 Drawer Exit Stats 和 Constraint Stats 在单次运行后的数据刷新
- 确保 `run_meta.json` 包含完整 `counters` 对象，供前端直接读取
- 复用现有引擎 metrics + 产物文件派生，不改动引擎层

**Non-Goals**
- 不修改前端渲染逻辑（已有正确的 fallback 机制）
- 不修改引擎层（`portfolio_builder.py`、`portfolio_simulator_strict.py`）
- 不改动 `build_run_meta()` (backtest_v2.py:505)，该函数服务于 group inspect 路径，与本次修复无关

## Decisions

### D1: 在 experiment_runner.py 中透传更多 metrics 字段

**选择**：扩展 `run_experiment()` 返回 dict，增加引擎已有的字段。

**理由**：引擎 `bt_result.metrics` 已经包含 `avg_positions`、`trend_slope_block_count`、`mf_rank_applied_rate`、`mf_gate_on_rate` 等字段，只是 `experiment_runner.py:167` 的 return dict 未包含。直接透传即可，无额外计算。

**备选（否决）**：在 `ensure_standard_artifacts()` 中重新从 CSV 文件提取——增加不必要的 I/O 和重复计算。

### D2: 在 ensure_standard_artifacts() 中从产物文件派生 exit/constraint 计数器

**选择**：在 `ensure_standard_artifacts()` 中增加一个 `_build_counters()` 辅助函数，负责：
1. 从 result dict 提取引擎直接输出的字段（`avg_positions`、`trend_slope_block_count` 等）
2. 从 `portfolio_trades.csv`（已由引擎写出到 results_dir）派生 exit reason 计数
3. 从 `portfolio_candidates.csv`（已由引擎写出到 results_dir）派生 constraint 计数
4. 计算派生字段（`slots_left = max_positions - avg_positions`）

**理由**：
- exit reason 字段（`reversal_exit_count`、`time_exit_count` 等）引擎 metrics 中不包含，但 trades CSV 有 `exit_reason` 列可以聚合
- constraint 字段（`cap_hit_single`、`cash_skip_count` 等）引擎 metrics 中不包含，但 candidates CSV 有 `reject_reason` / `skip_reason` 列可以聚合
- 此方式与 `_extract_trigger_counters()` 的思路一致，但简化为只读取 results_dir 下的文件（不依赖 group_dir 结构）

**备选（否决）**：调用 `_extract_trigger_counters()` 函数——该函数依赖 group_dir 目录结构（report_summary.json、report.json 等），但单次运行扁平化后这些文件不存在。

### D3: 完整 counters 字段列表

写入 `run_meta.json` 的 `counters` 对象包含以下 11 个字段：

| 字段 | 类型 | 来源 |
|------|------|------|
| `atr_stop_exit_count` | int | trades CSV: exit_reason == "ATR_STOP_LOSS" |
| `atr_trail_exit_count` | int | trades CSV: exit_reason == "ATR_TRAIL_EXIT" |
| `atr_trail_update_count` | int | result dict（引擎 metrics） |
| `reversal_exit_count` | int | trades CSV: exit_reason in ("SIGNAL_REVERSE", "SMA_CROSS_DOWN") |
| `time_exit_count` | int | trades CSV: exit_reason == "TIME_EXIT" |
| `avg_positions` | float | result dict（引擎 metrics） |
| `slots_left` | float | 派生: max_positions - avg_positions |
| `cap_hit_single` | int | candidates CSV: reason == "BLOCK_SINGLE_CAP" |
| `cap_hit_industry` | int | candidates CSV: reason == "BLOCK_INDUSTRY_CAP" |
| `cash_skip_count` | int | candidates CSV: reason == "SKIP_CASH_INSUFFICIENT" |
| `lot_skip_count` | int | candidates CSV: reason == "SKIP_LOT_TOO_SMALL" |

额外包含（已在引擎 metrics 中，供 wbTriggers 表格使用）：
- `gate_on_rate` (float)
- `mf_rank_applied_rate` (float)
- `trend_slope_block_count` (int)
- `raw_signal`, `blocked`, `orders`, `skipped`, `closed_trades` (int)

### D4: 清理 _extract_trigger_counters() 死代码

**选择**：保留该函数但不在本次修复中调用。该函数的逻辑依赖 group_dir 结构（report_summary.json 等），与单次运行的扁平目录结构不兼容。如果后续不再需要 group inspect 路径，可在单独的清理 change 中移除。

**理由**：最小化修改范围，避免影响其他代码路径。

## Risks / Trade-offs

- **[Risk] trades CSV 列名不确定** → 检查 `portfolio_builder.py` 中写出 trades 时的列名，确认 exit_reason 列是否存在。若列名为 `reason_code` 而非 `exit_reason`，需适配。
- **[Risk] candidates CSV 可能无 reject reason 列** → 如果引擎未输出 skip/block reason 列到 candidates CSV，则 constraint 计数器默认为 0。这与现状一致（当前也是 0），不算回退。
- **[Risk] run_meta.json 结构变更** → 新增 `counters` 字段为纯增量，前端已有 `art?.run_meta?.counters || row` fallback，向后兼容。

## Migration Plan

无需迁移。变更仅影响新运行的产物输出。已有历史产物的 `run_meta.json` 不受影响，前端 fallback 机制保证旧数据仍可显示。

## Open Questions

1. `portfolio_trades.csv` 中 exit reason 列的确切列名是什么？（需确认：`exit_reason`、`reason_code` 还是 `sell_reason`）
2. `portfolio_candidates.csv` 中是否包含 reject/skip reason 列？列名是什么？
