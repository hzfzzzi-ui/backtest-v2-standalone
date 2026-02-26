# Reason Code Taxonomy v1

本文件固化 `reason_code_counts.csv` 的原因码分层口径（v1）。

## 分层

- `Universe`：标的池过滤（示例：`UNIVERSE_*`）
- `Signal`：信号层过滤（示例：`SIGNAL_*`）
- `Gate-Regime`：门控/状态过滤（示例：`BLOCKED_*`, `GATE_*`, `REGIME_*`）
- `Execution`：成交层不可执行（示例：`SKIPPED_*`, `REJECTED_*`, `EXEC_*`）
- `RiskExit`：风控与退出（示例：`ATR_STOP_LOSS`, `ATR_TRAIL_EXIT`, `TREND_BREAK_EXIT`, `RISK_OFF_EXIT`）
- `Capital`：资金与仓位约束（示例：`CAPITAL_*`, `POSITION_*`, `SLOTS_*`）

## 文件契约

`reason_code_counts.csv` 必须包含列：

- `code`：`string`
- `count`：`int >= 0`
- `ratio`：`float >= 0`（推荐，若有总数则 `sum(ratio) ~= 1`）

## Router 侧提取优先级

1. `reason_code_summary.csv`
2. `report_summary.json` / `report.json` / `run_meta.json` 中的：
   - `reasons`
   - `exit_reason_breakdown`
   - `blocked_reasons_top3`（写入 `BLOCKED_*`）
   - `skipped_reasons_top3` / `top_skip_reason`（写入 `SKIPPED_*`）
3. `orders.csv` / `signals.csv` best-effort 聚合
4. 无源则写空壳并记录 `missing_reason_code_source`

