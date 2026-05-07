## Context

执行边界重构已经让正式主路径能输出 `subsystem_budgets / action_intents / risk_overrides / target_book / execution_audit`，但实现中仍并存旧合同对象和未完全退出的 planning helper。当前更像“合同主干立住了，但清残留还没做”。

## Goals / Non-Goals

**Goals:**
- 从共享执行边界中清除旧过渡合同的正式暴露地位。
- 明确 `candidate_plan`、旧 `ExecutionIntent` 只允许留在内部或 compat 映射层。
- 为后续 cleanup 实现提供小范围、可回退的清理顺序。

**Non-Goals:**
- 不改变研究逻辑、治理逻辑和执行行为。
- 不在本 change 中重新设计新的共享执行合同。
- 不在本 change 中做大范围 pipeline 重写。

## Decisions

- 决策 1：先清正式导出和边界定位，再清代码残留。
  原因：避免实现层先删代码，文档和规格还留旧入口。

- 决策 2：将 `candidate_plan` 与旧 `ExecutionIntent` 定位为内部/compat 结构。
  原因：当前正式共享边界已不是这些对象，继续并列暴露只会制造误导。

- 决策 3：清理批次必须绑定 golden 与回退说明。
  原因：这类清理很容易变成“看起来更干净”的机会性重构。

## Risks / Trade-offs

- [风险] 仍有隐式调用方依赖旧合同
  → 缓解：先在 specs 中保留 compat 条件，再在实现阶段逐一核销。

- [风险] `order_planning` 重复 helper 清理时误删仍在使用的逻辑
  → 缓解：把 helper 清理作为独立任务，并要求回归与回退说明。

## Migration Plan

1. 先在 specs 中收紧正式共享边界定义。
2. 再在实现阶段移除共享导出中的旧合同。
3. 最后清 `order_planning` 重复 helper 与未启用壳。

## Open Questions

- 仍需在实现阶段核对哪些内部测试或调试工具仍引用旧合同名称。
