## Context

上一轮 `improve-etf-weak-state-defense-deployability` 已经把 ETF 弱势防守合同、防守资产优先级和 deployability floor 建起来了。最新验收显示：

- `RISK_OFF` 下已经有正式防守 targets
- `weak_state_defense_policy` 已激活
- `effective_max_positions` 和 `total_exposure_cap` 也不再被压成 `0`

但在非再平衡日，ETF sleeve 仍可能因为固定 `biweekly` 节奏停留在：

- `ETF_BETA_AWAIT_BIWEEKLY_REBALANCE`
- `NO_SELECTED_ORDERS`
- `selected_etfs = []`

这说明当前缺口不在预算或合同层，而在执行路径：弱势防守合同已经存在，但 inter-rebalance 路径没有把它当作正式可落地的 redeploy 信号。

约束条件：
- 这是 ETF 弱势执行路径补丁，不是新一轮弱势预算改造。
- 不修改 stock sleeve、regime、50/50 组合结构。
- 不重新定义 `weak_state_defense_policy` 的目标暴露和 defense seat floor。
- 不把 `BULL / TRANS_UP` 的再平衡节奏改成更高频。

## Goals / Non-Goals

**Goals:**
- 让 `TRANS_DOWN / RISK_OFF` 下已激活的正式弱势防守合同在非再平衡日可执行。
- 当当前持仓未满足正式 defense posture 时，允许 ETF sleeve 触发一次防守型补位/切换，而不是机械等待 biweekly rebalance。
- 输出专门的 activation / reject reason codes，能够区分“已满足防守持仓”“无 defense 候选”“被执行约束拒绝”。
- 保持当前弱势目标暴露、seat floor 与 explain 字段不变，只补执行链缺口。

**Non-Goals:**
- 不增加新的长期主配置字段。
- 不提高 `RISK_OFF / TRANS_DOWN` 的 target exposure。
- 不把普通宽基 beta 重新作为 risk-off 默认承接。
- 不改变 `BULL / TRANS_UP` 的固定再平衡节奏。
- 不处理 stock 腿弱势部署。

## Decisions

### Decision 1: 将本次 change 限定为执行路径补丁，而不是再次修改弱势预算合同
- 方案：沿用现有 `weak_state_defense_policy`、`target_exposure`、`target_selected_count`，只补 inter-rebalance 下的弱势 defense redeploy。
- 原因：上一轮回放已经证明合同和 budget 方向是对的，当前失败点是 execution path。
- 备选方案：继续修改弱势预算或 defense asset weights。
- 不采用原因：会把“执行缺口”伪装成“预算优化”，结果失去归因。

### Decision 2: 触发条件必须严格绑定“弱势合同已激活且当前防守姿态未满足”
- 方案：只有在以下条件同时成立时，才允许 inter-rebalance defense redeploy：
  - `effective_state_5 in {TRANS_DOWN, RISK_OFF}`
  - `weak_state_defense_policy_active = true`
  - `target_exposure > 0`
  - 存在可交易 defense candidates
  - 当前 live seats 为空，或当前 live seats 不属于 formal defense posture
- 原因：这能把额外交易限制在真正需要的弱势防守切换上，避免把 ETF sleeve 变成高频调仓。
- 备选方案：只要弱势状态就允许非再平衡调仓。
- 不采用原因：会显著抬高 turnover，破坏当前低频 sleeve 定位。

### Decision 3: Inter-rebalance defense redeploy 只允许切到 formal defense posture
- 方案：redeploy 的目标集合只允许来自正式弱势防守合同输出的 targets，不允许临时走进攻 ranking。
- 原因：这次 change 不是“弱势时加快 ETF 轮动”，而是“弱势时把防守合同真正落地”。
- 备选方案：允许 inter-rebalance 继续沿用正常 selection chain。
- 不采用原因：会把非再平衡日执行扩张成广义再平衡，边界失控。

### Decision 4: Explain 面必须新增 activation 与 reject 级原因码
- 方案：新增一组 inter-rebalance weak-state reason codes，例如：
  - `ETF_BETA_WEAK_STATE_INTER_REBALANCE_DEFENSE_REDEPLOY_ACTIVE`
  - `ETF_BETA_WEAK_STATE_INTER_REBALANCE_DEFENSE_REDEPLOY_REJECT_ALREADY_DEFENSIVE`
  - `ETF_BETA_WEAK_STATE_INTER_REBALANCE_DEFENSE_REDEPLOY_REJECT_NO_DEFENSE_SELECTION`
  - `ETF_BETA_WEAK_STATE_INTER_REBALANCE_DEFENSE_REDEPLOY_REJECT_EXECUTION_CONSTRAINT`
- 原因：如果只看到最终是否下单，仍无法区分“无需 redeploy”和“该 redeploy 但失败”。
- 备选方案：继续复用现有 `AWAIT_BIWEEKLY_REBALANCE` 与 `NO_SELECTED_ORDERS`。
- 不采用原因：语义太粗，无法支持后续研究。

## Risks / Trade-offs

- [风险] 弱势中增加非再平衡日 redeploy 会抬高 ETF turnover。
  - 缓解：仅在 defense posture 未满足时触发，不对已满足防守持仓重复交易。

- [风险] 若激活条件过宽，可能把 `TRANS_DOWN` 变成准高频调仓状态。
  - 缓解：要求 formal weak-state policy 已激活，并以当前 live seats 是否已满足防守姿态作为二次门槛。

- [风险] 若 inter-rebalance 路径错误复用普通 ranking，会把本次 change 演化成新的主逻辑修改。
  - 缓解：限定 redeploy 目标仅来源于 formal defense targets。

- [风险] 若 explain 字段不细，回放后仍无法判断是“不该 redeploy”还是“redeploy 失败”。
  - 缓解：本次必须同时补 activation/reject 原因码。

## Migration Plan

1. 在 ETF execution path 中增加 weak-state inter-rebalance defense redeploy 判定与专用 reason codes。
2. 保持现有 `weak_state_defense_policy` 配置与 budget semantics 不变，只补执行入口。
3. 先用 ETF standalone 回放观察：
   - 非再平衡日是否从 `AWAIT_BIWEEKLY_REBALANCE + NO_SELECTED_ORDERS` 变成防守 redeploy 可落地
4. 再用 `A_STOCK_ETF_V1` 复核组合层：
   - 重点看 Sharpe/Calmar/MaxDD 与弱势 explain，不把 CAGR 作为唯一指标
5. 如果 turnover 抬升明显且风险指标不改善，则回退该执行路径补丁。

## Open Questions

- `TRANS_DOWN` 下如果 `allow_core_beta = true`，是否允许“core beta 已满足 posture”直接拒绝 redeploy，还是仍应优先切到 defense-only posture。
- 当当前持仓是旧的 core beta live seat 且弱势 defense targets 已出现时，是否允许在非再平衡日直接卖出切换，还是只允许新增 defense buy。
- inter-rebalance defense redeploy 是否需要单独的最小持有/冷却约束，避免弱势状态边缘来回切换。
