## Context

`docs/04_重构思路` 已明确：账户层必须先于 sleeve 层定义预算与状态切换，执行层只消费账户层输出。当前仓库已经完成三件事：

1. `runtime_truth_source = account_allocator`
2. 账户层 steady-state budget 已进入主 runtime
3. 账户层统一 state transition policy 已进入 `run_meta / audit / surface / frontend`

但真正的执行链仍存在结构性断层：账户层 transition contract 已经定义了 `carry / de-risk / cash release / budget handoff`，而 ETF 与组合执行链仍主要沿用旧的 weak-state patch、cash-drip、redeploy、candidate plan gating 与 slot/cash affordance 语义。结果是：上层 runtime 已讲账户层语言，下层执行链还在消费旧局部语义，双重语义仍然存在于行为层。

这条 change 的目标不是再加新的单状态 patch，而是让执行层开始正式消费账户层 transition contract，并把旧局部弱势执行语义降级成 diagnostics/reference。

## Goals / Non-Goals

**Goals:**
- 建立执行层消费账户层 transition contract 的正式入口。
- 定义统一的 transition action handoff 结构，使执行层能显式消费 `carry / de-risk / cash release / budget handoff`。
- 让 ETF 执行路径优先服从账户层 transition runtime，而不是继续以旧 weak-state patch 为主语义。
- 让 query / audit / frontend 能区分“账户层 transition 已消费”与“仅存在旧局部弱势 reject”。
- 将主验证重点放在行为归因是否切换到账户层，而不是立即追求收益优化。

**Non-Goals:**
- 本 change 不重写 stock alpha 内核。
- 本 change 不修改主 regime 定义或总暴露曲线。
- 本 change 不要求一次性完成所有 transition family 的完整执行实现；第一轮只要求统一执行入口与 `risk_on -> defensive` 优先消费路径成立。
- 本 change 不把 `combo/reference` 删除；reference 仍可保留用于历史对照，但不得重新获得主执行解释权。

## Decisions

### 1. 先统一 transition handoff，再逐类完善执行
- 决策：账户层先输出统一 `transition_action_handoff`，执行层消费同一结构；实现优先级先覆盖 `risk_on -> defensive`，其余 transition 先显式 `no_op` 或 `carry_forward`。
- 原因：这样可以保持合同单一真相，同时避免再次回到单状态 patch。
- 备选方案：只实现 `RISK_OFF` 局部 materialization。
- 放弃原因：仍会保留双重语义，并继续让其他状态切换落回旧执行链。

### 2. 执行层消费账户层动作，而不是反推账户层动作
- 决策：`account_allocator_runtime.state_transition_runtime` 成为执行层主输入，ETF/组合执行层只报告消费结果、拒绝原因与剩余缺口。
- 原因：账户层既然已经是 runtime 主真相，就不能再由 ETF 局部执行链决定何谓真实 transition。
- 备选方案：保留旧 weak-state policy 为主输入，再把账户层 transition 作为 explain。
- 放弃原因：这会让“账户层真相”继续停留在展示层。

### 3. 旧 weak-state 执行逻辑降级为 reference diagnostics
- 决策：保留 weak-state redeploy / cash-drip / materialization 等旧路径的原因码与参考字段，但它们只能作为 diagnostics，不得优先于账户层 transition handoff。
- 原因：历史可观测性仍有价值，但不能继续承接主执行语义。
- 备选方案：彻底删除旧路径。
- 放弃原因：会损失问题定位能力，也会让回放对比失真。

### 4. 先关注执行消费的“是否接通”，再关注收益优化
- 决策：验收优先级是：
  1. 账户层 transition 是否进入执行链
  2. reject 原因是否收敛到账户层 execution consumption
  3. `RISK_OFF` / `risk_on -> defensive` 行为是否开始变化
  4. 最后才看 `MaxDD / Calmar / CAGR`
- 原因：当前最主要的问题是双重语义，不是收益上限。

## Risks / Trade-offs

- [风险] 统一 handoff 后，执行层会同时存在新 transition input 与旧局部 diagnostics，容易产生迁移期复杂度。 → [缓解] 明确字段分层：`transition_action_handoff` 为主输入，旧 weak-state 字段全部标记为 diagnostics/reference。
- [风险] 第一轮只优先实现 `risk_on -> defensive`，其余 transition 仍是保守路径。 → [缓解] 在合同层一次定义全 transition family，在运行时显式标注哪些已消费、哪些仍是 `carry_forward/no_op`。
- [风险] 行为开始变化后，指标可能偏移。 → [缓解] 先用 ETF standalone 与 `A_STOCK_ETF_V1` 做双回放，优先判断行为归因是否切到账户层，而不是立即按收益好坏判定成败。
- [风险] query / frontend 若仍平铺展示旧 combo diagnostics，会重新制造双真相。 → [缓解] 当 `runtime_truth_source = account_allocator` 时，主面板只显示账户层 transition 消费状态，旧局部路径只能进入 diagnostics 区。

## Migration Plan

1. 在账户层 runtime 中新增统一 `transition_action_handoff` 结构，并让其对所有 transition family 都有明确输出。
2. 在 ETF 执行入口、candidate plan、day controls、accounting 中接入 handoff 消费结果与拒绝原因。
3. 在 query / audit / frontend 中将“已消费账户层 transition”提升为主叙事，把旧 weak-state 路径降级为 diagnostics。
4. 先对 ETF standalone 与 `A_STOCK_ETF_V1` 做行为级回放，再决定是否继续扩到其他 sleeve。
5. 如需回退，移除 handoff consumption 分支并恢复旧 weak-state 优先执行路径。

## Open Questions

- `defensive -> defensive` 与 `defensive -> recovery` 在第一轮是否只保留 `carry_forward`，还是要同步给出最小 de-risk / re-risk 消费动作。
- stock sleeve 是否在后续阶段也要消费同一套 transition handoff，还是先保持 ETF 优先试点。
