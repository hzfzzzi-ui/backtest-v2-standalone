## Context

当前账户层已经完成三件事：稳态 budget 真相、统一 state transition contract、以及 query/audit/front-end 主叙事收口。但真实执行仍由旧的 ETF weak-state 路径主导，导致 `transition_action_handoff` 进入了 `run_meta`，却没有成为实际执行 owner。最近几轮 `state_edge_cash_release`、`riskoff_cash_drip_topup`、`riskoff_account_budget_materialization`、`consume-account-layer-transition-contract-in-execution` 已经证明：在旧执行器上继续叠加 handoff 适配，只会制造“新合同成立、旧 reject 继续主导”的双重语义。

这次改动的目标不是再接入一个入口，而是完成一次明确的 ownership cutover：当 `runtime_truth_source = account_allocator` 且存在 `transition_action_handoff` 时，执行层必须先消费账户层 handoff，旧 weak-state 路径只能保留为 diagnostics/reference。

## Goals / Non-Goals

**Goals:**
- 建立统一的 `transition_execution_owner` 合同，明确账户层 handoff 是主执行 owner。
- 让 ETF 执行入口、day controls、candidate plan、accounting 统一消费账户层 `carry / de-risk / cash release / budget handoff`。
- 将旧 weak-state 路径降级为 diagnostics/reference，不再产出主 reason code、主执行状态或主拒绝结论。
- 让 `run_meta / audit / combo_truth / front-end` 只保留一套主叙事：账户层 transition execution。
- 第一优先实现 `risk_on -> defensive`，但合同范围必须覆盖全部 transition family，未实现部分也必须由账户层明确标记为 `reference_only` 或 `not_implemented`。

**Non-Goals:**
- 不重写 `stock alpha` 逻辑。
- 不改 `TRANS_DOWN`、`RISK_OFF` 的稳态目标预算数值。
- 不引入新的收益优化或新的执行 alpha。
- 不删除旧 weak-state 路径的全部代码；它们仍保留为 diagnostics/reference，直到后续确认可以物理移除。

## Decisions

### 决策 1：执行 owner 硬切换，而不是继续适配旧 ETF 执行器
- 方案：新增账户层 transition execution controller 语义，要求当 handoff 存在时，执行链只能从账户层 handoff 进入。
- 原因：旧路径已经反复证明会抢占主 reject 和主状态，继续并列只会保留双重语义。
- 替代方案：
  - 继续在旧 ETF 执行器上补 handoff 入口：已验证失败，不能解决 ownership 问题。
  - 直接删除旧路径：风险过高，会丢掉定位证据。

### 决策 2：合同一次定义全 transition family，实现先落 `risk_on -> defensive`
- 方案：`transition_action_handoff` 与 `transition_execution_owner` 合同覆盖四类 family：
  - `risk_on_to_risk_on`
  - `risk_on_to_defensive`
  - `defensive_to_defensive`
  - `defensive_to_recovery`
- 实现优先级先落 `risk_on_to_defensive`，其余 family 明确输出 `reference_only` 或 `not_implemented`。
- 原因：这样才能避免只改单状态而继续保留双语义。

### 决策 3：旧 weak-state 路径只能进入 diagnostics/reference 区
- 方案：保留以下路径，但统一降级为 diagnostics/reference：
  - `state_edge_cash_release`
  - `riskoff_cash_drip_topup`
  - `riskoff_account_budget_materialization`
  - `weak_state_inter_rebalance_defense_redeploy`
- 原因：它们仍有定位价值，但不再有资格产出主执行结论。
- 替代方案：
  - 全部删除：会降低排障能力。
  - 继续平铺展示：会继续制造双真相。

### 决策 4：主产物必须显式区分 `owned / rejected / reference_only / not_implemented`
- 方案：在账户层 execution consumption 上新增正式状态字段：
  - `transition_execution_owner`
  - `transition_execution_status`
  - `transition_execution_reason_code`
  - `transition_execution_reject_reason`
  - `transition_execution_reference_paths`
- 原因：不把状态枚举做清楚，后续研究会再次陷入“到底是谁主导”的归因混乱。

## Risks / Trade-offs

- [风险] 硬切换 owner 后，短期内可能暴露更多未实现 transition family。  
  → Mitigation：合同上一次定义全 family，但实现状态明确标记为 `reference_only` 或 `not_implemented`，不伪装成功。

- [风险] 旧 weak-state 路径降级后，当前行为可能出现新的 reject 分布。  
  → Mitigation：保留 diagnostics/reference 字段，要求旧 reason code 仍可在参考区观察。

- [风险] query/front-end 若仍平铺 combo/weak-state 文本，会再次制造双真相。  
  → Mitigation：主面板只允许账户层 execution 叙事，reference 区单独显示旧诊断。

- [风险] 第一轮只落 `risk_on -> defensive`，可能让人误以为其他 family 已实现。  
  → Mitigation：在 runtime、audit、front-end 中显式输出 `implemented_for_execution` 与 `reference_only`。

- [风险] 这次是行为级 change，指标可能漂移。  
  → Mitigation：以可归因性为首要验收标准，同时保留主回放对比与最小正式回归。
