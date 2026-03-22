## 1. Canonical 输入与 execution audit 接线

- [x] 1.1 固化主线路径可用的 accounting snapshot 最小字段集，明确 `cash_after`、`positions_after`、`trade_rows`、`nav`、`market_value`、`max_positions` 的 canonical 来源及缺证时降级规则。
- [x] 1.2 在正式 execution audit 中新增 `accounting_integrity` 摘要构建器，输出现金守恒、持仓守恒、NAV 一致性、负现金、超仓上限的计数与 bounded samples。
- [x] 1.3 将 `accounting_integrity` 接入 `audit.json` 写盘，同时保持既有 execution audit 字段兼容。

## 2. Research Gate 与正式门禁聚合

- [x] 2.1 在 `research_audit` 中新增 `accounting_integrity` gate，基于 execution audit 证据输出 `PASS/FAIL/UNKNOWN`，并补充 reason、evidence、metrics。
- [x] 2.2 将新 gate 纳入 `overall_status` 聚合与 evidence refs，不新增第二份审计真相文件。

## 3. 容差、样本与降级边界

- [x] 3.1 固化现金与 NAV 容差、sample 截断和 hard-fail 规则，并补充边界测试。
- [x] 3.2 对旧路径或证据不足路径补 `UNKNOWN` 降级，避免缺证时误判为 `PASS`，同时保持 `audit.json` 正常写盘。

## 4. 回归验证与变更说明

- [x] 4.1 补主路径单元测试与集成测试，覆盖 cash/position/NAV 守恒、负现金、超仓、兼容写盘和 `research_audit` 聚合。
- [x] 4.2 保留变更说明、验证方式和回退路径，确保后续可以独立理解“改了什么、怎么验、怎么回退”。
