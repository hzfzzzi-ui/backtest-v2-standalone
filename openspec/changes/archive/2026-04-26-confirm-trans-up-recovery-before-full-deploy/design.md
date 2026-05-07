# Design: confirm-trans-up-recovery-before-full-deploy

## Summary

给 `TRANS_UP` 恢复态增加两阶段部署：

1. `benchmark_off` 时允许 staged entry，但只按缩放后的 `order_value_scale` 轻仓进入
2. 后续 `benchmark_regime_on` 且仍处于 `TRANS_UP` 时，只对这批 staged holdings 做一次确认加仓

## Runtime Design

### New Config

在 `market_filter` 下新增：

- `trans_up_recovery_confirmed_top_up_scale_when_benchmark_on: float`

含义：

- `0.0` 表示关闭 confirmed top-up
- `>0` 表示对 staged recovery holding 的一次性加仓缩放比例

已有配置继续沿用：

- `allow_trans_up_recovery_entries_when_benchmark_off`
- `trans_up_recovery_entry_scale_when_benchmark_off`

### Stage 1: staged recovery entry

条件：

- `effective_state_5 == TRANS_UP`
- `trade_mode == TREND_LIGHT`
- `benchmark_regime_on == false`
- `allow_trans_up_recovery_entries_when_benchmark_off == true`

动作：

- 保留 buy signal
- `order_value_scale *= trans_up_recovery_entry_scale_when_benchmark_off`
- `entry_reason_code = TRANS_UP_RECOVERY_STAGED_ENTRY`

### Stage 2: confirmed top-up

条件：

- `effective_state_5 == TRANS_UP`
- `trade_mode == TREND_LIGHT`
- `benchmark_regime_on == true`
- `trans_up_recovery_confirmed_top_up_scale_when_benchmark_on > 0`
- 当前持仓存在，且 `holding_sources[symbol].entry_reason_code == TRANS_UP_RECOVERY_STAGED_ENTRY`

动作：

- 允许 existing holding top-up
- `order_value_scale *= trans_up_recovery_confirmed_top_up_scale_when_benchmark_on`
- `entry_reason_code = TRANS_UP_RECOVERY_CONFIRMED_TOP_UP`
- `entry_day_overwrite = true`

这样 fill accounting 在这次加仓成交后会把 holding source reason 更新为 confirmed top-up，避免重复加仓。

## Planning Constraint

candidate planning 默认不允许对已有股票仓位继续按新 entry 加仓，所以需要为这类 confirmed top-up 显式放行。

## Minimal A/B

最小候选只测一个 staged/confirmed 组合：

- `staged = 0.5`
- `confirmed_top_up = 0.5`

对比：

1. `false`
2. `true` full-open
3. staged candidate `0.5 + 0.5`

窗口：

1. `2012-2026`
2. `2018-2026`
