## 1. 后端 — 删除多组系统

- [x] 1.1 删除 `variants.py` 整文件（多组参数变体定义）。DoD: 文件不存在，无 import 引用报错。验证: `python -c "from backend.core.buses.experiment import variants"` 应失败。
- [x] 1.2 删除 `experiment_matrix.py` 整文件（多组矩阵构建）。DoD: 文件不存在，无 import 引用报错。验证: 同上。
- [x] 1.3 清理 `experiment_runner.py`：删除所有 `_run_*_validate_*` 函数（约 20+ 个），仅保留 `run_experiment()` 入口。DoD: 文件行数从 ~9500 降至 ~1000 以内。验证: 搜索 `_run_.*_validate` 返回 0 结果。
- [x] 1.4 重写 `run_experiment()` 为单次运行：直接调用 `run_portfolio_backtest()`，不再 dispatch preset 或循环 variant。DoD: `run_experiment()` 接受配置参数，返回单次结果 dict。验证: 函数内无 for-variant 循环。

## 2. 后端 — API 结果结构改造

- [x] 2.1 改造 `_run_backtest_v2_experiment_sync()`：去掉 preset/variant 逻辑，调用新的 `run_experiment()`，返回扁平结构 `{ exp_id, results_dir, status, metrics..., artifacts: {} }`。DoD: 返回无 `rows[]` 数组。验证: 手动 POST 检查 JSON 结构。
- [x] 2.2 改造 `ensure_standard_artifacts()`：产物直接写入 `results_dir/` 根目录（不再有 `groups/` 子目录）。DoD: perf.json 等文件在 `exp_xxx/` 下。验证: 检查文件系统输出。
- [x] 2.3 简化 `write_manifest()`：manifest 不再有 `groups[]` 数组，记录单次运行元信息。DoD: manifest.json 无 groups 字段。验证: 读取生成的 manifest.json。
- [x] 2.4 删除 `resolve_group_dir()`、`_scan_group_candidates()` 等多组目录解析函数。DoD: 函数不存在，无调用方报错。验证: grep 搜索无引用。
- [x] 2.5 清理 `backtest_v2_artifacts.py` 中的多组逻辑（`stabilize_experiment_result` 等函数中 rows/group 相关代码）。DoD: 函数处理扁平结果。验证: 无 `group_id` 引用。

## 3. 前端 — 删除多组 UI

- [x] 3.1 删除 `state.baseline_group_id`、`findRow()`、`setActiveGroupById()`、`renderCompareStrip()`、`renderEstimates()` 函数。DoD: 函数不存在。验证: 搜索函数名返回 0。
- [x] 3.2 重写 `renderExperimentResult()`：不再渲染 group 表格，运行完成后直接设置 `state.active_result = result`，调用 `loadArtifacts()` + `renderRightInspector()`。DoD: 无 `#wbRows` 表格填充逻辑。验证: 运行后 KPI 面板和图表直接显示。
- [x] 3.3 调整 `loadGroupArtifacts()`：参数从 groupRow 改为直接使用 `state.active_result`，artifact 路径从 `result.artifacts` 读取。DoD: 函数正常加载 perf/nav/funnel 等 artifact。验证: 数据正确显示在面板。
- [x] 3.4 调整 `renderPerfPanel()` 和 `renderExplainPanel()`：数据来源从 `state.active_group.row` / `state.active_group_artifacts` 改为 `state.active_result` / `state.active_artifacts`。删除 `renderExplainPanel()` 中 baseline 对比列。DoD: KPI 和图表正确渲染。验证: 运行后面板显示完整数据。
- [x] 3.5 删除 `index.html` 中 `#wbBaseline`、`#wbPresetBar`、`#wbPreset` 元素，清理 `#wbRows` 表格或隐藏。DoD: HTML 中无这些元素。验证: 页面无多余 UI 控件。

## 4. 测试 + 清理

- [x] 4.1 更新 `test_flow_smoke.py`：step 4 (verify artifacts) 断言新的扁平结果结构（无 rows[]），改为检查 `result.status`、`result.cagr` 等顶层字段和 `result.artifacts`。DoD: 测试代码适配新结构。验证: pytest 语法检查通过。
- [x] 4.2 删除 `experiment_multifactor.json` 配置文件。DoD: 文件不存在。验证: ls 确认。
- [x] 4.3 清理所有对已删除模块的 import 引用（variants、experiment_matrix），确保 `python -c "from backend.api.endpoints.backtest_v2 import router"` 无报错。DoD: 无 ImportError。验证: Python import 成功。

