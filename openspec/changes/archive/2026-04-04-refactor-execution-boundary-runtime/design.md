## Context

文档层已经完成了执行边界收口：

- `combo` 不再是独立正式模块
- 子系统跨共享执行边界正式输出是 `action_intent_v1`
- Governor 的高权限干预通过 `risk_override_v1`
- `execution_kernel` 是统一成交器，输出 `target_book_v1 + execution_audit`

但当前实现层仍残留多个旧壳：

- `candidate_plan` 和过渡 `target_book` 仍被大量视作执行前主合同
- Governor 与执行层之间缺少明确的 `risk_override_v1` 应用面
- 行动清单、持仓所有权和阻断审计的正式语义仍有实现漂移风险

这次 change 是 L3 边界收口：不改变研究逻辑、不改变信号和成交时点，只改变跨模块正式合同与迁移顺序。

## Goals / Non-Goals

**Goals**

- 固定正式执行边界合同
- 定义过渡壳与正式合同的分界
- 为后续实现提供 golden 回归面

**Non-Goals**

- 不在本次 change 中改变 `baseline_V10.1` 研究口径
- 不在本次 change 中引入新的研究信号
- 不在本次 change 中重写事务域或前端

## Decisions

### 1. `action_intent_v1` 是唯一正式普通动作合同

子系统跨共享执行边界的普通动作正式上只允许 `action_intent_v1`：

- `BUY`: `suggested_size_unit=weight`，`suggested_size_basis=subsystem_budget_relative`
- `SELL`: `suggested_size_unit=ratio`，`suggested_size_basis=sellable_qty_relative`
- `priority=1` 表示同一子系统内最高优先级

### 2. `risk_override_v1` 是 Governor 独立高权限合同

Governor 的高权限干预不混入普通动作，而是通过独立 `risk_override_v1` 下发：

- `portfolio REDUCE_ONLY`
- `portfolio FORCE_EXIT`
- `symbol FORCE_EXIT`

### 3. 过渡 `candidate_plan / target_book` 仅作为内部或迁移结构存在

这些结构可以在子系统内部或迁移期存在，但不再被定义为共享执行边界主合同。

### 4. `execution_audit` 必须覆盖阻断、覆盖、截断、整手取整

执行层任何阻断、覆盖、截断、整手取整，都必须进入 `execution_audit`，不能静默消失。

## Risks / Trade-offs

- 如果迁移顺序不清，容易出现“新旧合同同时生效”
- `SOURCE_ONLY` 和强平语义收紧后，需要避免把事务域生命周期状态一起扰动
- goldens 覆盖不足时，后续实现容易误伤执行口径

## Migration Plan

1. 先固定正式合同和 goldens
2. 再把 Governor 和持仓所有权语义收紧
3. 然后逐模块把旧过渡壳从共享边界主路径移开
4. 最后再删 compat

## Rollback

- 保留过渡结构但降级其语义
- 如迁移中发现口径漂移，可暂时回退为旧兼容主路径 + 新合同旁路审计
