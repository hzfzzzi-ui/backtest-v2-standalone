## Why

当前账户层主状态并不失控，但 `TRANS_UP / TRANS_DOWN` 过渡态存在明显抖动：短段过多、`A -> B -> A` 来回翻转偏频繁。这个问题会放大 transition 行为触发次数，降低研究归因质量，也会干扰后续共享账户执行 runtime 的行为研究。

## What Changes

- 在账户层状态切换合同中新增过渡态最短停留策略，只针对 `TRANS_UP / TRANS_DOWN`
- 账户层继续保留原始 `5-state` 诊断语义，但预算与执行消费抗抖后的有效账户状态
- 在主 runtime 中输出最短停留相关 explain，便于比较 raw state 与 effective state 的差异
- 增加最小对比试验，验证切换次数、短段数量、bounce 次数与主回放指标是否改善

## Capabilities

### New Capabilities
- `account-state-transition-hysteresis-policy`: 账户层过渡态最短停留与抗抖策略

### Modified Capabilities
- `account-layer-state-transition-policy`: 状态切换合同增加过渡态最短停留规则
- `account-budget-control`: 账户层预算控制消费抗抖后的有效状态
- `account-allocation-runtime-cutover`: 主 runtime 输出 raw/effective transition 解释与最短停留证据

## Impact

- `backend/core/services/account_allocator_shadow.py`
- `backend/core/services/cn_stock_etf_unified_runtime_service.py`
- `openspec/specs/account-layer-state-transition-policy`
- `openspec/specs/account-budget-control`
- `openspec/specs/account-allocation-runtime-cutover`
- 主回放与状态切换统计对比实验
