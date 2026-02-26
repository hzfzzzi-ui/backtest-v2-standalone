## Context

当前系统围绕"多组实验"设计：`run_experiment()` 通过 `preset_variants()` 生成 N 组参数变体，循环调用 `run_portfolio_backtest()`，结果以 `rows[]` 数组返回，前端通过组选择/baseline 对比展示。

实际前端 UI 只为单组参数设计，多组逻辑是无效复杂度。需要将整条管道从"多组编排"改造为"单次直达"。

核心引擎 `run_vector_portfolio_backtest_strict()` 和 `run_portfolio_backtest()` 不受影响——它们本身就是单次执行。改造对象是引擎之上的编排层和引擎之下的结果展示层。

## Goals / Non-Goals

**Goals:**
- 删除多组参数变体系统（variants、preset handler、experiment matrix）
- API 返回扁平化单次结果（无 rows[]、无 group_id）
- 前端运行完成后直接渲染 KPI + 图表，不经过组选择
- 结果目录扁平化（artifact 直接在 `exp_xxx/` 下）
- 通流测试适配新结构

**Non-Goals:**
- 不改动引擎层（`portfolio_simulator_strict.py`、`portfolio_builder.py`）
- 不改动数据加载层（DB 查询、数据预处理）
- 不设计"多 JSON 多次运行"的未来功能（留给后续 change）
- 不处理历史实验数据迁移（旧数据保留但不再兼容 UI 加载）

## Decisions

### Decision 1: `run_experiment()` 直接调用引擎

**选择**: 重写 `run_experiment()` 为：加载数据 → 构建 strategy → 调用 `run_portfolio_backtest()` → 返回单次结果

**放弃**: 保留 preset dispatch + 硬编码单组 variant。理由：既然删除多组，保留 dispatch 框架没有意义。

### Decision 2: API 结果结构扁平化

**选择**: 返回结构改为 `{ exp_id, results_dir, status, cagr, sharpe, ..., artifacts: { perf, nav, ... } }`

**放弃**: 保留 `rows[]` 但只放一个元素。理由：前端还得做 `rows[0]` 取值，增加无意义的间接层。

### Decision 3: 结果目录无 groups 子目录

**选择**: artifact 直接写入 `outputs/experiments/exp_xxx/` 根目录

**放弃**: 保留 `groups/default/` 子目录。理由：既然只有一组，多一级目录就是多一个路径拼接错误的机会。

### Decision 4: 前端跳过组选择，直连 perf panel

**选择**: `runExperiment()` 完成后直接调用 `loadArtifacts(result)` → `renderRightInspector()`，删除中间的 `renderExperimentResult()` 表格 + `setActiveGroupById()` + `renderCompareStrip()`

**放弃**: 隐藏表格但保留代码。理由：死代码会持续造成理解成本和维护负担。

### Decision 5: 保留 `ensure_standard_artifacts()` 产物生成

**选择**: 继续使用现有 artifact 生成逻辑（perf.json、nav.csv、funnel.csv 等），只调整输出路径从 `groups/G1/` 改为根目录

**放弃**: 重写产物生成。理由：产物格式本身没问题，前端 `loadGroupArtifacts()` 已经能解析这些格式。

## Risks / Trade-offs

- **[历史数据不兼容]** → 接受。旧的多组实验结果保留在磁盘但 UI 无法加载。用户可直接查看 JSON/CSV 文件。
- **[experiment_runner.py 大幅删除]** → 先备份。但由于即将 git init，git history 会保护代码。
- **[前端状态命名]** → `active_group` / `active_group_artifacts` 需要重命名以反映单次运行语义（如 `active_result` / `active_artifacts`）。如果重命名范围太大可保留旧名暂不改。
