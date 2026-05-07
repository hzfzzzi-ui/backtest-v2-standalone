## Why

当前共享执行上游仍然把一部分子系统候选裁决逻辑放在 `order_planning` 里处理，包括子系统权重解析、市场状态权重覆写、子系统名额分配和基于这些规则的候选截断。这让执行内核继续半理解个股多信号组合语义，也让“子系统先形成最终候选，再交给执行内核下单”的正式边界没有真正落地。

在上一条模块边界收敛 change 已经确认 baseline 无漂移后，现在需要继续把这层上游候选与兼容裁决从 `order_planning` 中收出去，避免执行内核继续承担子系统级候选决策。

## What Changes

- 新增“上游候选边界合同”，在共享执行之前固定当日最终可进入订单规划的候选集合、子系统名额和兼容裁决摘要。
- 将 `order_planning` 中当前负责的子系统权重解析、市场状态权重覆写、子系统名额分配和候选截断迁移到上游候选边界层。
- 让 `order_planning` 只消费已经完成边界裁决的候选结果和统一目标持仓合同，不再直接读取 `signal_composition`、`same_symbol_policy`、`market_state_weight_overrides` 之类的子系统私有语义。
- 将与上游候选边界相关的诊断字段从执行规划阶段下沉到候选边界阶段，并同步正式审计/研究诊断的字段口径。
- **BREAKING**：共享执行上游的日内契约会新增候选边界 payload，`order_planning` 的 debug/diagnostics 口径将改为消费该 payload，而不是再自行重建子系统候选裁决。

## Capabilities

### New Capabilities

- `upstream-candidate-boundary-contracts`: 定义共享执行之前的候选边界合同、字段和最小诊断语义。

### Modified Capabilities

- `architecture-doc`: 当前正式架构需要把“候选边界层位于子系统与执行内核之间”的现实写成正式真相。
- `runtime-boundary-contracts`: 共享执行边界需要新增上游候选边界合同，并收紧 `order_planning` 的正式职责。
- `signal-provider-protocol`: 日级信号输出需要允许上游候选边界层消费必要的候选元信息，并与最终买入信号边界分层。
- `cn-stock-trend-alpha-core`: 个股子系统需要把多信号组合后的候选集合、兼容裁决和子系统名额裁决视为子系统上游边界，而不是执行内核职责。
- `backtest-research-audit`: 审计与诊断需要把候选边界裁决从执行规划诊断中拆出去，避免继续误归因为执行内核行为。

## Impact

- 影响代码主要集中在 `backend/core/stage_pipeline/adapters/`、`backend/core/engine_vector/`、`backend/core/portfolio/` 和 `backend/core/audit/`。
- 影响共享执行日内 payload、调试计划摘要、候选审计行和研究诊断口径，但不应改变正式 baseline 收益口径。
- 影响 `docs/02_系统架构设计/全系统架构设计.md` 与 `docs/01_系统接口模块定义/共享层/A股子系统接口模块定义.md` 的正式边界描述。
