## ADDED Requirements

### Requirement: 单次运行 API 入口
系统 SHALL 提供 `POST /api/backtest_v2/experiment/run_async` 端点，接收单份配置 JSON，执行一次回测，返回扁平化结果。不再接受 `preset` 参数进行多组变体生成。

#### Scenario: 正常单次运行
- **WHEN** 前端 POST 包含 symbols、start_date、end_date、benchmark、workbench_config 的请求
- **THEN** 后端执行单次回测，job status 最终变为 "success"，result 包含顶层 metrics 和 artifacts 字典

#### Scenario: 忽略 preset 参数
- **WHEN** 请求中包含 preset 字段
- **THEN** 后端忽略该字段，仍执行单次运行（向后兼容，不报错）

### Requirement: 扁平化结果结构
API 返回的 result SHALL 为扁平结构：顶层包含 `exp_id`、`results_dir`、`status`、metrics 字段（cagr、sharpe、max_drawdown、trades 等）、以及 `artifacts` 字典。不再包含 `rows[]` 数组和 `group_id`。

#### Scenario: 结果包含必要 metrics
- **WHEN** 回测成功完成
- **THEN** result 顶层包含 `cagr`（float|null）、`sharpe`（float|null）、`max_drawdown`（float）、`trades`（int）、`total_return`（float）

#### Scenario: 结果包含 artifacts 路径
- **WHEN** 回测成功完成
- **THEN** result.artifacts 包含 `perf`、`nav`、`funnel`、`reason_codes`、`config`、`run_meta` 六个键，值为相对于 results_dir 的文件路径

#### Scenario: 不包含 rows 数组
- **WHEN** 回测成功完成
- **THEN** result 中不存在 `rows` 字段

### Requirement: 扁平化结果目录
回测产物 SHALL 直接写入 `outputs/experiments/exp_xxx/` 根目录，不再有 `groups/{group_id}/` 子目录层级。

#### Scenario: 产物文件在根目录
- **WHEN** 回测完成
- **THEN** `perf.json`、`nav.csv`、`funnel.csv`、`reason_codes.csv`、`config.json`、`run_meta.json` 直接位于 `results_dir/` 下

### Requirement: 前端直连渲染
前端 SHALL 在运行完成后直接从 result 加载 artifacts 并渲染 KPI 面板和图表，不经过组选择步骤。

#### Scenario: 运行完成自动渲染
- **WHEN** pollJob 返回 success
- **THEN** 前端直接调用 loadArtifacts → renderPerfPanel → renderExplainPanel，KPI 卡片和 NAV/DD 图表立即显示

#### Scenario: 无组选择 UI
- **WHEN** 用户查看运行结果
- **THEN** 页面上不显示组表格、baseline 选择器、compare strip

### Requirement: 删除多组参数变体系统
系统 SHALL 不再包含 preset 变体生成逻辑。`variants.py`、`experiment_matrix.py` 以及 `experiment_runner.py` 中的 `_run_*_validate_*` 系列函数 SHALL 被移除。

#### Scenario: 无 variants 模块
- **WHEN** 检查后端代码库
- **THEN** 不存在 `variants.py` 文件、不存在 `experiment_matrix.py` 文件

#### Scenario: 无 preset handler 函数
- **WHEN** 检查 `experiment_runner.py`
- **THEN** 不存在 `_run_*_validate_*` 形式的函数，`run_experiment()` 直接调用引擎

### Requirement: 保留引擎层不变
`portfolio_simulator_strict.py` 和 `portfolio_builder.py` SHALL 保持不变。单次运行仍通过 `run_portfolio_backtest()` → `run_vector_portfolio_backtest_strict()` 路径执行。

#### Scenario: 引擎调用链完整
- **WHEN** 执行单次回测
- **THEN** 调用链为 `run_experiment()` → `run_portfolio_backtest(engine_mode="VECTOR_FAST_STRICT")` → `run_vector_portfolio_backtest_strict()`
