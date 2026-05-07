## Why

回测主引擎的正式共享执行边界已经切到 `subsystem_budget_v1 / action_intent_v1 / risk_override_v1 / execution_audit_v1`，但旧的 `ExecutionIntent / CandidatePlan / TargetBook` 过渡合同和 `order_planning` 中重复 helper 仍留在主路径里。只要这些残留壳继续暴露，就会持续污染“正式共享边界已经收口”的事实。

## What Changes

- 清理共享执行边界中仍暴露的旧过渡合同与重复 helper。
- 明确 `candidate_plan` 只允许作为子系统内部或迁移期结构存在，不再作为共享边界主合同。
- 收紧共享执行边界对外导出的正式对象，只保留正式合同与必要 compat 映射。
- 为 cleanup 批次补回退顺序与验证要求，避免借清理之名做大重构。

## Capabilities

### New Capabilities
- `execution-boundary-residual-cleanup`: 定义共享执行边界残留合同与 helper 的正式清理条件、范围和回退要求。

### Modified Capabilities
- `runtime-boundary-contracts`: 收紧正式共享边界对外可见合同集合。
- `candidate-plan-boundary-contracts`: 明确降级为内部/迁移结构。
- `dead-code-removal`: 约束执行边界残留清理必须以替代路径稳定为前提。

## Impact

- 影响模块：`backend/core/stage_pipeline/contracts.py`、`order_planning.py`、共享导出层、相关 golden 测试。
- 风险：过早删除 compat 结构会破坏尚未完成迁移的调用方。
