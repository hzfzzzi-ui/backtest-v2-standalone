## Why

当前主系统的桌面端、移动端、HTTP API、结果工作台和实验结果契约仍然混在巨型入口文件里，已经开始影响可维护性和结果契约稳定性。现在必须先把主系统边界拆清楚，否则后续的执行壳重构、脚本收编、baseline 报告和移动只读面都会继续互相耦合。

## What Changes

- 建立新的正式 API 边界：`backend/api/backtest_v2/*` 和 `backend/api/mobile/*`，并保留旧 HTTP path 兼容。
- 定义主系统统一结果契约：`ExperimentManifest`、`ExperimentSurface`、`ExecutionPreview`、`ResultsWorkbenchSnapshot`。
- 将桌面结果工作台正式收敛为 `fetch -> build snapshot -> push snapshot` 的单向桥接模型。
- 将历史实验列表统一为 `manifest + 少量 perf 摘要`，不再内联大 surface。
- 将移动端只读面统一为基于 `ExperimentSurface` 派生的移动摘要对象。

## Capabilities

### New Capabilities
- `runtime-boundary-contracts`: 定义主系统统一的 manifest、surface、preview 和 snapshot 契约及懒加载边界。
- `http-surface-boundary-split`: 定义新的 backtest/mobile API 边界、旧 path 兼容规则和历史实验摘要接口。
- `results-workbench-snapshot-boundary`: 定义桌面页壳、状态切片和结果工作台之间的唯一输入真相。

### Modified Capabilities
- 无

## Impact

- 影响后端 API 入口：[backtest_v2.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/endpoints/backtest_v2.py)、[_experiment_runner_api.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/endpoints/_experiment_runner_api.py)、[backtest_v2_artifacts.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/endpoints/backtest_v2_artifacts.py)。
- 影响前端页面壳和结果工作台边界：[backtest_v2.js](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/assets/js/backtest_v2.js)、[ui-controls.js](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/assets/js/ui-controls.js)、[artifacts.js](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/assets/js/artifacts.js)、[results-workbench-bridge.js](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/assets/js/results-workbench-bridge.js)。
- 影响应用层服务和未来 CLI 命令面，但本 change 不直接落地 CLI/study runner。
- 不应改变 baseline 结果、价格型信号时点或执行口径。
