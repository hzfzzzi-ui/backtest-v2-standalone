## 1. 引擎 reason_code 动态化 (A1)

- [x] 1.1 在 `portfolio_simulator_strict.py` 循环外（line 218 附近）新增 `cross_up_code = f"{ma_type}_CROSS_UP"` 和 `cross_down_code = f"{ma_type}_CROSS_DOWN"`
  - DoD：两个变量在 simulation loop 外声明
  - 验证：EMA 策略时 cross_up_code == "EMA_CROSS_UP"

- [x] 1.2 替换 line 550 `reason = "SMA_CROSS_DOWN"` → `reason = cross_down_code`
  - DoD：SELL 信号 reason 动态化
  - 验证：EMA 策略的卖出 reason_code 为 EMA_CROSS_DOWN

- [x] 1.3 替换 line 675-676 `reason="SMA_CROSS_UP"` 和 `reason_code="SMA_CROSS_UP"` → 使用 `cross_up_code`
  - DoD：BUY 信号 reason/reason_code 动态化
  - 验证：EMA 策略的买入 reason_code 为 EMA_CROSS_UP

## 2. 漏斗计数修复 (A2)

- [x] 2.1 在 `portfolio_builder.py` `_compute_metrics()` return dict 中追加 `"total_buy_signals": int(total_buy_signals)` 和 `"blocked_signals": int(blocked_by_trend_count)`
  - DoD：metrics dict 含两个新字段
  - 验证：回测后 metrics["total_buy_signals"] > 0

- [x] 2.2 在 `experiment_runner.py` 中更新 `"raw_signal"` 提取逻辑，优先读 `m.get("total_buy_signals")`；`"blocked"` 优先读 `m.get("blocked_signals")`
  - DoD：result dict 的 raw_signal 和 blocked 不再为 0
  - 验证：run_meta.counters.raw_signal 与 run_meta.counters.blocked 均 > 0（有信号时）

## 3. exit_rules 参数映射 (B3)

- [x] 3.1 在 `backtest_v2.py` `_build_runtime_cfg_from_workbench()` 中从 `exit_rules.atr_stop` 读取 enabled/k，映射到 `strategy.params.enable_atr_stop` 和 `strategy.params.atr_stop_k`
  - DoD：前端 ATR 止损配置传递到引擎
  - 验证：关闭 ATR 止损 → 回测无 ATR_STOP_LOSS 退出

- [x] 3.2 同上，从 `exit_rules.trailing` 读取 enabled/k，映射到 `strategy.params.enable_atr_trail` 和 `strategy.params.atr_trail_k`
  - DoD：前端移动止盈配置传递到引擎
  - 验证：开启 trailing → 回测有 ATR_TRAIL_EXIT 退出

- [x] 3.3 从 `exit_rules.time_exit` 读取 enabled/n_days，映射到 `strategy.params.max_hold_days`（enabled=false 时映射 0）
  - DoD：前端时间退出配置传递到引擎
  - 验证：设置 time_exit.n_days=20 → strategy.params.max_hold_days=20

## 4. TIME_EXIT 引擎实现 (A3)

- [x] 4.1 在 `ema_cross.py` 和 `sma_cross.py` 新增 `max_hold_days: int = 0` 字段
  - DoD：策略类有 max_hold_days 字段
  - 验证：import 无报错

- [x] 4.2 在 `registry.py` ema_cross 和 sma_cross 分支中从 params 读取 `max_hold_days` 并传入构造
  - DoD：build_strategy() 正确传递 max_hold_days
  - 验证：构造后 getattr 值正确

- [x] 4.3 在 `portfolio_simulator_strict.py` 循环外读取 `max_hold_days = int(getattr(strategy, "max_hold_days", 0))`
  - DoD：引擎有 max_hold_days 变量
  - 验证：代码无语法错误

- [x] 4.4 在 held-only SELL 循环中（reason 判定区，ATR_TRAIL 之后、cross_down 之前）新增 TIME_EXIT 检查：若 `max_hold_days > 0` 且 `sym in entry_day` 且 `(day - entry_day[sym]).days >= max_hold_days` 则 `reason = "TIME_EXIT"`
  - DoD：持仓超过 max_hold_days 自动生成 TIME_EXIT
  - 验证：max_hold_days=10 时持仓 12 天的标的被 TIME_EXIT

## 5. 中间层修正 (B1+B2)

- [x] 5.1 在 `backtest_v2_artifacts.py` line 223 改为 `rc.isin(["SIGNAL_REVERSE", "SMA_CROSS_DOWN", "EMA_CROSS_DOWN"])`
  - DoD：reversal 统计覆盖 EMA 策略
  - 验证：EMA 回测的 reversal_exit_count 正确

- [x] 5.2 在 `backtest_v2_artifacts.py` `_generate_experiment_label()` 中按策略类型选择 ma config key：`ma_key = "ema" if "EMA" in strategy else "sma"`
  - DoD：EMA 策略 label 显示正确的 fast/slow
  - 验证：EMA 5/20 回测 label 含 "EMA_CROSS 5/20"

## 6. 前端修正 (C1+C2+C4+C5)

- [x] 6.1 在 `backtest_v2.js` `loadActiveArtifacts()` 加载 config 成功后，调用 `applyConfigToUI(loaded_config)` 再调 `buildConfigDraft()` 以同步 `state.config_draft`
  - DoD：加载历史实验后 config_draft 与实际配置一致
  - 验证：运行 EMA 回测 → 加载 → 摘要栏显示 EMA

- [x] 6.2 在 diagnostics tRows 数组中追加 `['信号反转退出', counters.reversal_exit_count ?? 0, false]`
  - DoD：诊断表含 reversal 行
  - 验证：回测后诊断面板可见信号反转退出计数

- [x] 6.3 `runPayloadFromDraft()` 中 `compare_symbol` 改读 `byId('wbBenchmark')?.value || '000001.SH'`
  - DoD：compare_symbol 跟随 benchmark 输入
  - 验证：设置 benchmark=000300.SH 后 compare_symbol 一致

## 7. atr_trail_update 计数修正 (A4)

- [x] 7.1 在 `portfolio_simulator_strict.py` 循环外新增 `atr_trail_update_count = 0`，在 held-only SELL 循环中当 `enable_atr_trail` 且 `peak_close_state[sym]` 被更新（新 peak > old peak）时计数 +1
  - DoD：trail update 事件被准确计数
  - 验证：开启 trailing 回测后 atr_trail_update_count > 0

- [x] 7.2 将 `atr_trail_update_count` 写入 metrics dict，在 `experiment_runner.py` 中透传，在 `_build_counters()` 中直接读取而非从 CSV 模式匹配
  - DoD：atr_trail_update_count 端到端传递
  - 验证：run_meta.counters.atr_trail_update_count 正确

## 8. 端到端验证

- [x] 8.1 Docker 构建，使用 EMA_CROSS 策略运行回测，验证：(a) trade reason_code 含 EMA_CROSS_UP/DOWN；(b) raw_signal > trades；(c) ATR 止损可通过前端开关控制；(d) 诊断面板计数器正确
  - DoD：所有修复在端到端场景中可验证
  - 验证：对比修复前后的 run_meta.json 差异
