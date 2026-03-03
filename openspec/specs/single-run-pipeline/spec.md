# single-run-pipeline Specification

## Purpose
TBD - created by archiving change remove-multi-group. Update Purpose after archive.
## Requirements
### Requirement: 单次运行 API 入口
系统 SHALL 提供 `POST /api/backtest_v2/experiment/run_async` 端点，接收单份配置 JSON，执行一次回测，返回扁平化结果。不再接受 `preset` 参数进行多组变体生成。

#### Scenario: 正常单次运行
- **WHEN** 前端 POST 包含 symbols、start_date、end_date、benchmark、workbench_config 的请求
- **THEN** 后端执行单次回测，job status 最终变为 "success"，result 包含顶层 metrics 和 artifacts 字典

#### Scenario: 忽略 preset 参数
- **WHEN** 请求中包含 preset 字段
- **THEN** 后端忽略该字段，仍执行单次运行（向后兼容，不报错）

### Requirement: 扁平化结果结构
API 返回的 result SHALL 为扁平结构：顶层包含 `exp_id`、`results_dir`、`status`、metrics 字段（cagr、sharpe、max_drawdown、trades 等）、以及 `artifacts` 字典。不再包含 `rows[]` 数组和 `group_id`。result 顶层还 SHALL 包含引擎产出的计数器字段，以便前端 fallback 使用。

#### Scenario: 结果包含必要 metrics
- **WHEN** 回测成功完成
- **THEN** result 顶层包含 `cagr`（float|null）、`sharpe`（float|null）、`max_drawdown`（float）、`trades`（int）、`total_return`（float）

#### Scenario: 结果包含引擎计数器字段
- **WHEN** 回测成功完成
- **THEN** result 顶层 SHALL 包含 `avg_positions`（float）、`trend_slope_block_count`（int）、`mf_rank_applied_rate`（float）、`mf_gate_on_rate`（float）
- **THEN** result 顶层 SHALL 包含 `take_profit_exit_count`（int）、`fixed_stop_loss_exit_count`（int）、`drawdown_breaker_block_count`（int）

#### Scenario: 结果包含 artifacts 路径
- **WHEN** 回测成功完成
- **THEN** result.artifacts 包含 `perf`、`nav`、`funnel`、`reason_codes`、`config`、`run_meta`、`trades`、`symbol_performance` 八个键，值为相对于 results_dir 的文件路径
- **THEN** 若 `portfolio_daily.csv` 存在，result.artifacts 还 SHALL 包含 `daily` 键

#### Scenario: run_meta.json 包含 counters
- **WHEN** 回测成功完成
- **THEN** `results_dir/run_meta.json` SHALL 包含 `counters` 对象，含全部 exit 和 constraint 计数器
- **THEN** `counters` SHALL 使用短名口径：`raw_signal`、`blocked`、`orders`、`skipped`、`closed_trades`
- **THEN** `counters` SHALL 包含新增风控计数器：`take_profit_exit_count`、`fixed_stop_loss_exit_count`、`drawdown_breaker_block_count`、`drawdown_breaker_trigger_count`、`drawdown_breaker_recover_count`

#### Scenario: 不包含 rows 数组
- **WHEN** 回测成功完成
- **THEN** result 中不存在 `rows` 字段

### Requirement: 扁平化结果目录
回测产物 SHALL 直接写入 `outputs/experiments/exp_xxx/` 根目录，不再有 `groups/{group_id}/` 子目录层级。

#### Scenario: 产物文件在根目录
- **WHEN** 回测完成
- **THEN** `perf.json`、`nav.csv`、`funnel.csv`、`reason_codes.csv`、`config.json`、`run_meta.json`、`symbol_performance.csv` 直接位于 `results_dir/` 下

#### Scenario: 缺失产物降级写空
- **WHEN** 某产物源数据缺失
- **THEN** 系统 SHALL 写出对应空文件以保持协议完整
- **THEN** `run_meta.missing_fields` SHALL 记录缺失来源键名

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

### Requirement: run_config.json 包含 resolved universe 摘要
`run_config.json` SHALL 在 universe 解析完成后追加 `_resolved_universe` 字段，记录实际运行的 universe 信息。

#### Scenario: 非 CUSTOM 模式写入 resolved 摘要
- **WHEN** `universe_mode` 为 `ALL_A`、`HS300_ZZ500` 或 `INDUSTRY`
- **THEN** `run_config.json` SHALL 包含 `_resolved_universe` 对象
- **THEN** `_resolved_universe.mode` SHALL 等于实际使用的 universe_mode 字符串
- **THEN** `_resolved_universe.resolved_count` SHALL 等于 `resolve_universe_by_mode()` 返回的 symbols 列表长度
- **THEN** `_resolved_universe.raw_count` SHALL 等于 `universe_meta.raw_count`（限制前的原始数量）

#### Scenario: CUSTOM 模式同样写入 resolved 摘要
- **WHEN** `universe_mode` 为 `CUSTOM`
- **THEN** `run_config.json` SHALL 同样包含 `_resolved_universe` 字段
- **THEN** `_resolved_universe.resolved_count` SHALL 等于用户提供的 symbols 归一化去重后的数量

#### Scenario: 原始输入配置保留
- **WHEN** `run_config.json` 写入完成
- **THEN** `universe.symbols` 字段 SHALL 保留用户原始输入值（不被 resolved symbols 覆盖）
- **THEN** 可通过 `_resolved_universe` 与 `universe.symbols` 的对比区分"输入"与"实际"

### Requirement: 前端标的数量展示使用 resolved 值
前端"标的数量"展示 SHALL 优先使用 `run_meta.universe` 中的实际解析数量，回退到 `config.universe.symbols.length`。

#### Scenario: 摘要栏展示 resolved 数量
- **WHEN** `renderSummaryBar()` 渲染且 `run_meta.universe` 存在
- **THEN** "标的 N 个"中的 N SHALL 等于 `run_meta.universe.raw_count`（或 `resolved_count`）
- **THEN** 不再使用 `config_draft.universe.symbols.length`

#### Scenario: 实验详情展示 resolved 数量
- **WHEN** 实验配置详情表渲染"标的数量"行
- **THEN** 展示值 SHALL 优先取 `run_meta.universe.raw_count`
- **THEN** 若 `run_meta` 不存在（旧实验），回退到 `symbols.length`（行为不变）

#### Scenario: 回退行为
- **WHEN** `run_meta.json` 缺失或 `universe` 字段不存在
- **THEN** 前端 SHALL 回退到 `config.universe.symbols.length`
- **THEN** 用户体验与修复前一致（不会更差）

### Requirement: 多实验对比 API
系统 SHALL 提供批量读取多个实验 perf 和 nav 的 API 端点，避免前端逐个请求。

#### Scenario: 批量读取 perf
- **WHEN** 前端 POST `/api/backtest_v2/experiments/compare` 并提供 `exp_ids` 列表（2-5 个）
- **THEN** 后端 SHALL 返回各实验的 `perf.json` 数据，按 exp_id 索引
- **THEN** 若某实验产物缺失，对应值 SHALL 为 null

#### Scenario: 批量读取 nav
- **WHEN** 请求中 `include_nav` 为 true
- **THEN** 响应 SHALL 额外包含各实验的 nav 序列（date, nav 数组）
- **THEN** nav 数据 SHALL 已按日期排序

