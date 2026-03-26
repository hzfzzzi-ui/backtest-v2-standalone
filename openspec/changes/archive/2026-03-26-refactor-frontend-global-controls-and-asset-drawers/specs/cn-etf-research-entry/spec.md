## ADDED Requirements

### Requirement: cn_etf 前端入口必须按 cn_etf_beta 语义展示特化配置
当当前配置草稿或实验结果属于 `asset_scope='cn_etf'` 时，桌面研究台 MUST 以 `cn_etf_beta` 的正式语义展示左侧特化配置。页面 SHALL NOT 继续把 ETF 模式展示成股票池、个股排序或 PIT 研究的变体。

#### Scenario: 打开 ETF 配置抽屉
- **WHEN** 用户在桌面研究台中切换到 `asset_scope='cn_etf'`
- **THEN** 左侧抽屉 MUST 展示 ETF 候选池、ETF beta 排序和调仓相关配置
- **THEN** 页面 SHALL NOT 以“股票池 / 行业 / 个股排序”作为 ETF 配置的主文案

### Requirement: cn_etf 结果摘要必须突出 ETF beta 运行语义
当结果属于 `cn_etf_beta` 时，结果摘要 MUST 显示 ETF 候选池、运行时选中 ETF、slot cap 或未部署原因等 ETF beta 特有语义。页面 SHALL NOT 仅复用股票回测摘要文案。

#### Scenario: 渲染 ETF beta 结果概览
- **WHEN** 用户加载 `cn_etf_beta` 实验结果
- **THEN** 结果概览 MUST 显示 ETF beta 的候选池和运行时部署语义
- **THEN** 页面 SHALL NOT 仅用股票交易统计来解释该实验
