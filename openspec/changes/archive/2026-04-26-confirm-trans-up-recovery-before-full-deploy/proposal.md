# Change Proposal: confirm-trans-up-recovery-before-full-deploy

## Why

严格 A/B 已经证明：

- `allow_trans_up_recovery_entries_when_benchmark_off=true` 对 `2018-2026` 是正向的
- 但对 `2012-2017` 是明显负向的

根因不是恢复态不能参与，而是恢复态一旦放开，就会从轻仓试错直接放成接近常态重仓，导致早期 `TRANS_UP` 的低质量恢复仓被大规模带入组合，再拖进 `BEAR / RISK_OFF_EXIT`。

## What Changes

本 change 只研究一个最小问题：

- 当 `TRANS_UP + benchmark_off` 时，允许恢复态参与，但只以轻仓进入
- 当后续 `benchmark_regime_on` 且仍处于 `TRANS_UP` 时，只对这批 staged recovery holdings 做一次确认加仓

本 change 不改：

- 股票池
- 排序因子
- breakout 定义
- ETF 逻辑
- 账户层状态机

## Success Criteria

最小 A/B 需要同时看：

1. `2012-2026` 全样本相对 `full-open` 不再显著恶化
2. `2018-2026` 相对 `false` 仍保留主要收益改善
3. `TRANS_UP` 不再从轻仓试错直接抬到接近常态重仓

## Non-Goals

- 不做恢复态专用评分体系
- 不做二次确认 bar-count 规则
- 不做新的 regime 定义
