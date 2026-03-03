## Why

经过多轮快速迭代（pipeline-fix、trading-costs、audit-trail、ema-cross 等），代码库累积了大量死代码（约 4,500 行零引用）、两个巨型文件（`backtest_v2.py` 2346 行、`backtest_v2.js` 2651 行），以及重复定义（`sanitize_json`、`_results_root` 各出现两次）。这增加了认知负担、拖慢 onboarding，并让未来修改容易误触死路径。

## What Changes

### 删除死代码（Phase 1）
- **BREAKING** 删除 `backend/core/buses/` 整目录（~1,800 行）— 从未接入的实验总线克隆
- **BREAKING** 删除 `backend/core/execution/` 整目录（~800 行）— 被 `engine_vector` 完全取代
- 删除 `backend/core/analytics/` 中 9 个无外部调用者的文件，仅保留 `symbol_performance.py`
- 删除 `backend/core/portfolio/` 中 4 个死文件（`ledger.py`, `positions.py`, `snapshots.py`, `sizing.py`），保留 `portfolio_builder.py` + `selection_order.py` + `account.py`（被 execution 引用，连带删除）
- 删除 `backend/core/strategies/sma_cross_multifactor.py`（已废弃，registry 会 raise）
- 删除 `backend/core/tools/walkforward.py` + `univote_v2.py`（零引用）
- 删除 `backend/core/data/calendar.py` + `memory_provider.py` + `snapshot.py`（零引用）
- 删除 `backtest_v2.py` 内 ~630 行孤立函数（`normalize_row`, `build_run_meta`, `_write_*_csv`, `_extract_trigger_counters` 等）

### 拆分巨型文件（Phase 2）
- `backtest_v2.py` → 主文件(~700 行) + `_utils.py` + `_paths.py` + `_job_store.py` + `_config_store.py` + `_experiment_runner.py` + `_experiment_history.py`
- `backtest_v2.js` → 主文件(~500 行) + `report.js` + `charts.js` + `artifacts.js` + `ui-controls.js` + `api-client.js`

### 去重（Phase 3）
- `sanitize_json` 统一到 `_utils.py`，两处调用者改为 import
- `_results_root` / `_repo_root` 统一到 `_paths.py`

## Capabilities

### New Capabilities
- `dead-code-removal`: 识别并删除所有零引用模块、函数、文件
- `api-module-split`: 将 backtest_v2.py 拆分为职责清晰的子模块
- `frontend-module-split`: 将 backtest_v2.js 拆分为独立功能模块

### Modified Capabilities

（无现有 spec 级别行为变更 — 本次是纯内部重构，不改变任何 API 契约或前端功能）

## Impact

- **后端 API**：路由路径和请求/响应格式不变，仅文件组织结构变更
- **前端**：`index.html` 需要更新 `<script>` 标签引入拆分后的 JS 模块
- **Docker**：无变更（所有文件仍在同一镜像内）
- **测试**：现有测试 import 路径可能需要更新（如果引用了被删除的模块）
- **配置**：无变更
