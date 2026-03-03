# Design: Fix Frontend-Backend Pipeline Integrity

## D1: reason_code 动态化（A1）

**现状**: `portfolio_simulator_strict.py:550,675-676` 硬编码 `SMA_CROSS_UP/DOWN`。
**决策**: 用已有的 `ma_type` 变量（line 218）构造 `cross_up_code = f"{ma_type}_CROSS_UP"` 和 `cross_down_code = f"{ma_type}_CROSS_DOWN"`，在循环外一次性计算，循环内引用。
**影响**: 3 处替换（line 550 的 SELL reason, line 675-676 的 BUY reason/reason_code）。

## D2: _compute_metrics 补漏斗字段（A2）

**现状**: `_compute_metrics()` 接收 `total_buy_signals` 和 `blocked_by_trend_count` 但 return dict 不含 `raw_signal` / `blocked` / `orders` / `skipped`。
**决策**: 在 return dict 中追加 4 个字段：
- `"total_buy_signals": int(total_buy_signals)` — 原始信号数
- `"blocked_signals": int(blocked_by_trend_count)` — 被趋势过滤拦截数
- `"orders_filled": int(len(trades_df[trades_df["side"]=="BUY"]))` — 实际 BUY 成交数
- `"sell_trades": int(len(trades_df[trades_df["side"]=="SELL"]))` — SELL 成交数

同时更新 experiment_runner 的 m.get 映射，优先读新字段名。

## D3: exit_rules 参数映射补齐（B3）

**现状**: `_build_runtime_cfg_from_workbench()` 只映射了 entry_filter 和 hold_constraint，ATR stop/trail/time 配置被丢弃。
**决策**: 从 `wb_cfg.exit_rules` 读取 `atr_stop.enabled/k`、`trailing.enabled/k`，映射到 `strategy.params.enable_atr_stop/atr_stop_k/enable_atr_trail/atr_trail_k`。
**不做**: time_exit 映射暂不加（引擎尚无 TIME_EXIT 逻辑，在 D4 中一起处理）。

## D4: TIME_EXIT 引擎逻辑（A3）

**现状**: 前端有 wbExitTime / wbExitDays 控件，但引擎无 TIME_EXIT 退出分支。
**决策**: 在 held-only SELL 循环中，检查 `entry_day[sym]` 存在且 `(day - entry_day[sym]).days >= max_hold_days` 时生成 `TIME_EXIT` reason。优先级在 cross_down 之前、ATR_TRAIL 之后。
**参数**: 从 strategy 读 `max_hold_days: int = 0`（0 表示不启用）。需要在 ema_cross / sma_cross 策略和 registry 中新增此字段，同时在 `_build_runtime_cfg_from_workbench()` 中映射 `exit_rules.time_exit.n_days`。

## D5: reversal 统计修正（B1）

**现状**: `backtest_v2_artifacts.py:223` 只匹配 `["SIGNAL_REVERSE", "SMA_CROSS_DOWN"]`。
**决策**: 改为 `["SIGNAL_REVERSE", "SMA_CROSS_DOWN", "EMA_CROSS_DOWN"]`。

## D6: experiment label 修正（B2）

**现状**: `_generate_experiment_label()` 固定从 `sma` 取 MA 参数。
**决策**: 先判断 strategy 是否含 "EMA"，再取对应的 ma config key。

## D7: 前端 config_draft 同步（C1+C2）

**现状**: `renderSummaryBar()` 和 JSON 预览读 `state.config_draft`，加载实验后未更新。
**决策**: 在 `loadActiveArtifacts()` 成功加载 config 后，调用已有的 `applyConfigToUI(config)` 再调 `buildConfigDraft()` 以同步 `state.config_draft`。

## D8: atr_trail_update_count 修正（A4）

**现状**: artifacts 从 `triggered_rule` 列匹配 "TRAIL"+"UPDATE" 模式，但引擎不产生此模式。
**决策**: 在引擎 SELL 循环中，当 `peak_close_state` 被更新（即 peak 上移）且持仓开启了 atr_trail 时，在 daily_rows 中记录 trail update 事件的计数。将计数直接写入 metrics dict，artifacts 直接读取而非从 CSV 重建。

## D9: compare_symbol 不硬编码（C5）

**现状**: `backtest_v2.js:698` 硬编码 `compare_symbol: '000001.SH'`。
**决策**: 改读 `byId('wbBenchmark')?.value || '000001.SH'`。

## D10: diagnostics tRows 补齐（C4）

**现状**: diagnostics 表缺 reversal_exit_count。
**决策**: 在 tRows 数组中追加 `['信号反转退出', counters.reversal_exit_count ?? 0, false]`。
