## Why

当前正式主线 `baseline_V10.1` 的官方锚点仍然固定在 `2021-01-04 ~ 2026-03-20`，这与当前项目要求的更长全周期审计口径不一致。用户已明确要求把正式 baseline 台账改为从 `2012-01-04` 开始，而且这次变更要保持 `baseline_V10.1` 的策略逻辑不变，只重挂官方窗口和 linked experiment。

如果不显式完成这次重挂，系统里会同时存在：

- `baseline_V10.1` 官方台账仍指向 `2021-2026`
- 实际讨论和验证口径已经转向 `2012-2026`

这会直接破坏基线的可解释性、可审计性和可回滚性。

## What Changes

- 将 `baseline_V10.1` 的官方配置快照窗口改为 `2012-01-04 ~ 最新正式结束日`
- 将 `baseline_V10.1` 的 `linked_exp_id` 重挂到已经完成的正式 stock-only 实验 `exp_20260328_220801073_478b`
- 同步刷新 `outputs/baselines/baseline_V10_1/` 下的 `baseline.json`、`config.json`、baseline 索引和 baseline 报表资产
- 为这次重挂补齐最小 OpenSpec 变更，明确这是一次“既有 baseline 官方锚点重挂”，不是新策略上线，也不是新 baseline 版本注册

## Capabilities

### Modified Capabilities

- `baseline-anchor-registration`: 既有正式 baseline 必须支持经批准的官方窗口重挂，并同步更新配置快照、linked experiment 和 baseline 索引
- `script-surface-governance`: 既有正式 baseline 锚点重挂后，baseline ledger/report/champion 资产必须追加可审计记录

## Impact

- 影响产物：
  - `outputs/baselines/baseline_V10_1/baseline.json`
  - `outputs/baselines/baseline_V10_1/config.json`
  - `outputs/baselines/index.json`
  - `outputs/baselines/baseline_V10_1/machine/*`
  - `outputs/baselines/baseline_V10_1/human/*`
- 不改变：
  - `baseline_V10.1` 策略逻辑
  - A 股个股主引擎
  - ETF 逻辑
  - `baseline_V10.2`
