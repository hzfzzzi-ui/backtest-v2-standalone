## Why

当前主线已经把执行链收敛到 `candidate_boundary_v1 -> candidate_plan_v1 -> target_book_v1`，并验证 `baseline_V10.1` 无漂移；但仍有两个 P1 级别的历史真相没有收掉：

1. `candidate_plan.py`、`execution_orders.py`、`portfolio_runtime.py::build_rebalance_orders()` 仍各自维护一份 sizing / 下单算法。
2. 正式审计仍保留 `sleeve_budget` 旧别名，把已经废弃的候选边界语义继续暴露到正式产物里。

这两处会继续制造重复真相和口径漂移风险，不符合当前“执行内核只认统一合同”的正式架构。

## What Changes

- 新增共享 sizing 真相，收敛 direct target、风险预算、反波动率和等权 sizing 的正式计算路径。
- 把 `build_rebalance_orders()` 改成薄编排层，改为复用 `candidate_plan -> execution_orders`，不再保留第二套独立 sizing 实现。
- 从正式审计中删除 `sleeve_budget` 旧别名，只保留 `candidate_boundary / candidate_plan / execution_kernel` 三层正式摘要。
- 同步更新相关文档和测试，并重跑 `baseline_V10.1` 确认无漂移。

## Capabilities

### Modified Capabilities
- `runtime-boundary-contracts`
- `backtest-research-audit`
- `architecture-doc`

## Impact

- 影响代码主要集中在 `backend/core/portfolio`、`backend/core/stage_pipeline/adapters/daily_accounting.py` 和相关单测。
- 不改变 baseline 主策略逻辑、状态定义、执行时点和风险预算口径。
- 需要通过定向回归和 `baseline_V10.1` 对账证明这次收敛只消除历史兼容真相，不引入行为漂移。
