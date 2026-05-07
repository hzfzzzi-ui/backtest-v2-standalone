## Context

当前 ETF 弱势研究已经连续做了两轮收口：
1. 先把弱势状态从“被再平衡节奏直接挡掉”改成“进入正式 weak-state defense redeploy 路径”。
2. 再把弱势目标结构改成 `债 + 少量核心宽基`。

最新回放的结论很明确：目标结构已经变了，但实际 `RISK_OFF` 行为没有变化，`RISK_OFF` 非零持仓率与平均 ETF 暴露都没有提升，主拒绝原因仍然是 `ETF_BETA_WEAK_STATE_INTER_REBALANCE_DEFENSE_REDEPLOY_REJECT_EXECUTION_CONSTRAINT`。这说明当前主问题已经收敛为执行约束过紧，而不是目标映射错误。

用户对下一轮的偏好也已经明确：
- `RISK_OFF` 不要空仓
- 只要有现金就补一点
- 接受更频繁的小额补仓
- 资产顺序偏好为“债优先，核心宽基次之”

## Goals / Non-Goals

**Goals:**
- 只在 `RISK_OFF` 下为 ETF 新增正式的 `cash-drip top-up` 执行能力。
- 让 ETF 在非再平衡日、存在可用现金时，可以按最小可执行单位做小额补仓，而不是要求先满足较大的 deploy gap。
- 明确补仓顺序：先补 `511010.SH`，再补 `510300.SH`。
- 输出可审计 explain，至少区分：已执行 drip top-up、现金不足最小单位、目标已满足、被硬约束阻断。
- 保持本轮改动单一可归因，优先观察 `RISK_OFF` 非零持仓率与弱势行为直觉是否改善。

**Non-Goals:**
- 不修改 `TRANS_DOWN`。
- 不修改弱势 target map。
- 不修改 stock、regime、组合 `50/50`。
- 不在本轮同时处理其他 execution constraint 或 affordability 路径。
- 不追求本轮先提升 `CAGR`，收益改进不是首要验收目标。

## Decisions

### 1. 只处理 `RISK_OFF`，不同时扩大到 `TRANS_DOWN`
- 选择：将 cash-drip top-up 限定在 `RISK_OFF`。
- 原因：用户最强诉求是“最弱环境也不要空仓”；先把最窄场景做实，避免再次引入双变量。
- 备选方案：同时覆盖 `TRANS_DOWN`。
- 不选原因：会把本轮从执行约束修复扩成弱势全状态行为重写，结果难归因。

### 2. 用“最小可执行单位 + 可用现金”替代“大 deploy gap 门槛”
- 选择：`RISK_OFF` 下只要有现金且满足最小 lot / 最小成交约束，就允许 drip top-up。
- 原因：用户要的是频繁、小额、持续累积；旧的大门槛机制天然偏向“不下单”。
- 备选方案：保留 deploy gap 门槛，只做更弱的 clip。
- 不选原因：大门槛仍会把弱势行为继续卡成接近空仓。

### 3. 先债后宽基，按缺口顺序补仓
- 选择：优先补 `511010.SH`，其次补 `510300.SH`。
- 原因：这与上一轮已经确定的弱势目标结构一致，也符合“债为主、少量核心 beta”的用户偏好。
- 备选方案：按 `70/30` 同比例同时补。
- 不选原因：在现金很小的场景下，同步分配会增加小单碎片和 lot 失败概率。

### 4. 本轮只改执行路径，不改目标与预算
- 选择：保持当前 `RISK_OFF = 511010 70% + 510300 30%`，总暴露不变。
- 原因：当前需要验证的是“现有目标能否落地”，不是再改目标本身。
- 备选方案：同时提升 `RISK_OFF` 总暴露或改权重。
- 不选原因：会再次破坏单改动归因。

### 5. explain 与原因码必须单列
- 选择：新增 `cash-drip top-up` 专属 activation/reject reason codes 与 formal/research explain 字段。
- 原因：如果本轮仍然只看到笼统的 `execution constraint`，下一轮无法继续收缩问题。
- 备选方案：沿用现有 reason code。
- 不选原因：可观测性不足，无法验证“是没现金、没 lot，还是已经满足目标”。

## Risks / Trade-offs

- [风险] 频繁小额补仓会抬高换手与交易成本
  - 缓解：本轮仅限 `RISK_OFF`，并坚持债优先、小额 clip，不扩大到 `TRANS_DOWN`。

- [风险] 小额补仓可能在很多天都只补债，导致宽基累积很慢
  - 缓解：这是刻意设计，优先保证“防守承接成立”，而不是追求更快恢复进攻暴露。

- [风险] 如果 cash-drip 仍然没有提升 `RISK_OFF` 非零持仓率，说明主阻塞不在 deploy gap，而在更底层的 affordability / lot 约束
  - 缓解：通过新增 reason codes，把失败进一步收敛到“现金不足最小单位”或“其他硬约束”，为下一轮继续收口。

- [风险] 回放指标可能几乎不变
  - 缓解：本轮首要验收指标不是收益，而是 `RISK_OFF` 仓位行为与 explain 的可解释改善。

## Migration Plan

1. 在 ETF execution path 中新增 `RISK_OFF cash-drip top-up` 分支。
2. 为 formal/research explain 增加 drip activation/reject 字段。
3. 先做 ETF standalone 回放，再做 `A_STOCK_ETF_V1` 组合复核。
4. 若 `RISK_OFF` 非零持仓率提升且无明显风险恶化，再考虑是否推广到 `TRANS_DOWN`。

回退路径：
- 直接回退 ETF execution path 与 explain 字段改动，恢复到当前“target 已修正、执行仍按旧 constraint 拒绝”的状态。

## Open Questions

- 本轮先不回答 `TRANS_DOWN` 是否也需要 cash-drip top-up。
- 本轮先不回答是否要放松更底层的 affordability 规则；只有在 `RISK_OFF` cash-drip 仍无效果时再进入下一轮。
