## ADDED Requirements

### Requirement: ResultsWorkbenchSnapshot 必须支持 unified runtime 组合摘要
当实验属于 `cn-stock-etf-unified-runtime-entry` 时，`ResultsWorkbenchSnapshot` MUST 同时提供组合级摘要与 sleeve 级摘要。前端 SHALL 能区分：

- 组合级净值与绩效
- `cn_stock_trend_alpha_core` 摘要
- `cn_etf_beta` 摘要

系统 SHALL NOT 仅通过一个全局 `asset_scope` 或单条 governed snapshot，假装整个实验已经表达了双 sleeve 运行。

#### Scenario: 统一运行结果进入 snapshot
- **WHEN** 页面壳加载 unified runtime 实验
- **THEN** snapshot MUST 包含组合级 summary
- **THEN** snapshot MUST 包含股票 alpha sleeve 与 ETF beta sleeve 的最小摘要字段

#### Scenario: 前端区分组合级与 sleeve 级结果
- **WHEN** 结果工作台渲染 unified runtime 实验
- **THEN** 前端 MUST 能分别展示组合级与 sleeve 级结果
- **THEN** 前端 SHALL NOT 把其中一条 sleeve 的结果误当成整个组合结果
