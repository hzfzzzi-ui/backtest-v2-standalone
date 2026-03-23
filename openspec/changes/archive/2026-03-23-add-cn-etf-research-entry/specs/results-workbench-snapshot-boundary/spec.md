## ADDED Requirements

### Requirement: 桌面研究页必须按 `cn_etf` 资产上下文切换 ETF 研究入口文案
当当前配置草稿、snapshot 或 active experiment 的 `assetContext.asset_scope='cn_etf'` 时，桌面研究页 MUST 切换为 ETF 研究入口文案，并显示 ETF 专属提示。页面 SHALL NOT 继续把“股票池 / 行业 / PIT 成分”作为默认文案真相。

#### Scenario: ETF 配置页切换入口文案
- **WHEN** 用户将资产范围切换为 `cn_etf`
- **THEN** 页面 MUST 把“股票池”切换为 ETF 资产或标的语义
- **THEN** 页面 MUST 隐藏或禁用股票专属过滤控件与股票 PIT 提示

#### Scenario: ETF 结果页渲染 ETF 提示
- **WHEN** 当前实验 `assetContext.asset_scope='cn_etf'`
- **THEN** 结果工作台 MUST 显示 ETF 资产标签与 ETF 研究提示
- **THEN** 工作台 SHALL NOT 使用股票成分股 lineage 文案解释该实验

### Requirement: ResultsWorkbenchSnapshot 必须携带 ETF 研究覆盖与口径摘要
当结果属于 `cn_etf` 时，页面壳 MUST 将 ETF 研究摘要推入 `ResultsWorkbenchSnapshot`，至少包含 ETF 名单、批次、覆盖起止日期、数据表和价格语义，以便工作台和旧壳兼容层能用统一 snapshot 渲染 ETF 结果。

#### Scenario: ETF 运行摘要进入 snapshot
- **WHEN** 页面壳加载 `cn_etf` 实验结果
- **THEN** `ResultsWorkbenchSnapshot` MUST 携带 `etf_symbols`、`etf_batch`、`coverage_start`、`coverage_end`、`daily_table` 和 `price_series_semantics`
- **THEN** 工作台 MUST 基于这些字段展示 ETF 研究摘要
