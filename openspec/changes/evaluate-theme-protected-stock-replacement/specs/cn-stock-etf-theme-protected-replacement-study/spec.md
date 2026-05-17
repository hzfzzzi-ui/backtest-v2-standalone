## ADDED Requirements

### Requirement: B0.1 保护替换研究 MUST 通过正式 study 入口运行

系统 MUST 提供 `cn_stock_etf/cn_stock_etf_theme_protected_replacement_v1` study，并且该 study MUST 能通过 `study_run` dry-run 和正式运行。

#### Scenario: 生成正式 study 执行计划

- **WHEN** 用户对该 study 执行 dry-run
- **THEN** 系统 MUST 输出窗口、variant、baseline、request payload 和 `study_meta`
- **THEN** variant MUST 明确为 research-only shadow，不得声明真实回测收益

### Requirement: 保护替换研究 MUST 明确不改变 V3 执行口径

系统 MUST 把本 study 标记为 research-only，并且 SHALL NOT 修改 baseline、股票池、ETF 池、排序主因子、信号时点、成交时点、退出规则、组合权重或防守仓定义。

#### Scenario: 写出运行结果

- **WHEN** study runner 完成一个窗口
- **THEN** 结果 MUST 包含 `research_only=true`
- **THEN** 结果 MUST 包含 `not_nav_backtest=true`
- **THEN** 结果 MUST 说明该窗口只审计 shadow plan，不代表真实 NAV 改善

### Requirement: 保护替换研究 MUST 校验证据输入与来源链路

系统 MUST 校验上一轮 V3 attribution bundle 中 B0.1 所需文件存在，并输出 source artifact dir、V3 baseline、stock component exp_id、ETF component exp_id 和缺失文件列表。

#### Scenario: 输入文件完整

- **WHEN** `b01_shadow_daily_plan.csv`、`b01_shadow_raw_triggers.csv`、`b01_shadow_filtered.csv`、`b0_shadow_daily_plan.csv` 和 `manifest.json` 均存在
- **THEN** runner MUST 写出 `source_files_checked` 通过的机器摘要

#### Scenario: 输入文件缺失

- **WHEN** 任一 required file 缺失
- **THEN** runner MUST 写出 `verdict= "inconclusive"`
- **THEN** runner MUST 在报告中列出缺失文件

### Requirement: 保护替换研究 MUST 输出窗口级触发、保护和集中度摘要

系统 MUST 对每个窗口输出 B0 计划行数、B0.1 计划行数、触发天数、unique buy/sell 标的数、cap 后潜在替换金额、主题分布、买入样例、卖出样例和保护过滤原因。

#### Scenario: 汇总 2016-2026 主窗口

- **WHEN** runner 处理 `1626`
- **THEN** 输出 MUST 包含 B0 到 B0.1 的行数减少量
- **THEN** 输出 MUST 包含 top buy themes、buy examples 和 sell examples
- **THEN** 输出 MUST 包含是否卖出核心科技主题的审计字段

### Requirement: 三窗口覆盖不足 MUST 被明确标注

如果 B0.1 输入证据覆盖范围不能完整覆盖 study window，系统 MUST 在窗口结论中标注 coverage risk，并且不得把该窗口作为 baseline 升级依据。

#### Scenario: 2012-2017 硬门槛窗口覆盖不足

- **WHEN** source artifact 的有效起点晚于 study window 起点
- **THEN** runner MUST 标记 `coverage_complete=false`
- **THEN** conclusion verdict MUST 为 `inconclusive`

### Requirement: study 输出 MUST 接入 conclusion registry 和 study journal

正式运行后，系统 MUST 写出 study conclusion registry 记录，并创建或更新一个 study journal round，让前端研究页面能检查本轮结果。

#### Scenario: 研究日志显示本轮结果

- **WHEN** study 完成运行
- **THEN** `research/study_journal/rounds/` MUST 包含本轮 round json
- **THEN** round evidence MUST 指向本轮 study output
- **THEN** auto summary SHOULD 能匹配到本轮 conclusion registry 记录
