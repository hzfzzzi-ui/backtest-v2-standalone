## Why

当前系统核心围绕"多组实验"设计——一次运行通过 preset 生成 N 组参数变体（G1-G4 等），前端用表格展示多组结果、支持组间对比。但实际使用中前端 UI 配置面板只为单组参数设计，多组逻辑导致：
1. Dashboard 字段和图表不刷新（artifact 路径嵌套在 `groups/{group_id}/` 下，链路断裂）
2. 大量无用代码（`variants.py` 1465 行、`experiment_runner.py` 20+ 个 `_run_*_validate_*` 函数共 ~8500 行）
3. 前端组选择/baseline 对比等交互与实际单组使用场景不匹配

未来如需多组对比，应采用"加载多份 JSON config 分别运行"的方式，而非当前"一份 config 生成多组参数变体"。

## What Changes

- **BREAKING** 删除多组参数变体系统：`variants.py` 整文件、`experiment_matrix.py` 整文件
- **BREAKING** 清理 `experiment_runner.py`：删除 20+ 个 preset handler 函数（`_run_*_validate_*`），重写 `run_experiment()` 为单次运行入口
- **BREAKING** API 返回结构变更：废弃 `result.rows[]` 数组 + `group_id`，改为顶层扁平化 metrics + `artifacts` 字典
- **BREAKING** 结果目录扁平化：从 `exp_xxx/groups/G1/perf.json` 变为 `exp_xxx/perf.json`
- 删除前端多组 UI：group 表格、baseline 选择器、compare strip、preset 下拉框
- 简化前端渲染链路：运行完成后直接渲染 KPI 面板 + 图表，不再经过"选组→加载 artifact"
- 更新 `test_flow_smoke.py` 适配新结果结构

## Capabilities

### New Capabilities
- `single-run-pipeline`: 单次运行管道——从 API 接收配置到引擎执行到结果返回到前端渲染的完整单次运行路径

### Modified Capabilities
- `smoke-flow-test`: 通流测试需适配新的结果结构（无 rows[]、无 group_id）

## Impact

- **后端删除文件**：`variants.py`、`experiment_matrix.py`、`experiment_multifactor.json`
- **后端重构文件**：`experiment_runner.py`（~9500→~1000 行）、`backtest_v2.py`（API 端点 + artifact 稳定化）、`backtest_v2_artifacts.py`
- **前端重构文件**：`backtest_v2.js`（状态管理 + 渲染链路）、`index.html`（删除 preset/baseline HTML 元素）
- **测试文件**：`test_flow_smoke.py` 断言结构需同步更新
- **历史数据**：`outputs/experiments/` 下已有多组实验结果将不再兼容（可保留但无法从 UI 加载）
