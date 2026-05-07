## Context

formal ETF Phase 1 当前已经恢复了预算和交易，但 Governor 预算标签仍然把 ETF sleeve 的 slot-cap 压缩统称为 `BREADTH_CAP_ACTIVE`。这会让正式实验和 rootcause 摘要把“真实 breadth 开关”与“ETF 本地 slot cap”混为一谈，后续任何关于 zero-day 的讨论都会继续失真。

这次变更只修 Governor 标签合同和最小诊断字段，不动策略口径，不重做状态预算，也不调整 `TRANS_DOWN/RISK_OFF` 的数值行为。

## Goals / Non-Goals

**Goals:**
- 让 Governor 预算标签只在真实 breadth 压缩时输出 `BREADTH_CAP_ACTIVE`。
- 为 ETF sleeve 输出独立、可审计的 slot-cap 生效标签。
- 在不改变预算数值的前提下，让 diagnostics 和 rootcause 摘要能正确归因。

**Non-Goals:**
- 不修改 `_STATE_SLOT_CAPS`、`requested_budget`、`target_exposure` 或 Governor 数值逻辑。
- 不改变 formal ETF Phase 1 的调仓频率、资产池、fallback 和 bucket 配置。
- 不把这次变更扩展为新的策略优化实验。

## Decisions

### 决策 1：保留现有预算数值，只修标签来源
`effective_max_positions`、`total_exposure_cap`、`slot_cap` 和 `requested_budget` 保持原行为。变更只限于标签和字段，不引入策略行为漂移。

原因：
- 用户这轮要先修合同，不是先改口径。
- 这样可以把诊断准确性和策略决策拆开验证。

### 决策 2：Governor 显式区分 breadth cap 与 ETF sleeve slot cap
在 Governor 快照中新增最小字段来表达：
- breadth 是否真实生效
- sleeve slot cap 是否真实生效
- sleeve slot cap 的来源文本

同时：
- 只有真实 breadth 压缩时才追加 `BREADTH_CAP_ACTIVE`
- `cn_etf` 下若 sleeve slot cap 生效，则追加 `ETF_BETA_SLOT_CAP_ACTIVE`

原因：
- 当前 `breadth_max_positions` 被 ETF slot cap 复用，必须拆开，否则 reason code 永远误报。

### 决策 3：slot-cap 来源优先复用 provider 现有 source 数组
不重新推断 slot-cap 来源，直接复用 ETF provider 已有的 `target_selected_count_source` 数组，作为 Governor 和 diagnostics 的来源字段。

原因：
- 避免再造一套“猜来源”的合同。
- 能与现有 `state_slot_cap_fallback`、`phase1_targets` 等语义对齐。

## Risks / Trade-offs

- [风险] 新增 reason code 可能影响既有诊断计数。  
  通过同步更新 zero-trade diagnostics 和测试，确保旧的误标签不再被当作 breadth 根因。
- [风险] 旧实验产物仍保留历史 `BREADTH_CAP_ACTIVE`。  
  这是预期；新合同只约束重跑后的新产物。
- [风险] 未来非 ETF sleeve 也可能需要类似标签。  
  这次先限定在 `cn_etf`，避免把范围扩大成通用重构。
