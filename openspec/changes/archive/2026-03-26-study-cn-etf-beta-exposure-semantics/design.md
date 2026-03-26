## Context

当前 ETF 线已经完成了独立 provider、Governor 接入、research audit 接入，以及 `rule family` 与 `stabilizer v2` 两轮研究。现有事实已经比较清楚：

- 当前 V2 核心风险篮子 `510050 + 510300` 的价格年化本身不高。
- ETF sleeve 的平均实际总暴露长期偏低，历史研究里一度只有约 `5%`，V2 抬升后也仅约 `10%`。
- `fallback` 的影响远小于“预算上限过低 + 实际部署不足”。
- 继续改候选池或微调买卖规则，无法先回答“ETF 稳定器到底有没有被正常部署”。

所以这轮设计必须把问题收窄为：**ETF sleeve 到底应该拿多少、最低应该部署多少、为什么没有部署到位。**

## Goals / Non-Goals

**Goals:**

- 为 `cn_etf_beta` 建立可研究、可审计的暴露语义。
- 让 ETF sleeve 的研究结论能明确区分：
  - 预算上限损失
  - 空仓/低仓损失
  - fallback 替代损失
  - 过滤/切换损失
- 为 Governor 定义更适合 beta 稳定器的 ETF 部署口径。
- 形成下一轮最小 AB：只比较暴露语义，不混入候选池变化。

**Non-Goals:**

- 本 change 不改 ETF 主候选池。
- 本 change 不新增防守层正式资产。
- 本 change 不把 `511010` 升级为独立 defense sleeve。
- 本 change 不做前端布局改造。
- 本 change 不推进 unified runtime 的个股+ETF 单实验入口。

## Decisions

### 1. 先把 ETF 问题定义成“暴露语义问题”，而不是“选池问题”

- 决策：本轮正式研究固定当前 ETF 主候选池，不再把收益问题继续归因到候选池切换。
- 原因：最近两轮结果已经证明，收益差的最大损失来自预算上限和部署不足，而不是 `510050` 与 `510300` 的相对优先级。
- 备选：
  - 继续改候选池：会把“拿得太少”和“选得不对”混在一起，研究不可归因。

### 2. ETF sleeve 需要独立的目标暴露语义

- 决策：为 ETF sleeve 明确研究并比较以下语义：
  - 固定 `target_exposure`
  - 状态分段 `target_exposure`
  - `min_deployable_exposure`
- 原因：当前 ETF sleeve 的主问题不是“有没有信号”，而是“理论想拿多少，实际只拿了多少”。
- 备选：
  - 继续沿用隐式 slot-cap 映射：无法清楚解释 under-deploy 来源。

### 3. ETF deployability 要从隐式诊断变成正式证据

- 决策：把以下内容升级为正式产物字段和 audit 证据：
  - `target_exposure`
  - `min_deployable_exposure`
  - `actual_exposure`
  - `deployability_gap`
  - `under_deploy_reason_codes`
- 原因：只有把理论暴露和实际暴露并排输出，才能判断收益差是不是“仓位没给出来”。
- 备选：
  - 继续只输出 gross exposure：不足以解释是预算压缩、无合格标的，还是 fallback 没触发。

### 4. fallback 继续视为 sleeve-local，而不是 defense 正式层

- 决策：本轮可以继续比较 `cash` 与 `511010`，但只把它们视为 ETF sleeve-local fallback。
- 原因：用户当前要先研究 beta 稳定器暴露语义，而不是扩正式防守层。
- 备选：
  - 把 `511010` 正式化成 defense sleeve：会把问题扩成另一条主线。

### 5. 验收优先顺序从收益改成“部署是否合理”

- 决策：下一轮 AB 的正式验收优先看：
  - 全窗口平均实际暴露
  - 有持仓日平均暴露
  - target vs actual gap
  - under-deploy 原因分布
  - fallback 占比
  - 再看收益与回撤
- 原因：如果暴露语义都没跑对，收益对比没有解释力。
- 备选：
  - 继续只看 CAGR / Sharpe：会掩盖结构问题。

## Risks / Trade-offs

- [ETF 暴露抬升后回撤恶化] → 同时输出目标暴露、实际暴露、回撤和 under-deploy 原因，避免只看单一收益。
- [把 ETF sleeve 推得过像独立主策略] → 明确本轮只研究 beta 稳定器暴露语义，不改其系统角色。
- [fallback 研究再次混淆 defense 边界] → 在 spec 和 audit 中明确标记为 sleeve-local fallback。
- [Governor 语义扩展影响 A 股个股主线] → 仅允许 ETF sleeve 使用新增暴露字段，不改 `cn_stock_trend_alpha_core` 现有预算语义。

## Migration Plan

1. 先新增 `cn-etf-beta-exposure-semantics` spec，明确研究对象和 AB 结构。
2. 再修改 `cn-etf-beta-sleeve` spec，增加目标暴露与最小可部署语义。
3. 再修改 `cn-a-portfolio-governor` spec，要求输出 ETF sleeve 暴露与 under-deploy 证据。
4. 再修改 `backtest-research-audit` spec，把 ETF 暴露质量纳入正式 gate。
5. 实现时先跑最小 AB：
   - 控制组：当前 V2 基线暴露语义
   - 候选组：更高/分段 `target_exposure`
   - 候选组：不同 `min_deployable_exposure`
6. 若部署明显改善但收益仍弱，则保留研究结论，不强推正式升级。

## Open Questions

- ETF sleeve 的下一轮主研究应优先比较：
  - 固定暴露抬升
  - 还是状态分段暴露
- `min_deployable_exposure` 应以绝对比例定义，还是以 slot 语义映射定义。
- 当前 `511010` fallback 在暴露语义研究里是否需要保留为并行对照，还是只保留 `cash` 以简化归因。
