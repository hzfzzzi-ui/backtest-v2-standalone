## Why

当前主线分解结果里，真正稳定偏正的不是 `final_score` 整体，而是其中少数质量项，尤其是：

1. `volume_price_quality_score`
2. `breakout_quality_score`

如果不把这条线独立收成研究对象，后续仍然会把“主线综合分偏弱”和“质量子项偏正”混在一起解释。

## What Changes

- 新增 positive quality factor catalog，首版只收当前主线已观察到偏正的质量项。
- 新增 positive quality factor snapshots 与 factor score snapshots。
- 新增 positive quality factor study surface，支持单因子和质量组合分研究。
- 明确这条 change 仅用于研究层，不改主线排序、预算、执行或退出。

## Capabilities

### New Capabilities
- `positive-quality-factor-catalog`
- `positive-quality-factor-snapshots`
- `positive-quality-factor-study-surface`

### Modified Capabilities
- 无

## Impact

- 受影响代码主要位于 `backend/research`、`research/studies/factors` 和 `openspec`。
- 不改变 `baseline_V10.1` 的正式行为。
