## Context

当前 `cn_etf_beta` 已经具备：

- 独立 ETF 日线真值表 `pams_cn_etf_daily`
- 独立 `cn_etf` 研究入口
- Governor / attribution / run_meta 的 ETF 语义

但最新主 smoke `cn_etf_first_wave_core` 仍然是：

- `trades = 0`
- `NO_DEPLOYABLE_SLOTS` 大量出现
- `TOTAL_RISK_BUDGET_REDUCED` 与 `slot_cap=0` 主导 ETF sleeve 行为

这说明当前系统仍把 ETF beta 放在“路径已接通，但未真正可交易”的阶段。问题不在数据和 read path，而在于：

- ETF beta 仍未拥有独立的低频选标/调仓逻辑
- ETF beta 的 deployability 仍被股票 alpha 的交易语义间接压死
- 当前 smoke 验收只证明了路径和审计，不证明策略真正可用

## Goals / Non-Goals

**Goals:**

- 让 `cn_etf_beta` 在现有 Governor 架构下具备最小可交易能力。
- 保持 canonical 五状态为唯一正式状态真相源，ETF beta 只消费五状态和 Governor 预算，不新增旁路状态机。
- 用最小规则实现低频、可解释、可审计的 ETF beta 选标与调仓。
- 把 smoke 验收提升为“路径通过 + 非零交易证据 + 审计通过”。

**Non-Goals:**

- 不扩首波 ETF 名单。
- 不接入 `518880/511010` 的正式防守层语义。
- 不接入 `value_bluechip_satellite` 或 `insurance_overlay`。
- 不做复杂优化器、宏观大类资产切换或参数扫面。
- 不把 ETF beta 做成第二套股票 breakout alpha 引擎。

## Decisions

### 1. `cn_etf_beta` 使用独立的 ETF 低频 selector，不再借壳股票 breakout provider

ETF beta 的正式定位是 `market_beta_sleeve`，不是股票 alpha。继续复用股票 breakout provider 会把 ETF 路径绑定到股票的候选生成、资金流语义、局部 budget 约束和 `NO_TRADE` 模式，事实已经证明这会导致 `0 trades`。

本次变更要求：

- `asset_scope=cn_etf` 的正式运行主线走 ETF beta selector/provider
- selector 只消费 ETF 真值表与 Governor 输出
- 不再消费股票 PIT、行业约束、ST 约束、个股 breakout 质量 veto

备选方案：

- 继续复用股票 breakout 壳，再调 budget 或 benchmark

不采用原因：

- 这会把 ETF beta 永久绑死在股票 alpha 语义上，和当前正式架构冲突。

### 2. ETF beta 的最小可交易规则采用“周频调仓 + 双窗口相对强弱 + 单一绝对趋势过滤”

Phase 1 的目标不是做最优策略，而是做最小可交易、可解释、可回退规则。规则收口为：

- 调仓频率：周频
- 正式候选池：`510300 / 510500 / 510050 / 512100`
- 默认不启用 `512890`
- 绝对过滤：`close > MA120`
- 相对强弱：`score = 0.6 * rank(120d_return) + 0.4 * rank(60d_return)`
- BULL：最多持有 2 只
- TRANS_UP：最多持有 2 只
- LIGHT：最多持有 1 只
- TRANS_DOWN / RISK_OFF：不持有 core beta

备选方案：

- 直接用个股 breakout
- 用日频 top1 轮动
- 在 TRANS_DOWN 继续持有 core beta

不采用原因：

- 个股 breakout 不符合 ETF beta 定位
- 日频轮动噪音过大，不利于 Phase 1 审计
- 在未正式接入防守层前，TRANS_DOWN 继续持有 core beta 会模糊风险边界

### 3. Governor 为 ETF beta 提供独立 deployability map，但仍只消费 canonical 五状态

ETF beta 不新增自己的状态机，只在 Governor 层定义独立的 deployment policy：

- `BULL`: deployable
- `TRANS_UP`: deployable with reduced sleeve cap
- `LIGHT`: deployable with conservative sleeve cap
- `TRANS_DOWN`: no deployable core beta slots
- `RISK_OFF`: no deployable core beta slots

这里的关键不是新增新状态，而是：

- ETF beta 的 `slot_cap / selected_count / deployability reason` 由 ETF beta policy 决定
- 股票 alpha 的 `trade_mode` 不再直接作为 ETF beta 的局部真相

备选方案：

- 继续让 ETF beta 直接复用股票 alpha 的 `trade_mode_main/light/notrade`

不采用原因：

- 当前 smoke 的 `0 trades` 已经证明这条路径不可接受。

### 4. `research_audit` 为 ETF beta 增加最小可交易 smoke gate

之前的 smoke 验收只要求：

- path truth 正确
- audit/governor 语义通过

这不足以证明 ETF beta 可进入正式研究主线。本次 smoke gate 提升为：

- `provider/read path` 真值通过
- `etf_beta_sleeve` gate 通过
- `attribution_traceability` gate 通过
- 主 smoke 窗口 `orders > 0`
- 主 smoke 窗口 `trades > 0`

备选方案：

- 保留“路径通过即可”的 smoke

不采用原因：

- 这会继续允许“系统说自己接入了 ETF beta，但实际上不会交易”。

## Risks / Trade-offs

- [Risk] ETF 低频规则过于保守，交易数仍偏低  
  → Mitigation：先追求非零且可解释，不在本 change 内做收益优化。

- [Risk] Governor 的 ETF beta deployability map 与股票 alpha 预算语义发生冲突  
  → Mitigation：明确 ETF beta 只改 sleeve deployability，不改 canonical 五状态和总预算真相。

- [Risk] 2016-2026 主 smoke 达不到非零成交  
  → Mitigation：将 smoke 失败视为 change 未完成，不用结果包装成“接入成功”。

- [Risk] 周频 selector 引入新的运行路径，增加调试成本  
  → Mitigation：强制输出 reason codes、selected/eligible ETF、weekly rebalance 诊断。

## Migration Plan

1. 先新增 ETF beta selector/provider 与配置入口。
2. 再接 Governor 的 ETF beta deployability map。
3. 再接 `run_meta / audit / research_audit` 的可交易诊断字段。
4. 最后重跑 `etf/cn_etf_first_wave_core` 的 `1626` smoke。
5. 若 smoke 未达非零交易，则回滚 selector route，不保留半接入状态。

回退策略：

- 回退 ETF beta selector/provider 与 route 绑定
- 回退 Governor 的 ETF beta deployability map
- 回退 `research_audit` 的 ETF beta tradability gate

## Open Questions

- `LIGHT` 状态下默认持有 1 只 ETF 是否足够保守；若 smoke 仍显著过少，后续可再单独评估 `LIGHT -> top2`。
- `512890` 是否在下一条 change 里升格为正式 limited defense 默认候选；本次先不启用。
