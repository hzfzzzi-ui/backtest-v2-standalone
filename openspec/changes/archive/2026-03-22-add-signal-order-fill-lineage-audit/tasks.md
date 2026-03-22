## 1. Stable Lineage ID 合同

- [x] 1.1 定义 `signal_id/order_id/fill_id` 的最小字段与确定性生成规则；DoD: 形成可复现的 id 方案、父子关系和跨路由最小公共字段集；验证: 新增 contract 测试验证相同输入下 id 稳定；风险: 使用隐式或随机 id 会破坏复现与 golden。
- [x] 1.2 在正式执行链中传播 lineage id；DoD: 信号进入订单规划、订单进入成交落账时都能保留父链路关系；验证: 用代表性路由样本断言 `signal_id -> order_id -> fill_id` 完整存在；风险: 某个中间阶段吞字段会导致后续台账断链。

## 2. 生命周期台账与产物分层

- [x] 2.1 新增 execution lineage ledger artifact；DoD: 实验产物能输出独立明细台账，记录 `generated/scheduled/filled/rejected/canceled/expired` 等关键状态与日期；验证: 集成测试检查 artifact 存在、字段完整且不内联到 `audit.json`；风险: 状态集合定义不稳会导致不同路由难以统一。
- [x] 2.2 在 `audit.json` 中新增 lineage 摘要与异常样本引用；DoD: `audit.json` 可表达 generated/scheduled/filled/terminal 计数以及 same-day fill、dropped order、missing fill 等异常样本；验证: 审计契约测试和 artifact 样本核对；风险: 摘要与明细不同步会让审计失真。

## 3. Timing Gate 与 Golden 接线

- [x] 3.1 让 `timing_alignment` 优先消费显式 lineage 证据；DoD: 有 lineage 时优先按 `signal_date/scheduled_date/fill_date` 判定，无 lineage 时兼容旧推断路径；验证: 单元测试覆盖 same-day fill fail、next-day pass、missing lineage unknown/fallback；风险: 新旧路径优先级处理错误会改坏历史口径。
- [x] 3.2 扩展 execution contract goldens 覆盖 lineage；DoD: 代表性 golden 样本能校验 lineage id 稳定性、父子关系和终态；验证: golden 回归输出包含 lineage 断言；风险: golden 样本选择过窄无法覆盖关键路径。

## 4. 回归验证与运行边界说明

- [x] 4.1 补 contract / integration / audit 测试；DoD: 覆盖 dropped order、missing fill、cancel/reject、reason_code 追溯和主审计摘要引用；验证: 运行对应 pytest 子集并记录结果；风险: 只测 happy path 会遗漏链路断裂类问题。
- [x] 4.2 更新变更说明与回退策略；DoD: 说明 ledger artifact、主审计摘要、兼容回退路径和不纳入台账的边界；验证: 文档能独立解释为什么明细与摘要分层；风险: 边界未写清会导致后续继续把 diagnostics 与 lifecycle 混在一起。
