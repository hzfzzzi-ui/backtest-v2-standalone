## Context

当前主线因子拆分已经证明：

- `breakout_distance / residual_strength / trend_quality` 不适合作为正向横截面 rank 因子；
- `final_score` 整体也不是简单正向排序逻辑；
- 但 `volume_price_quality_score` 与 `breakout_quality_score` 在基线锚定研究里持续表现为偏正质量项。

需要把这两项从 `final_score` 组合里单独拉出来，作为一条独立的质量研究线。

## Goals / Non-Goals

**Goals**
- 建立 positive quality factor catalog。
- 生成 quality snapshots 与 quality score snapshot。
- 提供独立的 study surface 跑三窗口研究。

**Non-Goals**
- 不改主线正式排序。
- 不在本条 change 里把 `sector_strength_score` 强行并入正向质量项。
- 不在本条 change 里做 runtime A/B。

## Decisions

### D1. 首版只收两项
- `volume_price_quality_score`
- `breakout_quality_score`

原因：这是当前证据最清楚的正向质量项，先保边界。

### D2. 继续按 rank 因子研究
这条线研究的是“高质量分是否对应更好的未来收益”，所以沿用 rank surface。

### D3. 保持研究层隔离
只做 catalog/snapshot/study surface，不接 runtime。

## Risks / Trade-offs

- [风险] 样本仍然是基线锚定 traded-core 样本。→ 先接受，后续再做候选池扩展。
- [风险] 只做两项可能遗漏别的正向 context。→ 当前先收最清楚的部分，不扩张边界。
