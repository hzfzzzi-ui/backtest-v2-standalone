## Why

当前已经分别拿到了 `baseline_V10.1 / 2012-2026` 的正式结果和 `ABSNETMF_MA20` 在严格历史 `PIT_DYNAMIC` 口径下的月频结果，但还没有一个可审计的研究实验去回答一个更具体的问题：在 `V10.1` 的市场过滤器非牛市阶段，是否值得用半仓现金承载 `ABSNETMF` 月频线，而在牛市阶段继续使用 `V10.1` 主线。

这个问题同时涉及市场阶段切换、双策略拼接和结果可解释性，属于高风险研究实验，必须先把实验口径写清楚，再实施，避免把临时 research shell 误当成正式主线行为。

## What Changes

- 新增一个 research-only 的混合实验定义：`V10.1` 牛市阶段使用主线日频收益，非牛市阶段使用 `0.5 * ABSNETMF + 0.5 cash` 的日频收益拼接。
- 明确本次实验**不修改** `baseline_V10.1` 主逻辑、不修改 `ABSNETMF` 因子逻辑、不修改任何正式引擎或 runtime 行为。
- 为该混合实验新增最小审计产物，至少输出：
  - 混合净值序列
  - 切换日统计
  - `trade_mode` 分布
  - `V10.1` / `ABSNETMF` 各自贡献区间摘要
- 明确混合实验的边界：它是研究拼接壳，不是正式可交易策略实现。

## Capabilities

### New Capabilities
- `regime-switch-hybrid-study`: 定义一个 research-only 的双策略拼接实验能力，允许在既有实验产物之上按市场过滤阶段切换收益源并输出可审计对照产物。

### Modified Capabilities
- 无

## Impact

- 主要影响 `backend/scripts/ops/*` 下的研究脚本与 `outputs/ops/*` 研究产物。
- 可能新增少量测试或复用工具函数，但不应修改 `baseline_V10.1`、`engine_vector`、`experiment_runner` 或正式前端加载协议。
- 本次 change 的目标是生成一轮可信研究结果，不是把混合壳接入正式产品路径。
