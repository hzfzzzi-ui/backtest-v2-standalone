## Context

上一条 `converge-a-share-system-module-boundaries` 已经把正式执行 sizing 收敛到统一目标持仓合同，也确认了 baseline_V10.1 在容器重跑后与正式锚点完全一致，没有漂移。当前剩余的主要越界点集中在 `order_planning` 的上游候选处理：

- `order_planning` 直接解析 `signal_composition.modules`
- `order_planning` 直接读取 `market_state_weight_overrides`
- `order_planning` 在共享层按子系统做名额分配和候选截断
- `order_planning` 仍然输出这些子系统裁决的 debug/diagnostics

这使得共享执行上游仍然承担了本应属于个股多信号组合边界的职责。ETF 当前不依赖这套逻辑，因此这轮 change 的主要行为面集中在 A 股个股多信号路径，但收敛目标仍然是共享主链边界。

## Goals / Non-Goals

**Goals:**

- 在 `order_planning` 之前建立正式的上游候选边界层，并定义稳定的 `candidate_boundary_v1` 合同。
- 将子系统权重解析、市场状态权重覆写、子系统名额分配、候选截断和对应诊断从 `order_planning` 中移出。
- 保持 `order_planning` 只负责基于已确认候选生成订单、构建统一目标持仓单和记录执行级 debug。
- 让正式审计和研究诊断能够明确区分“候选边界裁决”与“执行内核行为”。
- 在不改变 baseline 正式口径的前提下完成边界收敛。

**Non-Goals:**

- 不修改个股策略的排序、过滤、退出口径。
- 不修改 ETF 子系统的正式策略语义。
- 不修改 `candidate_plan_mode` 的现金感知搜索、轮换替换等执行级 sizing 行为。
- 不调整总控预算、市场状态定义或正式 baseline 配置。

## Decisions

### 决策 1：新增独立的上游候选边界层，而不是继续扩张 `order_planning`

做法：

- 在 `backend/core/stage_pipeline/adapters/` 下新增候选边界适配器。
- 它运行在 `prepare_daily_snapshot -> provider.day_signals/postprocess -> order_planning` 之间。
- 该层输出 `candidate_boundary_v1` payload，并把边界裁决后的买入候选集合写入 `current_day`。

理由：

- 这样可以在不改变子系统主 provider 协议的前提下，把共享执行上游的候选裁决从订单规划中剥离出来。
- 它仍然可以消费当日 `controls`、卖出后的持仓数和 `day_signals`，不会受 provider 缺少组合级上下文的限制。

备选方案：

- 直接把所有名额裁决完全下沉到 `multi_alpha_signal_provider`

不采用原因：

- provider 当前没有卖出后的持仓占用、正式 `effective_max_positions` 等完整上下文。
- 一次把全部逻辑压回 provider，改动面过大，难以保证 baseline 稳定。

### 决策 2：`candidate_boundary_v1` 只表达边界裁决结果，不重复定义执行目标真相

合同只包含：

- 决策日
- 生效的子系统边界模式
- 已确认的买入候选列表
- 子系统名额与可用名额摘要
- 候选裁决拒绝计数与最小样本
- 调试原因摘要

它不包含：

- 正式订单
- 最终目标持仓单
- 成交结果

理由：

- 候选边界层负责回答“哪些候选可以进入订单规划”。
- 目标持仓单负责回答“最终组合要长成什么样”。
- 两者必须分层，避免重复真相。

### 决策 3：`order_planning` 仍保留执行级 sizing 决策

保留在 `order_planning / portfolio_runtime` 的能力包括：

- 基于现金和手数的下单可行性
- `candidate_plan_mode`
- `cash_aware_search_top_n`
- `rotation_replace_*`
- 最终订单与目标持仓单构建

理由：

- 这些逻辑仍然属于执行内核“怎么把候选变成订单”的职责。
- 它们不是子系统候选边界，而是执行级 sizing/可成交性控制。

### 决策 4：研究诊断中明确新增“候选边界裁决”归因层

做法：

- 正式日级/订单级记录新增 `candidate_boundary_*` 摘要字段。
- 研究审计将 `SLEEVE_BUDGET_EXCEEDED` 等拒绝原因归到候选边界层，而不是执行规划层。

理由：

- 当前很多诊断被误解释成 `order_planning` 的执行行为，实际属于上游候选裁决。
- 把这层显式化后，后续再收紧多信号个股子系统边界会更清楚。

## Risks / Trade-offs

- [风险] 新增候选边界层会让日内 payload 增加一层结构 -> 缓解：只新增最小正式合同，并复用现有 `current_day` 生命周期，不新开第二套运行状态。
- [风险] 旧测试直接断言 `order_planning` 里的 debug_plan 字段 -> 缓解：同步把断言迁移到候选边界 payload 或新的 debug 摘要字段。
- [风险] 候选审计行来源变化可能影响研究诊断脚本 -> 缓解：保持 `candidate_rows` 的输出表头稳定，只改变来源和 stage 归因。
- [风险] 如果候选边界和执行规划都继续保留同名字段，会形成新一轮重复真相 -> 缓解：在实现中明确 `candidate_boundary_*` 前缀，只保留一处正式来源。

## Migration Plan

1. 先补 OpenSpec delta specs，明确候选边界层和 `order_planning` 新职责。
2. 新增候选边界适配器和合同结构，并在 `bridge_adapter.ensure_day()` 中接入。
3. 修改 `order_planning`，让它消费已裁决候选，不再自己解析子系统权重与名额。
4. 同步更新日级诊断、研究审计和相关测试。
5. 重跑 baseline_V10.1，确认收益口径无漂移后再结束 change。

回退路径：

- 删除候选边界适配器接线
- 恢复 `order_planning` 里的 `_resolve_sleeve_weights / _apply_hard_sleeve_budget` 路径
- 回退相关诊断字段和测试断言

## Open Questions

- `candidate_boundary_v1` 是否需要进入 `StageOutputs.payload` 作为标准阶段产物，还是只需要进入 `current_day` 和最终日级产物。
- 个股多信号路径之外，未来是否还有其他子系统需要复用这套候选边界层；本轮实现先不强求通用化，只保留可扩展字段。
