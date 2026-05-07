## Context

当前账户层已经完成 steady-state budget、state transition policy、audit/query/front-end 主叙事切换，但 transition execution 的真实 owner 仍然停留在旧 ETF 单腿执行链。过去几轮 change 已反复证明：只在 ETF 局部路径上叠加 `state_edge_cash_release`、`cash_drip_topup`、`materialization` 或 handoff 适配，无法真正切断旧 owner，只会形成“账户层语义已成立，执行层仍由旧路径主导”的双重语义。

当前约束有三条：
1. `runtime_truth_source = account_allocator` 已是正式主线，不能再回退为 combo/ETF 并列真相。
2. 执行 owner 切换必须可审计、可回滚，不能靠隐式优先级覆盖。
3. 旧 ETF weak-state 路径仍有研究价值，但只能保留为 diagnostics/reference，不能继续输出主执行结论。

## Goals / Non-Goals

**Goals:**
- 建立共享账户执行 runtime，使账户层 `state_transition_runtime + transition_action_handoff` 成为 transition execution 的唯一 owner。
- 让执行层直接消费账户层 handoff，输出统一的 transition execution plan、owner、reason code、reject reason。
- 将旧 ETF weak-state 路径降级为 diagnostics/reference，禁止再以主执行结论身份进入 runtime/audit/query/front-end。
- 第一优先打通 `risk_on -> defensive` 族，但合同范围一次覆盖全部 transition family，避免再次产生单状态语义。
- 保持当前主回放指标可归因；如果出现漂移，必须能明确归因到共享账户执行 owner 切换，而不是局部 patch。

**Non-Goals:**
- 不在本 change 中重写 `stock alpha`、主 regime、总暴露预算或 `TRANS_DOWN` 专属研究策略。
- 不把独立 ETF sleeve 直接删除；它仍保留为研究/参考执行器。
- 不在前端重新计算任何研究逻辑；前端只消费新的单真相产物。

## Decisions

### Decision 1: 共享账户执行 runtime 成为 transition execution 唯一 owner
- 选择：在账户层之上新增共享执行 owner，由它把 `carry / de-risk / cash release / budget handoff` 统一编译成 transition execution plan。
- 原因：当前问题不是字段没接上，而是执行主控权仍在旧 ETF 路径里。只有把 owner 上收到共享执行 runtime，才能切断“新合同驱动旧执行器”的结构性矛盾。
- 备选：继续在 ETF 路径上适配 handoff。已被多轮 no-go 证明无效，因为账户层合同发生在组件回放之后，无法反向接管执行。

### Decision 2: 合同范围一次覆盖全部 transition family，实现优先级单独控制
- 选择：统一定义 `risk_on -> risk_on`、`risk_on -> defensive`、`defensive -> defensive`、`defensive -> recovery` 四类 family 的共享执行合同。
- 原因：如果合同层只写 `RISK_OFF` 或单 family，会再次制造双语义；正确做法是合同全覆盖、实现可分阶段。
- 备选：先只定义 `RISK_OFF`。已明确放弃，因为会让其他状态继续沿用旧语义。

### Decision 3: 旧 weak-state 路径只保留 diagnostics/reference
- 选择：`state_edge_cash_release`、`riskoff_cash_drip_topup`、`riskoff_account_budget_materialization`、`weak_state_inter_rebalance_defense_redeploy` 只能作为 diagnostics/reference 输出。
- 原因：这些路径仍有排障价值，但不能继续与账户层共享执行 owner 并列为主结论。
- 备选：保留双路径并列，再靠优先级字段区分。拒绝，因其会持续污染 audit/query/front-end 主叙事。

### Decision 4: query / audit / front-end 只展示账户层主执行结论
- 选择：当 `runtime_truth_source = account_allocator` 时，主 explain 仅展示共享账户执行 runtime 的 owner/status/reason/reject；旧 ETF 局部路径只进入 diagnostics/reference 区。
- 原因：单真相不只是 runtime 字段要求，也必须体现在查询与展示层。
- 备选：保留 combo/ETF 平铺叙事。拒绝，因为这会让用户继续看到两套同级执行语义。

## Risks / Trade-offs

- [Risk] 共享执行 owner 切换可能带来行为级漂移 → Mitigation：以 `A_STOCK_ETF_V1` 主回放和 ETF standalone 双回放对比，要求差异必须可归因。
- [Risk] 旧 ETF 路径降级后，历史调试脚本可能依赖原有主 reason code → Mitigation：保留 diagnostics/reference 输出，不直接删除旧字段。
- [Risk] 共享执行 runtime 新增后，query/front-end 若仍偷读旧路径，会重新出现双语义 → Mitigation：同步修改 audit/query/front-end，只允许主面板读取账户层 owner。
- [Risk] 合同覆盖全部 family，但首轮只实现 `risk_on -> defensive`，其余 family 容易被误解为已落地 → Mitigation：在 runtime 中显式标明 family implementation status，并在 tasks/验收里区分 contract-ready 与 execution-ready。

## Migration Plan

1. 新增共享账户执行 runtime 合同与 plan 结构，先把 owner、status、reason、reject 统一编译到账户层。
2. 让执行层优先消费共享账户执行 runtime；当 owner 存在时，旧 ETF weak-state 路径只回写 diagnostics/reference。
3. 同步 audit/query/front-end，使账户层共享执行结论成为唯一主叙事。
4. 使用 ETF standalone 与 `A_STOCK_ETF_V1` 主回放验证：
   - 新 owner 字段是否成为主执行结论；
   - 旧 reason code 是否只留在 diagnostics/reference；
   - 指标是否保持可归因。
5. 如验证失败，回退共享执行 owner 接管点，保留旧 diagnostics 输出。

## Open Questions

- 首轮 `risk_on -> defensive` 的共享执行 plan 是否需要直接生成统一 sell-first / buy-second 阶段计划，还是先只生成 sell-side ownership 切换。
- 独立 ETF sleeve 在长期架构中是保留为研究执行器，还是未来继续下沉为共享账户执行 runtime 的资产适配器。
- `defensive -> recovery` 是否应在后续单独研究 change 中引入更积极的 core beta 恢复节奏。
