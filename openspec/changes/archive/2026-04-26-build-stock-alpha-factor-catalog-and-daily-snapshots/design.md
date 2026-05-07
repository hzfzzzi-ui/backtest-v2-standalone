## Context

当前平台的个股 alpha 研究主线仍然以“策略逻辑 + 运行结果”作为研究主入口，导致以下问题：

- 原子因子没有正式目录，研究入口更多依赖策略配置和代码约定
- 因子值、标准化值、排序值和最终信号混在一起，难以区分哪一层发生了变化
- 研究一条新逻辑时，经常必须跑完整回放，无法先独立判断单因子和因子组合本身是否成立
- 因子、状态、预算和执行耦合过紧，不利于后续做连续状态分数和 runtime 解耦

当前阶段不应直接重写主策略，而应先把研究平台的第一层基础设施建出来：正式的因子目录、正式的因子快照、正式的研究入口。

## Goals / Non-Goals

**Goals:**

- 给个股 alpha 第一版原子因子建立统一目录和元数据合同
- 给个股 alpha 建立日频因子快照产物，保证 as-of、availability 和标准化口径可审计
- 支持单因子与因子组合研究作为原生研究入口，而不是强依赖完整回放
- 为后续第二条 change 的“连续状态分数”提供可直接消费的研究基础

**Non-Goals:**

- 不改 `baseline_V10.1` 主行为
- 不让 runtime 默认直接消费新的 factor snapshot
- 不在本 change 内引入连续状态分数
- 不扩股票池、不改 breakout 逻辑、不改 ETF 或账户预算逻辑

## Decisions

### Decision 1: 第一条 change 只做 stock alpha，不同时引入 ETF 或 account factor

原因：
- 当前最明确的重构需求来自个股 alpha 研究层
- 如果第一条就把 ETF、状态分数和预算一起做，会直接失去归因

备选方案：
- 一次性做全平台因子目录
- 结论：拒绝，范围过大，L3 风险不可控

### Decision 2: 因子平台先输出三层产物，而不是只输出一个总分

三层产物：
- 原子因子值 `raw_value`
- 标准化/秩次值 `normalized_value / rank_value`
- 研究层组合分数 `factor_score`

原因：
- 你要的是可解释因子优先
- 只有把这三层分开，后面才能清楚判断问题出在因子本身、标准化过程还是组合方式

备选方案：
- 只输出一个最终 alpha score
- 结论：拒绝，可解释性不足

### Decision 3: 日频 factor snapshot 必须是正式研究产物，不允许 runtime 隐式重算

原因：
- 当前平台最需要解决的是口径漂移
- 如果 factor snapshot 只是一个运行期临时对象，后续仍然会回到“策略里现算一套、报表里展示另一套”

备选方案：
- 先在 runtime 临时重算，后面再沉淀产物
- 结论：拒绝，会反向污染研究口径

### Decision 4: 第一版原子因子数量保持小而硬

第一版建议只覆盖：
- `breakout_distance`
- `residual_strength`
- `trend_quality`
- `volatility_penalty`
- `liquidity_quality`

原因：
- 第一条 change 的目标是平台基础，不是因子 zoo
- 因子太多会直接引入新的过拟合和治理负担

备选方案：
- 一次性把所有现有 scoring 字段都因子化
- 结论：拒绝，范围失控

## Risks / Trade-offs

- [风险] 因子目录定义过大，第一条 change 就开始承载策略争议 → **缓解**：第一版只收 5 个原子因子，其他一律后移
- [风险] snapshot 产物和 runtime 现有字段重名，造成展示口径混淆 → **缓解**：独立命名 `factor_snapshot / score_snapshot`，不复用旧 runtime 字段名
- [风险] 研究入口和完整回放入口边界不清 → **缓解**：本 change 明确只提供单因子/因子组合研究入口，不接入主回放默认链路
- [风险] 后续第二条 change 需要连续状态分数时又重算一遍因子 → **缓解**：本 design 要求连续状态分数消费第一条 change 产物，而不是另起一套实现

## Migration Plan

1. 先建立 stock alpha 因子目录 schema 和第一版 catalog
2. 再建立日频 factor snapshot 产物和落盘协议
3. 再建立单因子 / 因子组合研究入口
4. 等这三层都稳定后，再开启第二条 change：连续状态分数

回退策略：
- 如果第一版 catalog 或 snapshot 设计不成立，只回退新增研究基础设施，不触碰现有主策略链路

## Open Questions

- 第一版标准化是否统一用横截面 rank，还是允许部分因子保留时间序列标准化
- 因子组合研究的第一版标准输出，是否需要直接包含 IC/分层收益/覆盖率三类指标
- factor snapshot 的正式持久化位置，是进入独立 side table，还是先作为研究产物文件落盘
