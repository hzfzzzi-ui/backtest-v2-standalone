## Context

最近几轮 change 已经把执行总线、artifact finalize pipeline 和 runtime 热点拆成了 facade 加子模块，但 `daily_accounting.py`、`artifacts_diagnostics.py` 与 `strict_runtime_daily_loop.py` 之间仍有一层耦合没有拆掉：执行主循环在生成原始事件的同时，也隐含承担了 buy funnel 与 stage count 的最终口径定义。后续只要继续重构 runtime 热点，这层混合 ownership 就会把“结构调整”重新变成“计数漂移风险”。

当前约束：
- `baseline_V10.1 -> exp_20260314_144548534_7db9` 是唯一回归锚点。
- 不能改变信号时点、成交时点、订单数和交易数。
- 只能重构 diagnostics owner 和阶段计数的归属，不允许借机改执行行为。

## Goals / Non-Goals

**Goals:**
- 为执行层建立统一的 `runtime diagnostics snapshot` 与 `stage count` 契约。
- 让 `daily_accounting.py` 只输出原始执行快照与原始诊断输入，不再定义最终 UI/artifact 口径。
- 让 `artifacts_diagnostics.py` 成为唯一的 canonical diagnostics builder。
- 让 `strict_runtime_daily_loop.py` 只保留执行主循环与原始事件采集，不再混合最终 funnel 归一化。
- 为后续继续拆 runtime/provider 热点提供稳定的 diagnostics owner。

**Non-Goals:**
- 不重写 `strict_runtime_default.py` 的执行语义。
- 不改变 `V10.1` 的收益、回撤、订单数、交易数或 stage funnel 最终值。
- 不扩展新的 UI 字段或新的实验协议。
- 不顺手调整 provider、portfolio 或 benchmark 行为。

## Decisions

### 1. 引入独立的 runtime diagnostics contract
把“执行层原始事件”和“诊断层最终口径”拆开。执行层只负责提供原始计数输入，例如原始买信号数、候选数、持仓过滤后数量、slot/cash 约束输入、exit owner 分布、reason counts 和 audit payload；最终 buy funnel、surface counters 和 diagnostics notes 统一由 diagnostics contract 归一化。

备选方案：
- 继续让 `daily_accounting.py` 直接写最终 daily row 口径。
  - 不选，因为它会让每次执行循环重构都重新碰 diagnostics 语义。

### 2. `daily_accounting.py` 只做日快照与原始诊断输入
`daily_accounting.py` 保留：
- `DailySnapshot`
- daily row 基础字段
- 原始执行事件到 diagnostics input 的收集

它不再负责：
- route 专属的最终 funnel 归一化
- artifact 面向 UI 的文案和 stage note

备选方案：
- 在 `strict_runtime_daily_loop.py` 内继续构建 diagnostics row，再由 `daily_accounting.py` 落盘。
  - 不选，因为这会让 diagnostics owner 重新回到执行本体。

### 3. `artifacts_diagnostics.py` 成为 canonical diagnostics builder
`artifacts_diagnostics.py` 统一消费 runtime diagnostics snapshot，并负责：
- buy stage funnel
- counters
- symbol/reason diagnostics
- surface 诊断字段

这允许后续接别类资产时，只替换 diagnostics builder，而不是回头改执行循环。

备选方案：
- 把 diagnostics builder 下沉回 `daily_accounting.py`
  - 不选，因为会再次混合执行与诊断。

### 4. `strict_runtime_daily_loop.py` 只保留原始事件，不保留最终 stage 语义
`strict_runtime_daily_loop.py` 可以继续收集执行当日的原始事件和原始 debug plan，但不再对“最终 stage 名称、stage note、slot/cash 归一化语义”负责。最终 stage 解释统一放到 diagnostics builder。

备选方案：
- 在 daily loop 内构建完整 stage funnel 对象并直接写入结果。
  - 不选，因为这会固定一套难以迁移的执行内嵌 diagnostics 协议。

## Risks / Trade-offs

- [Risk] stage count 归一化迁移后与现有 baseline funnel 不一致
  → Mitigation：以 `baseline_V10.1` 做 artifact compare 和 smoke，对 `buy_stage_funnel`、`run_meta`、`orders/closed_trades` 同时对照。

- [Risk] diagnostics contract 新增中间对象，短期内增加模块数量
  → Mitigation：保持 facade 稳定，只新增一个集中 contract owner，避免继续散落 helper。

- [Risk] route 专属口径仍可能偷偷回流到执行层
  → Mitigation：在 specs 和测试里明确规定 route 专属归一化只能发生在 diagnostics builder。

## Migration Plan

1. 新增 runtime diagnostics contract 与输入/输出数据类。
2. 重构 `daily_accounting.py`，让它输出原始 diagnostics input。
3. 重构 `artifacts_diagnostics.py`，改为消费 canonical diagnostics input 并输出统一 funnel/counters。
4. 收缩 `strict_runtime_daily_loop.py` 中与最终 diagnostics 语义相关的逻辑。
5. 跑 baseline artifact compare、runtime smoke 和相关单测。
6. 若任一步对 `baseline_V10.1` 造成漂移，直接回退新 contract 接线，恢复旧 diagnostics owner。

## Open Questions

- breakout route 当前对 `buy_candidate_count / after_held_filter_count / after_slot_filter_count` 的中间语义，是否完全可以统一为 diagnostics builder 归一化，还是仍需保留极少量 route hint 字段。
- 是否需要把 diagnostics contract 进一步推广到非 default route 之外的其他执行入口；本 change 先不扩张，只收当前主链。
