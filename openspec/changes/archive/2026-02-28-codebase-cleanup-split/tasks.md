## 1. Phase 1 — 删除死代码（零风险，零引用）

- [x] 1.1 删除 `backend/core/buses/` 整目录
- [x] 1.2 删除 `backend/core/execution/` 整目录
- [x] 1.3 删除 analytics 死文件：`report.py`, `equity.py`, `export.py`, `conclusions.py`, `summary.py`, `benchmark_curve.py`, `trade_pnl.py`, `trade_concentration.py`, `schema.py`
- [x] 1.4 删除 portfolio 死文件：`account.py`, `ledger.py`, `positions.py`, `snapshots.py`, `sizing.py`
- [x] 1.5 删除 `strategies/sma_cross_multifactor.py`，清理 registry.py 中对应分支
- [x] 1.6 删除 `tools/walkforward.py` + `tools/univote_v2.py`
- [x] 1.7 删除 `data/calendar.py` + `data/memory_provider.py` + `data/snapshot.py`
- [x] 1.8 删除 `backtest_v2.py` 内孤立函数（~630 行）：`normalize_row`, `_parse_ps_object_row`, `_resolve_candidate_dir`, `_to_rel`, `_write_nav_csv`, `_write_funnel_csv`, `_write_reason_code_counts_csv`, `_infer_universe_size`, `build_run_meta`, `_infer_manifest_dims`, `_extract_trigger_counters`, legacy run 子系统函数
- [x] 1.9 Docker rebuild + curl 冒烟测试：确认所有路由正常、回测执行成功

## 2. Phase 2a — 后端 API 拆分

- [x] 2.1 创建 `_utils.py`：提取 `sanitize_json`, `_coerce_number`, `_load_json_file`, `_hash_json`, `_sanitize_for_json` 及相关常量
- [x] 2.2 创建 `_paths.py`：提取所有路径辅助函数 `_repo_root`, `_bt_root`, `_results_root`, `_configs_root`, `_execution_root`, `_jobs_root`, `_job_file`, `_experiments_root`
- [x] 2.3 更新 `backtest_v2.py` 和 `backtest_v2_artifacts.py`：将重复定义替换为从 `_utils` 和 `_paths` 的 import
- [x] 2.4 创建 `_job_store.py`：提取 Job 管理逻辑（`_JOBS`, `_persist_job`, `_create_job`, `_update_job`, `_is_cancel_requested`, `_mark_job_canceled`, `_job_payload`）
- [x] 2.5 创建 `_config_store.py`：提取配置 CRUD 路由（save/get/list configs + flow_script 辅助）
- [x] 2.6 创建 `_experiment_runner_api.py`：提取实验执行逻辑（`_run_sync`, `_run_job`, `_build_runtime_cfg_from_workbench` 等）
- [x] 2.7 创建 `_experiment_history.py`：提取实验历史路由（list/get_report/delete/clear_all）
- [x] 2.8 主文件注册子路由：`router.include_router()` 整合所有子模块
- [x] 2.9 Docker rebuild + curl 测试全部 19 个路由端点

## 3. Phase 2b — 前端 JS 拆分

- [x] 3.1 创建 `report.js`：提取 `generateReport()` 及其内部辅助函数
- [x] 3.2 创建 `api-client.js`：提取 `apiRequestJson` 及状态面板函数
- [x] 3.3 创建 `charts.js`：提取 LightweightCharts 渲染函数（`renderNavChartLW`, `renderDdChartLW`, `setupChartSync` 等）
- [x] 3.4 创建 `artifacts.js`：提取产物加载和面板渲染函数（`loadActiveArtifacts`, `renderPerfPanel` 等）
- [x] 3.5 创建 `ui-controls.js`：提取表单/配置/抽屉交互函数（`buildConfigDraft`, `applyConfigToUI` 等）
- [x] 3.6 更新 `index.html`：按依赖顺序添加 `<script>` 标签
- [x] 3.7 Docker rebuild + 浏览器手动验证：页面加载无 JS 错误，回测全流程正常

## 4. Phase 3 — 去重验证

- [x] 4.1 确认 `sanitize_json` 仅在 `_utils.py` 中定义，`backtest_v2.py` 和 `backtest_v2_artifacts.py` 都从 `_utils` import
- [x] 4.2 确认 `_repo_root` / `_results_root` 仅在 `_paths.py` 中定义
- [x] 4.3 最终 Docker rebuild + 完整回测冒烟测试（包含交易成本字段验证）
