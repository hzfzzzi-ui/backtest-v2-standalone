## Context

当前正式文档已经把 study conclusion registry 定义为长期研究结论留痕，但实现上仍把 `study_gates.evaluate_hard_gates()` 的 `PASS/FAIL` 直接写入 registry 的 `verdict`。这使 `verdict` 同时承担两种语义：

- 运行硬门槛是否通过
- 研究方向是否被确认、证伪或暂不确定

这两种语义必须拆开。硬门槛通过只能说明该 window/variant 有可审计产物，不等于研究方向被接受。

## Goals / Non-Goals

**Goals:**

- 让新写入的 conclusion registry 使用正式 study verdict：`confirmed`、`falsified`、`inconclusive`。
- 保留 hard gate 结果，但放入独立 `gate_status` / `gate_reason` / `gate_checks` 字段。
- 让 `study_runner` 在写 registry 前做一次可解释转换，避免下游页面自行猜测。
- 让 `study_journal` 自动摘要按正式 study verdict 统计，同时兼容读取历史 `PASS/FAIL` 记录。

**Non-Goals:**

- 不回写或重写历史 `outputs/studies/conclusions/**/registry.jsonl`。
- 不修改任何实验运行结果、NAV、交易账本或 baseline 注册。
- 不引入新的收益门槛作为全局策略规则；本次只约束结果合同和默认推断。

## Decisions

### 1. `verdict` 只保留研究结论语义

新记录的 `verdict` 必须是 `confirmed`、`falsified`、`inconclusive` 之一。`PASS/FAIL` 继续允许作为输入兼容值，但 registry 写入时必须转换。

原因：

- OpenSpec 已经把正式结论定义为 confirmed/falsified/inconclusive。
- `PASS/FAIL` 过于像测试状态，不能表达研究方向。

备选方案：新增 `study_verdict`，保留旧 `verdict`。不采用，因为会让 `verdict` 继续停留在双语义状态。

### 2. hard gate 结果独立存储

registry 新增：

- `gate_status`
- `gate_reason`
- `gate_checks`
- `verdict_source`

原因：

- 需要保留“为什么能产出或不能产出可审计记录”的信息。
- 需要让前端和审计能区分 gate 与 research verdict。

### 3. 默认转换先保守

默认转换规则：

- hard gate `FAIL` -> `inconclusive`
- 缺少 compare 或关键指标 -> `inconclusive`
- hard gate `PASS` 且关键相对指标明显改善 -> `confirmed`
- hard gate `PASS` 且关键相对指标明显恶化 -> `falsified`
- 其他情况 -> `inconclusive`

当前先用最小关键指标：`cagr`、`sharpe`、`max_drawdown` 的 baseline delta。该转换只负责默认治理，不替代人工研究判断。

## Risks / Trade-offs

- [Risk] 历史 registry 中已有 `PASS/FAIL`，页面统计会混杂新旧口径。  
  -> Mitigation：读取端兼容旧值，但新写入端禁止继续写 `PASS/FAIL`。

- [Risk] 默认转换规则可能过于保守。  
  -> Mitigation：保守值只会让结论停留在 `inconclusive`，不会误升级 baseline；人工可在后续 change 中增加更精细的 study-specific gates。

- [Risk] 特定 study 可能只关心单一指标，默认综合判断不完全匹配。  
  -> Mitigation：保留 `gate_status` 和 key metrics，正式升级仍需人工审计，不由默认转换自动完成 baseline promotion。
