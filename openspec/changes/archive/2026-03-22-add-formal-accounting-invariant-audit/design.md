## Context

当前正式主线的审计链路分成两层：

- `foundation_shell -> merge_experiment_audit` 负责把 `stage_pipeline`、`warnings`、`days_with_fills` 等运行摘要写入 `metrics["audit"]`
- `artifacts_finalize -> build_research_audit` 负责在 `audit.json` 中补 `research_audit`

这条链路已经具备正式产物入口，但没有把会计恒等式作为主线正式证据。仓库里的历史 `AuditCollector` 提供过现金守恒、持仓守恒、NAV 守恒、负现金和超仓等校验思路，但它没有成为当前 stage pipeline 主线的 canonical owner。结果是：研究门禁能判断时间合同、股票池口径和成交现实性，却不能正式证明“记账自洽”。

这次 change 是跨 `stage_pipeline`、`engine_runtime`、`audit`、`artifacts` 和测试合同的横切改动，适合先明确设计边界，再进入实现。

## Goals / Non-Goals

**Goals:**
- 让当前 stage pipeline 主线输出正式的 `accounting_integrity` 审计证据，而不是依赖历史旁路检查器。
- 让 `audit.json` 在保持兼容的前提下补齐会计恒等式摘要、异常计数和失败样本。
- 让 `research_audit` 基于主线证据新增 `accounting_integrity` gate，并进入统一 `overall_status` 聚合。
- 把运行复杂度保持在线性级别，避免通过事后重放全历史成交来做审计。

**Non-Goals:**
- 不在本 change 中引入 `signal -> order -> fill` 的稳定 lineage id 和生命周期台账。
- 不回迁整套历史 `AuditCollector` 输出格式，也不要求旧执行路径完全复刻其字段。
- 不改变策略执行语义、成交撮合逻辑或资金管理逻辑；本 change 只补正式审计。
- 不把全量日级快照内联到 `audit.json`。

## Decisions

### 决策 1：以主线正式记账快照为唯一审计输入

采用方案：
- 会计审计的 owner 放在当前正式执行链中，消费 `daily_accounting` / `AccountingSnapshot` / 等价正式快照，而不是在产物阶段重放 `portfolio_trades.csv`
- `portfolio_trades.csv` 仍可作为辅证，但不能作为唯一真相

原因：
- 运行时快照最接近真实执行状态，能线性地得到 `cash_before/after`、`positions_before/after`、`nav/cash/market_value`
- 事后从 `trades.csv` 反推容易丢掉未成交、当日状态、浮点容差和持仓边界信息

备选方案：
- 直接复用历史 `AuditCollector`
  - 放弃原因：它不在当前正式主线合同里，接线后仍需要重新定义与 `audit.json`、`research_audit` 的兼容边界
- 在 finalize 阶段完全依赖 artifact 重建
  - 放弃原因：复杂度更高，且可信度更低

### 决策 2：执行审计与研究门禁分层表达

采用方案：
- 在 execution audit 层新增 `accounting_integrity` 子树，保存摘要、异常计数、受控样本和状态
- 在 `research_audit.gates` 中新增同名 gate，把 execution audit 的事实转换为 `PASS/WARN/FAIL/UNKNOWN`

原因：
- execution audit 保留“发生了什么”的明细语义
- research audit 保留“这是否可信”的门禁语义
- 两层职责清楚，便于以后引入更细粒度的订单生命周期审计

备选方案：
- 只写 execution audit，不进 research_audit
  - 放弃原因：无法让正式研究门禁反映记账自洽性
- 只写 research_audit，不保留 execution audit 事实
  - 放弃原因：丢失复核样本，审计不可追责

### 决策 3：保持 `audit.json` 兼容，新增字段采用摘要 + sample 形式

采用方案：
- `stage_pipeline`、`warnings`、`days_with_fills` 等旧字段保持不变
- 新增字段只补充到现有 `audit.json` 顶层 execution audit 区域
- 每类失败只保留有限 sample，避免把日级全量快照塞进主审计文件

原因：
- 当前前端和 machine bundle 已经消费 `audit.json`
- 最小改动更符合仓库的研究纪律

备选方案：
- 另起 `accounting_audit.json`
  - 放弃原因：会制造第二份正式真相文件

### 决策 4：证据不足时返回 `UNKNOWN`，不偷渡成 `PASS`

采用方案：
- 如果某条主线路由没有提供足够的正式记账证据，`accounting_integrity` gate 返回 `UNKNOWN`
- 只有在证据完整且所有硬性检查通过时才给 `PASS`

原因：
- 这符合当前仓库“可信优先”的原则
- 能避免旧路由或过渡路径因为缺字段而被误判安全

备选方案：
- 缺证据默认跳过
  - 放弃原因：会让 formal audit 失真

## Risks / Trade-offs

- [风险] 不同执行路径提供的记账快照字段不一致 → 先定义最小 canonical 字段集；不足时统一降级为 `UNKNOWN`
- [风险] 新 gate 会让部分历史实验从 `PASS/WARN` 变成 `UNKNOWN/FAIL` → 在设计中保留兼容写盘，同时补测试和回归样本
- [风险] `audit.json` 体积变大 → 只保留摘要与 bounded samples，不内联全量日级记录
- [风险] 浮点误差导致误报 → 明确容差规则，并复用现有资金 / NAV 精度约定

## Migration Plan

1. 定义 canonical accounting audit 输入字段和 execution audit 输出 schema。
2. 在当前正式 stage pipeline 主线生成 `accounting_integrity` execution audit 子树。
3. 在 `research_audit` 中新增 `accounting_integrity` gate，并把它接入统一聚合。
4. 更新 `audit.json` stabilize、surface 兼容逻辑和 machine bundle。
5. 补 unit / integration / contract 测试，并用代表性实验样本做回归核对。

回退方案：
- 如主线接线不稳定，可先移除 `research_audit` 中的新 gate，保留 execution audit 子树或完全回退新增字段。
- 不修改旧字段的前提下，回退只需撤回新增子树与测试合同，不影响现有产物读取。

## Open Questions

- `accounting_integrity` 是否需要 `WARN` 层，还是只保留 `PASS/FAIL/UNKNOWN` 三态更清晰。
- 对“无成交但有完整快照”的实验，是直接判 `PASS` 还是单独标识为样本不足但记账一致。
