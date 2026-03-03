## MODIFIED Requirements

### Requirement: 扁平化结果结构
API 返回的 result SHALL 为扁平结构：顶层包含 `exp_id`、`results_dir`、`status`、metrics 字段（cagr、sharpe、max_drawdown、trades 等）、以及 `artifacts` 字典。不再包含 `rows[]` 数组和 `group_id`。result 顶层还 SHALL 包含引擎产出的计数器字段，以便前端 fallback 使用。

#### Scenario: 结果包含必要 metrics
- **WHEN** 回测成功完成
- **THEN** result 顶层包含 `cagr`（float|null）、`sharpe`（float|null）、`max_drawdown`（float）、`trades`（int）、`total_return`（float）

#### Scenario: 结果包含引擎计数器字段
- **WHEN** 回测成功完成
- **THEN** result 顶层 SHALL 包含 `avg_positions`（float）、`trend_slope_block_count`（int）、`mf_rank_applied_rate`（float）、`mf_gate_on_rate`（float）

#### Scenario: 结果包含 artifacts 路径
- **WHEN** 回测成功完成
- **THEN** result.artifacts 包含 `perf`、`nav`、`funnel`、`reason_codes`、`config`、`run_meta`、`trades`、`symbol_performance` 八个键，值为相对于 results_dir 的文件路径
- **THEN** 若 `portfolio_daily.csv` 存在，result.artifacts 还 SHALL 包含 `daily` 键

#### Scenario: run_meta.json 包含 counters
- **WHEN** 回测成功完成
- **THEN** `results_dir/run_meta.json` SHALL 包含 `counters` 对象，含全部 exit 和 constraint 计数器
- **THEN** `counters` SHALL 使用短名口径：`raw_signal`、`blocked`、`orders`、`skipped`、`closed_trades`

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
