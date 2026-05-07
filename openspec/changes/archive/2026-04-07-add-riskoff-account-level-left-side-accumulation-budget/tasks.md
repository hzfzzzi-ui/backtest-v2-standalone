## 1. 账户层预算合同

- [x] 1.1 定义 `RISK_OFF` 左侧累积预算输入与目标配比，DoD：`proposal/design/spec` 明确债为主、`510300.SH` 次之；验证：delta spec 能独立表达该预算合同；风险：若合同仍含糊，后续实现会重新滑回 ETF 局部补丁。
- [x] 1.2 将该预算语义接入 `account_allocator_runtime` 主解释，DoD：`run_meta` 可区分常规防守预算与 `RISK_OFF` 左侧累积预算；验证：主回放产物中出现账户层预算字段；风险：若只改 shadow 不改 runtime，会出现双重真相。

## 2. explain / audit / 前端

- [x] 2.1 切 audit 与 explain 到账户层左侧累积叙事，DoD：`audit`、`experiment_query_service`、前端 governor/account allocator 面板能解释该预算；验证：`audit.json` 与前端结果页一致；风险：若只切后端不切前端，用户仍会看到旧 governor 叙事。
- [x] 2.2 保持本轮不处理 execution constraint，DoD：设计和实现不修改 lot/cash/top-up 主逻辑；验证：代码 diff 不涉及执行约束主路径；风险：若边界失守，结果将无法归因到账户层预算。

## 3. 验收

- [x] 3.1 用 `A_STOCK_ETF_V1` 回放验证 `RISK_OFF` 左侧累积预算已成为主解释，DoD：`run_meta/audit/frontend` 一致体现账户层左侧累积；验证：对比主验收实验的结构差异；风险：若结构生效但行为无变化，应明确记录为预算语义成立而非执行落地成立。
- [x] 3.2 复核 `MaxDD / Calmar / RISK_OFF 非零持仓率`，DoD：本轮至少给出行为和风险方向判断；验证：改前改后指标与 `RISK_OFF` 持仓率对比；风险：若只看 CAGR，会误判这轮研究价值。
