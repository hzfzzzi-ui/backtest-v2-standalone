## 1. 残留清理基线
- [x] 1.1 定义残留文件、目录、旧文档的正式清理准入条件。
- [x] 1.2 固定残留清理顺序与回退要求。

## 2. 相关规范收紧
- [x] 2.1 收紧 `dead-code-removal`，明确只有正式替代落地后才能删除。
- [x] 2.2 收紧 `clean-dir-structure`，明确目录清理必须服从正式边界收口。
- [x] 2.3 收紧 `script-surface-governance`，明确旧脚本和 compat 入口必须显式标记退出条件。

## 3. 实施前准备
- [x] 3.1 产出残留对象 checklist 模板。

## 4. 当前实现批次
- [x] 4.1 删除已不再被任何前端入口装载、且已被 `shared-api.js + desktop-shell/api-adapter.js` 替代的旧 helper：`frontend/assets/js/api.js`
- [x] 4.2 删除已不再被任何入口装载、且对应逻辑已内联到 `backtest_v2.js` 的旧 ESM helper：`frontend/assets/js/ui.js`
- [x] 4.3 记录当前不能删除的 compat 对象清单，并说明未满足双条件的原因。
- [x] 4.4 删除已被当前前端需求下线、且不再拥有任何页面 DOM 主入口的旧历史对比链：`frontend/assets/js/compare.js` 及其状态、事件、装载残留。
- [x] 4.5 删除已不再被结果工作台引用、且导出功能已被当前前端需求下线的旧 Markdown 报告 UI 组件：`frontend/app/results-workbench/components/AgentReportPanel.vue`

## 5. 后续批次
- [x] 5.1 在新桌面壳完全接管后，完成 `results-workbench-bridge.js`、`ui-controls.js`、`artifacts.js`、`desktop-*.js` 第一批前端 compat 退出。
- [x] 5.2 在事务域真正 DB 主表化后，将 `transaction_lifecycle_service` 与 `sim_account_domain_service` 切为 DB 主读写；文件路径降级为影子写出与回退 compat。
- [x] 5.3 在共享执行边界 compat 读取面退出后，完成旧 `ExecutionIntent` 读取面移除，并将 `CandidateBoundary / CandidatePlan` 降为未导出的残留结构，不再作为任何运行时或测试/spec 正式合同。
