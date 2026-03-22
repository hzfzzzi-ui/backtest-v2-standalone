# param-sweep-report Specification

## Purpose

定义参数扫描实验的对比报告输出要求，确保多实验结果可以按统一格式汇总、排序、分组展示，并保留失败样本的可观测性。

## Requirements

### Requirement: 从多个实验产物生成对比表
`sweep_report.py` MUST 扫描指定实验目录列表，从每个实验的 `perf.json` 提取关键指标，生成对比 CSV 和终端表格。

#### Scenario: 生成对比 CSV
- **WHEN** 调用 `sweep_report.generate_report(run_ids=[...])` 传入一组实验 run_id
- **THEN** 输出 CSV 文件包含列：`config_name, total_return, annual_return, max_drawdown, sharpe_ratio, win_rate, total_trades, turnover`，按 `sharpe_ratio` 降序排列

#### Scenario: 终端友好输出
- **WHEN** 脚本运行完成
- **THEN** 在终端打印对齐的表格，列宽自适应，数值格式化（百分比保留 2 位小数，夏普保留 3 位）

#### Scenario: 缺失实验标记
- **WHEN** 某个 run_id 的 `perf.json` 不存在（实验失败或未运行）
- **THEN** 该行在对比表中标记为 `FAILED`，不影响其他行的输出

### Requirement: 支持按轮次分组对比
对比表 MUST 支持按实验轮次（RSI 轮 / ATR 轮）和 universe（CSI800 / ALL_A）分组展示。

#### Scenario: 分组对比
- **WHEN** 生成报告时传入 `group_by="round"`
- **THEN** 输出按轮次分组的子表，每组内按 `sharpe_ratio` 排序，组间用分隔线区分
