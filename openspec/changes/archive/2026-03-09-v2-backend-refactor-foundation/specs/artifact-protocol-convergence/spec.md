## ADDED Requirements

### Requirement: foundation 阶段必须保留核心产物命名不变
foundation 阶段 SHALL 保持当前前端依赖的核心实验产物文件名和语义不变。

#### Scenario: 写出核心产物
- **WHEN** 新主线通过兼容执行壳完成一次运行
- **THEN** 实验目录 SHALL 继续包含 `portfolio_daily.csv`、`portfolio_trades.csv`、`portfolio_candidates.csv`、`perf.json`、`run_meta.json` 和 `manifest.json`
- **THEN** 这些文件的核心语义 SHALL 与锁定基线保持一致

### Requirement: 实验目录必须增加配置快照分层产物
foundation 阶段 SHALL 在不破坏旧文件的前提下，为实验目录新增分层配置快照产物。

#### Scenario: 写出新增配置快照
- **WHEN** 一次运行完成配置编译
- **THEN** 实验目录 SHALL 新增 `input_config.json`、`resolved_config.json` 和 `compiled_plan.json`
- **THEN** `manifest.json` SHALL 包含这些新增产物的映射

### Requirement: 实验目录必须记录基线比较结果
foundation 阶段 SHALL 为每次受治理的运行记录基线比较产物。

#### Scenario: 写出 baseline 比较报告
- **WHEN** 一次运行触发锁定基线比较
- **THEN** 实验目录 SHALL 包含 `baseline_compare.json`
- **THEN** `manifest.json` SHALL 包含该文件的产物映射

### Requirement: manifest 必须同时表达稳定产物与比较状态
系统 SHALL 要求 `manifest.json` 同时表达实验核心产物、配置快照和基线比较状态。

#### Scenario: manifest 记录完整
- **WHEN** manifest 写盘完成
- **THEN** manifest SHALL 至少包含 experiment_id、artifacts、config_snapshots、baseline_compare_status 和 schema_version
- **THEN** 前端或治理脚本 SHALL 能仅通过 manifest 发现实验目录中的稳定文件集合
