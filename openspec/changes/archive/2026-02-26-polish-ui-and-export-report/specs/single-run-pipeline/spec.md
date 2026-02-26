## MODIFIED Requirements

### Requirement: 扁平化结果结构
API 返回的 result SHALL 为扁平结构：顶层包含 `exp_id`、`results_dir`、`status`、metrics 字段（cagr、sharpe、max_drawdown、trades 等）、以及 `artifacts` 字典。不再包含 `rows[]` 数组和 `group_id`。result 顶层还 SHALL 包含引擎产出的计数器字段，以便前端 fallback 使用。

#### Scenario: 结果包含 artifacts 路径
- **WHEN** 回测成功完成
- **THEN** result.artifacts 包含 `perf`、`nav`、`funnel`、`reason_codes`、`config`、`run_meta`、`trades` 七个键，值为相对于 results_dir 的文件路径
- **THEN** 若 `portfolio_daily.csv` 存在，result.artifacts 还 SHALL 包含 `daily` 键
