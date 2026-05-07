## 1. 共享账户执行 owner 接管

- [x] 1.1 新增共享账户执行 runtime 编译入口，DoD：能从 `state_transition_runtime + transition_action_handoff` 生成统一 `transition execution plan/owner/status/reason/reject`；验证：单测或最小回放能看到新字段；风险：只接 explain 不接主执行会继续双语义。
- [x] 1.2 在主执行链切换 owner，DoD：当 `runtime_truth_source = account_allocator` 时 transition execution 只走共享账户执行 runtime；验证：主回放中主 reason code 不再来自旧 weak-state 路径；风险：owner 切换可能引入行为漂移。

## 2. 旧 ETF weak-state 路径降级

- [x] 2.1 将旧 weak-state 路径降级为 diagnostics/reference，DoD：`state_edge_cash_release`、`riskoff_cash_drip_topup`、`riskoff_account_budget_materialization`、`weak_state_inter_rebalance_defense_redeploy` 不再输出主执行结论；验证：run_meta 与 portfolio diagnostics 仅在 reference 区出现旧路径；风险：历史排障脚本可能依赖旧主 reason code。
- [x] 2.2 明确 family implementation status，DoD：全部 transition family 都有账户层 implementation status，未实现 family 不再静默回落旧 owner；验证：run_meta/audit 可见 family status；风险：状态标记不完整会误导前端与审计。

## 3. 审计、查询与前端单真相收口

- [x] 3.1 同步 audit/query/front-end 主叙事，DoD：主面板只展示账户层 transition execution owner，旧 ETF 局部路径只进 diagnostics/reference；验证：`audit.json`、`combo_truth`、结果工作台文本一致；风险：前端若仍偷读旧字段会继续并列双语义。
- [x] 3.2 收紧 reference combo 边界，DoD：`combo/reference` 只保留 benchmark/reference 角色，不再与账户层 transition execution 平铺展示；验证：query/front-end 无同级双叙事；风险：历史兼容展示需要额外 fallback 文本。

## 4. 回放验收与回退准备

- [x] 4.1 跑 ETF standalone 与 `A_STOCK_ETF_V1` 主回放，DoD：共享账户执行 owner 成为主执行结论，旧 weak-state 路径不再主导 reject；验证：对比 `run_meta / audit / portfolio_daily.csv`；风险：行为漂移需要重新归因。
- [x] 4.2 跑最小正式回归并记录回退点，DoD：最小正式回归通过且记录最小回退文件集；验证：`tests/run_minimal_formal_regression.ps1`；风险：如果不记录回退集，L3 切换失败后难以快速恢复。

## 回退点

- 最小回退文件集：
  - `backend/core/services/account_allocator_shadow.py`
  - `backend/core/services/cn_stock_etf_unified_runtime_service.py`
  - `backend/core/engine_vector/etf_beta/execution_paths.py`
  - `backend/core/services/experiment_query_service.py`
  - `backend/core/audit/research_audit.py`
  - `frontend/app/results-workbench/helpers/resultsFormatting.js`
