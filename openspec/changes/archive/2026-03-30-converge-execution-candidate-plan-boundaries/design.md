## Context

当前正式链路已经完成两层边界收敛：

- 子系统原始买入候选先进入 `candidate_boundary_v1`
- 执行内核正式目标输出为 `target_book_v1`

但 `order_planning` 与 `build_rebalance_orders()` 之间仍保留一组股票侧候选规划兼容参数：

- `candidate_plan_mode`
- `cash_aware_search_top_n`
- `rotation_replace_enabled`
- `rotation_replace_only_strong_risk_on`
- `rotation_replace_max_swaps_per_day`
- `rotation_replace_candidate_top_n`
- `rotation_replace_min_score_gap`
- `rotation_min_hold_days`

这组参数本质上描述的是“候选规划与轮换替换”语义，而不是执行内核的共用下单能力。继续让执行内核直接消费这些兼容参数，会让个股子系统逻辑继续渗入共享执行壳，也会让 ETF 等其他子系统未来很难复用统一执行边界。

## Goals / Non-Goals

**Goals:**

- 在 `candidate_boundary_v1` 和 `target_book_v1` 之间增加正式的 `candidate_plan_v1` 合同。
- 把候选规划、现金感知搜索、轮换替换等兼容逻辑从 `order_planning` 的配置读取中前移。
- 让 `order_planning` 只消费候选规划结果，而不是消费候选规划配置。
- 保持 `baseline_V10.1` 绩效、交易数和预热起点不漂移。
- 让审计可以区分“候选边界层”“候选规划层”“执行内核层”三类拒绝来源。

**Non-Goals:**

- 不改变 A 股个股主策略语义。
- 不改变 ETF 子系统正式研究口径。
- 不改 Governor、市场状态、风险预算或资产池。
- 不把 `build_rebalance_orders()` 整体重写为全新执行引擎。

## Decisions

### 决策 1：新增 `candidate_plan_v1`，而不是继续向 `order_planning` 传兼容参数

采用方案：

- 新增候选规划层适配器，输出 `candidate_plan_v1`
- `candidate_plan_v1` 负责表达：
  - 经候选边界确认后的最终候选计划
  - 现金感知选择结果
  - 轮换替换结果
  - 规划层拒绝计数与摘要

不采用的方案：

- 继续让 `order_planning` 读取这些兼容参数  
  原因：会继续把个股子系统私有语义留在共享执行层。

### 决策 2：执行内核只消费候选计划结果，不消费候选计划配置

采用方案：

- `order_planning` 只读取 `candidate_plan_v1` 和执行级 sizing 必需参数
- `build_rebalance_orders()` 的输入从“配置模式”收敛为“规划结果”

不采用的方案：

- 只把参数包装一下继续下传  
  原因：这只是在改字段形态，没有真正收边界。

### 决策 3：个股子系统承担候选规划真相，ETF 子系统允许直通

采用方案：

- 个股子系统负责形成 `candidate_plan_v1`
- ETF 子系统当前若没有现金感知搜索或轮换替换需求，可输出直通规划结果

不采用的方案：

- 为 ETF 单独再造一套候选规划协议  
  原因：当前目标是统一边界，不是增加新的资产专用分支。

### 决策 4：正式审计新增候选规划层归因，但不把研究诊断字段抬升为执行真相

采用方案：

- 正式审计记录 `candidate_boundary`、`candidate_plan`、`execution_kernel` 三层归因摘要
- 研究诊断可继续保留更细的排障字段，但不进入正式执行合同

不采用的方案：

- 直接复用现有 `candidate_rows` 作为全部层级真相  
  原因：这会再次混淆正式合同与研究排障口径。

## Risks / Trade-offs

- [风险] 候选规划层前移后，基线候选集合或轮换替换顺序可能发生漂移  
  → 缓解：以 `baseline_V10.1` 容器重跑作为强约束，逐项比对绩效、交易数和预热日期。

- [风险] `build_rebalance_orders()` 仍然较大，提炼候选规划接口时容易顺手扩大改动面  
  → 缓解：本次只抽离候选规划输入边界，不同时重写 sizing 和成交逻辑。

- [风险] 审计层新增第三层归因后，历史诊断脚本可能出现口径不兼容  
  → 缓解：正式审计新增字段时保留旧兼容别名，研究诊断脚本后续单独收口。

- [风险] ETF 子系统当前对候选规划层的需求很薄，新增合同后可能出现“直通层”看起来多余  
  → 缓解：明确 `candidate_plan_v1` 是统一边界合同，ETF 可使用最小直通 payload。
