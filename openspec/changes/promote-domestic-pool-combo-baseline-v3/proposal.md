## Why

`sr_20260510_domestic_pool_three_window_audit` 已完成 `DOMESTIC_POOL_BASE` 三窗口补证。用户明确要求直接将该轮结果提升为组合基线 V3。

本次提升不是新策略逻辑开发，而是 baseline apply：将全周期 `1226` 结果 `exp_20260510_034302669_7790` 登记为新的 stock+ETF 组合 baseline truth，并保留旧锚点用于回滚和审计。

## What Changes

- **BREAKING**: 当前 stock+ETF 组合 active baseline 从 `CN_STOCK_ETF_FORMAL_V1` 切换为 `CN_STOCK_ETF_COMBO_BASELINE_V3`。
- 新 baseline 绑定 `linked_exp_id = exp_20260510_034302669_7790`。
- `CN_STOCK_ETF_FORMAL_V1` 标记为 `superseded`，保留目录与 linked experiment。
- `CN_STOCK_ETF_COMBO_BASELINE_V2` 标记为 `superseded`，保留作为 V3 的上一个研究锚点。
- 前端默认 bootstrap baseline 切换为 `CN_STOCK_ETF_COMBO_BASELINE_V3`。
- baseline regression 合同的 current anchor 切换为 V3。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `baseline-anchor-registration`: 允许在用户明确确认后将 domestic-only ETF pool 的全周期结果登记为 active stock+ETF 组合基线。

## Impact

- 影响 `outputs/baselines/` 注册状态、V3 baseline 目录和 `index.json`。
- 影响前端默认加载源。
- 影响 baseline regression 的当前锚点。
- 不修改股票腿、ETF 选择逻辑、成交时点、组合调度代码或研究 runner。
