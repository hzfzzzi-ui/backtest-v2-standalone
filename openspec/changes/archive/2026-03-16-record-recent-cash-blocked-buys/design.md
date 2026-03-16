## Context

系统当前已经能在候选规划阶段统计聚合级别的 `SKIP_NO_CASH` 计数，但缺少一份“最近一周交易日、按股票列出资金不足拦截明细”的稳定产物。最近一次回测里，即使 `portfolio_daily.csv` 显示某天存在买入候选和未成交，也无法直接回答是哪几只股票、当时现金是多少、估算买入多少股/金额。

这次 change 只补充诊断能力，不改变执行链行为。实现必须遵守 `backend/core` 约束：不改 execution timing，不改成交逻辑，不动 stage pipeline contract。

## Goals / Non-Goals

**Goals**

- 在候选审计行中稳定保留资金拦截所需的个股级字段。
- 每次回测落盘最近一周交易日的资金不足拦截明细，哪怕结果为空也要稳定输出空 CSV。
- 通过统一 `surface/{section}` 读取这份明细，避免前端直接读底层 artifact 文件。

**Non-Goals**

- 不修改买入排序、资金分配、cash-aware subset 选择逻辑。
- 不把 `NOT_SELECTED_CASH_AWARE` 重新解释成“资金不足”；本 change 只记录明确的 `SKIP_NO_CASH` 事件。
- 不新增前端页面逻辑；这次只提供后端可读产物和 surface section。

## Decisions

### 决策 1：只把明确的 `SKIP_NO_CASH` 视为“资金不足拦截”

原因：

- `NOT_SELECTED_CASH_AWARE` 表示 cash-aware planner 在预算内做了组合选择，不等同于“这只票因为现金不足被拦截”。
- 用户这次要的是确定性诊断，最小歧义的定义就是记录执行链里明确发生的 `cost > est_cash` 分支。

放弃的方案：

- 把所有 cash-aware 未选中标记都算作“资金不足拦截”。
  - 放弃原因：会混淆“预算优化未入选”和“现金不够无法下单”。

### 决策 2：诊断明细挂在候选审计行，而不是扩 runtime contract

原因：

- 当前 `portfolio_candidates.csv -> candidate_signals.csv` 已经是个股级候选诊断的正式承载面。
- 这次只需要 enrich 候选审计字段，不需要修改 `RuntimeDiagnosticsInput` 或 stage pipeline contract。
- 风险更低，不会影响 `daily_accounting` 或 `strict_runtime_daily_loop` 的核心边界。

放弃的方案：

- 在 `RuntimeDiagnosticsInput` 或 `diagnostics_input_json` 中新增 symbol-level 列表。
  - 放弃原因：会把高风险 runtime contract 改动引入一个纯诊断需求。

### 决策 3：recent artifact 的时间范围固定为最近 5 个交易日

原因：

- 用户要求是“最近一周交易日”。
- 实验目录里最稳定的交易日真相是 `portfolio_daily.csv`，因此以其中最后 5 个 distinct `date` 为准。
- 如果 `portfolio_daily.csv` 不存在或为空，则降级使用候选表里的最后 5 个 distinct `date`。

## Risks / Trade-offs

- [候选行字段膨胀]：`portfolio_candidates.csv` 会新增几个诊断列。控制方式是仅新增最小必要字段，不把整段 debug payload 塞进候选表。
- [误把 cash-aware 规划未选中当作现金不足]：通过只统计 `SKIP_NO_CASH` 避免语义漂移。
- [最近一周没有资金拦截事件]：artifact 仍输出空 CSV，保持前后端契约稳定。

## Migration Plan

1. 在候选审计行写入 `cash_available / estimated_qty / estimated_amount / estimated_price / cash_blocked_flag / cash_blocked_reason`。
2. 在 diagnostics finalize 中新增 `cash_blocked_buys_recent.csv` builder。
3. 在 manifest artifacts 和 query surface 中注册新 artifact / section。
4. 增加单测，验证：
   - 只采集 `SKIP_NO_CASH`
   - 只保留最近 5 个交易日
   - 空结果仍稳定输出
5. 跑定向测试，确认不触发 `V10.1` 行为口径漂移。
