## Why

上一条变更已经把候选边界和候选规划前移成 `candidate_boundary_v1` 与 `candidate_plan_v1`，并验证 `baseline_V10.1` 无漂移。但当前 `order_planning` 仍然保留两类越界职责：一是缺失上游产物时会回退重建候选边界与候选规划，二是仍通过旧的兼容式 `build_rebalance_orders()` 间接消费候选规划参数。  
这使执行内核还没有真正收敛成“只做执行”的纯共享壳，也继续让个股子系统的候选规划语义泄漏到共享执行层。

## What Changes

- 收敛 `order_planning`，要求其只消费上游已经准备好的 `candidate_plan_v1` 与执行级必要参数，不再回退构建候选边界或候选规划。
- 新增纯执行级下单辅助路径，把“候选规划/轮换替换/现金感知搜索”的解释职责从 `build_rebalance_orders()` 调用链中剥离。
- 保留旧的 `build_rebalance_orders()` 作为兼容入口，避免影响未迁移的非 stage 调用方。
- 同步正式审计与架构文档，使“候选边界 -> 候选规划 -> 纯执行内核 -> 统一目标持仓”链路可审计、可追踪。

## Capabilities

### New Capabilities
- `<none>`: 无

### Modified Capabilities
- `runtime-boundary-contracts`: `order_planning` 必须只消费候选规划结果与统一目标持仓，不再自行解释候选规划兼容参数。
- `backtest-research-audit`: 审计必须明确区分候选边界层、候选规划层和纯执行内核层的拒绝来源。
- `architecture-doc`: 架构文档必须把 `order_planning` 明确锚定为纯执行内核，而不是候选规划兼容层。

## Impact

- 影响代码主要集中在 [order_planning.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/stage_pipeline/adapters/order_planning.py)、[portfolio_runtime.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/portfolio/portfolio_runtime.py)、候选规划适配器和正式审计链路。
- 不改变 `baseline_V10.1` 的策略口径、市场状态、风险预算、资产池和执行时点。
- 需要补充单元回归，并在容器内重跑 `baseline_V10.1` 确认关键绩效与预热起点无漂移。
