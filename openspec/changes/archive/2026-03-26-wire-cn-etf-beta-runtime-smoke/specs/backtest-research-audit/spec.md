## ADDED Requirements

### Requirement: 研究审计必须按 ETF 主线解释 cn_etf_beta 运行
当运行的 `asset_scope=cn_etf` 且 `governed_a_share.etf_beta.enabled=true` 时，研究审计 MUST 将该运行识别为 ETF beta 主线入口，显式输出 ETF `entry_type`、ETF coverage truth 与 ETF sleeve 证据链，不得混入股票 PIT lineage 解释。

#### Scenario: ETF 主线研究审计
- **WHEN** 用户运行 `cn_etf_first_wave_core` 或等价 ETF beta smoke
- **THEN** `research_audit` MUST 识别 `cn_etf_research_entry`
- **THEN** `research_audit` MUST 输出 ETF 覆盖窗口、ETF daily_table 与 ETF sleeve 选择摘要
