## Why

当前手机端半自动链路的“当前持仓”和买卖建议仍然建立在最新实验产物之上：`positions` 由实验 `portfolio_trades.csv` 重建，`guidance` 来自 `execution preview` 的目标持仓差集。这一口径在“只读看板”阶段可用，但一旦进入模拟盘协同，就会与真实持仓脱节，导致手机端展示和人工下单依据不可靠。

下一步逐步对接模拟盘时，系统必须先固化“真实持仓同步 -> 以真实持仓为起点重算正式策略 -> 手机端刷新待确认动作 -> 人工确认后再通过持仓同步刷新当前持仓”的闭环。否则，手机端看到的买卖单、价位和股数都只是实验视角，不是模拟盘视角。

## What Changes

- 新增模拟盘最新持仓同步能力，定义标准持仓快照、更新时间、来源、失败状态与审计记录。
- 新增持仓感知的日重算流程：使用正式 baseline 配置、最新市场数据和最新持仓快照，生成当日待确认 action sheet。
- 新增手机端动作单刷新模型，展示当前持仓、建议买入/卖出、参考价、建议股数/目标权重、差异原因和数据新鲜度。
- 新增“确认不等于持仓已更新”的运行边界：手机端确认只生成待执行动作，当前持仓只能由下一次持仓同步或执行回写刷新。
- 新增持仓漂移、数据过期、未同步和动作单过时等风险提示与降级状态，避免手机端把旧动作单当成真实可执行状态。
- 修改移动端主输出契约，使其优先消费 position-aware reconcile 结果，而不是继续单独依赖 `execution preview + experiment trades`。

## Capabilities

### New Capabilities
- `sim-account-holdings-sync`: 统一接收模拟盘最新持仓快照，输出标准化持仓、freshness、来源和审计状态。
- `position-aware-reconcile-run`: 以最新持仓快照作为运行输入，重跑正式策略并生成待确认买卖动作单与诊断结果。
- `mobile-trade-sheet-refresh`: 手机端刷新“当前持仓 + 待确认动作 + 待执行状态”三类信息，并显式展示同步时间与过期风险。

### Modified Capabilities
- `runtime-boundary-contracts`: 移动端半自动链路需要新增持仓感知的 reconcile surface 与 freshness 契约，不能继续只依赖 position-blind 的 execution preview。

## Impact

- 后端需要新增模拟盘持仓同步、标准化、重算编排和动作单聚合服务。
- `backend/api/mobile` 需要扩展新的刷新/同步/状态字段，手机端前端需要从“实验差集看板”切到“真实持仓驱动动作单”。
- 运行产物需要新增持仓快照、重算结果和审计对象，并与现有 `mobile_ops` / `ops` 目录边界清晰分离。
- 测试需要覆盖持仓未同步、持仓漂移、动作单过时、确认后未成交、重新同步后持仓刷新等关键场景。
