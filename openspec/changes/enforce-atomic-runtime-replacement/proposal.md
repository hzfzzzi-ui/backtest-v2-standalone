## Why

B1 真实 AB 暴露出一个执行合同缺口：`ROTATION_REPLACE` 卖单会先进入订单集，但对应候选买单可能因为现金、数量或执行约束没有在同一 runtime pass 中生成，导致“卖出已发生、替换未完成”。

该问题会污染替换研究的 NAV/account 口径，也会让回撤改善和收益损失无法可靠归因。

## What Changes

- 为 runtime rotation replacement 增加原子替换合同。
- 只有当替换买单在同一执行规划 pass 中可生成时，才允许对应 `ROTATION_REPLACE` 卖单进入最终订单集。
- 如果替换买单不可执行，则对应卖单和买单必须同时取消，并记录可审计的取消原因。
- 保持默认行为不变：`rotation_replace_enabled=false` 时不影响正式基线。
- 不改变信号时点、成交时点、股票池、排序因子、退出规则或成本模型。

## Capabilities

### New Capabilities
- `atomic-runtime-replacement`: 约束 runtime rotation replacement 的卖买配对、取消和审计语义。

### Modified Capabilities
- 无。

## Impact

- 影响代码：
  - `backend/core/portfolio/execution_orders.py`
  - `backend/core/portfolio/portfolio_runtime.py`
  - 相关单元测试
- 影响行为：
  - 仅当研究配置启用 `sizing.rotation_replace_enabled` 时生效。
  - 计划中的 replacement pair 若买入不可执行，不再产生孤立卖单。
- 回退方式：
  - 关闭 `sizing.rotation_replace_enabled`，或回滚本 change 的执行内核改动。
