## Why

当前公开主链虽然已经收敛到 `config_json -> experiment_id -> manifest/artifact`，但代码里仍残留三类边界漂移：公开 API 仍挂着 legacy 请求字段与 `results_dir` 后门，API 验证/序列接口仍直接实例化数据库 provider，审计产物仍分散在 foundation shell 与 artifact stabilize 两侧。继续清理旧代码前，必须先把这四个后端边界定死。

## What Changes

- 新增公开边界模块，冻结 `/api/backtest_v2/experiment/run`、`/run_async`、`/execution/preview`、`/artifacts/read` 的请求契约与最小返回面。
- **BREAKING** 移除公开 `artifacts/read` 对 `results_dir` 的依赖，公开产物读取只允许 `exp_id + manifest declared rel_path`。
- 新增共享数据库边界模块，统一 runtime provider 创建、universe 解析、验证用 symbol 集解析，以及 API 序列读取入口。
- 新增共享审计契约模块，统一 `audit.json`、`stage_summary`、`stage_pipeline` 的归一化与写盘入口。
- 明确 foundation shell 是唯一公开引擎编排边界，legacy stage adapter 仅允许作为 internal implementation detail 被调用。
- 补冻结文档与回归门禁，确保 `exp_20260308_021045840_cde0` 的核心产物保持不变。

## Capabilities

### New Capabilities
- `backend-boundary-freeze`: 冻结后端公开 API、引擎编排边界、数据库访问边界、审计写盘边界

### Modified Capabilities
- `single-run-pipeline`: 公开单次回测入口的编排边界改为只暴露 foundation shell
- `pipeline-data-integrity`: API 数据验证与行情序列读取改为走共享数据库边界
- `artifact-protocol-convergence`: 公开产物读取改为只认 `experiment_id + manifest`
- `backtest-audit`: 审计产物与 stage 管线摘要改为共享同一审计契约

## Impact

- 影响代码：
  - `backend/api/endpoints/backtest_v2.py`
  - `backend/api/endpoints/_experiment_runner_api.py`
  - `backend/core/engine_compat/foundation_shell.py`
  - `backend/core/tools/data_bundle_builder.py`
  - `backend/api/endpoints/backtest_v2_artifacts.py`
  - `frontend/assets/js/artifacts.js`
  - `frontend/assets/js/ui-controls.js`
- 影响系统：
  - 公开回测运行 API
  - 公开产物读取 API
  - 数据验证 / benchmark / symbol 序列查询 API
  - 审计产物写盘协议
