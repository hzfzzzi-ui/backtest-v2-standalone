## 1. 账户层状态切换合同

- [x] 1.1 定义账户层统一状态切换分类与输入输出合同，DoD：runtime 能区分 `risk_on -> risk_on`、`risk_on -> defensive`、`defensive -> defensive`、`defensive -> recovery` 四类切换，并统一输出 carry/de-risk/cash release/budget handoff 结构；验证：`run_meta` 与调试快照出现统一 transition policy 字段；风险：若仍按单状态 patch 定义，双重语义会继续保留。
- [x] 1.2 将账户状态机上收为上游真相，DoD：账户层状态不再由 stock/ETF sleeve 状态简单聚合反推；验证：移除或降级 `_most_defensive_state` 之类聚合真相路径，并能在 explain 中说明账户状态输入证据；风险：若 state source 不收口，账户层仍只是 sleeve 派生层。

## 2. runtime 与 reference 边界收口

- [x] 2.1 收紧 combo/reference 边界，DoD：当 `runtime_truth_source = account_allocator` 时，旧 combo/reference 只保留 benchmark/reference 角色，不再与主 runtime 并列承担解释权；验证：`run_meta`、`surface`、`query` 中主真相字段只指向账户层；风险：若 reference 仍与主真相平铺，用户将继续看到双真相。
- [x] 2.2 将状态切换合同接入账户层 runtime 主链，DoD：账户层 steady-state budget 与 transition policy 在统一 runtime 合同中并列输出，sleeve 只消费该输出；验证：`account_allocator_runtime` 同时出现预算与状态切换字段，ETF/stock 不再单独定义账户层切换语义；风险：若只改 explain 不改主链，执行层仍会回落旧语义。

## 3. explain / audit / frontend 单叙事

- [x] 3.1 收口 audit 与 query 叙事，DoD：`audit.json`、`experiment_query_service` 能统一解释账户层预算与状态切换，不再并列输出旧 combo/governor 主叙事；验证：主回放产物中账户层叙事完整且 reference 区显式降级；风险：若 audit/query 不同步，前后端会继续各讲一套。
- [x] 3.2 收口前端主展示，DoD：结果工作台在 `runtime_truth_source = account_allocator` 时只保留账户层主面板，旧 combo/governor 只显示为 reference 区；验证：前端 surface/combo_truth 与页面展示一致；风险：若前端仍平铺双面板，用户仍会把 reference 当主真相。

## 4. 验收与回退

- [x] 4.1 用正式回放验证统一状态切换合同不再产生双重语义，DoD：至少完成 `A_STOCK_ETF_V1` 主回放，明确列出哪些状态切换已纳入账户层合同、哪些仍是 no-op；验证：改前改后 `run_meta / audit / surface` 对比；风险：若合同范围写全但实现未落，系统会出现“文档全、runtime 空”的假完成。
- [x] 4.2 完成最小正式回归与回退说明，DoD：前端最小回归、unit 最小回归通过，并给出账户层 transition policy 的最小回退集；验证：最小正式回归为绿，回退文件列表明确；风险：若没有回退路径，高风险 L3 迁移不可控。
