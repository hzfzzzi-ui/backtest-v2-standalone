## ADDED Requirements

### Requirement: Universe resolver 必须支持 `cn_etf` 的受控 `CUSTOM` 解析
当 `asset_scope='cn_etf'` 且 `universe_mode='CUSTOM'` 时，resolver MUST 只从正式 ETF 目录中解析 ETF 代码，并返回 ETF 资产元数据。resolver SHALL NOT 复用 A 股个股的股票池查询、股票行业筛选或指数成分股逻辑。

#### Scenario: 解析单只 ETF
- **WHEN** `asset_scope='cn_etf'`、`universe_mode='CUSTOM'` 且 `symbols=['512100.SH']`
- **THEN** resolver MUST 返回标准化后的 `512100.SH`
- **THEN** 返回的 `meta` MUST 包含 `asset_scope='cn_etf'` 与 ETF 目录来源标识

#### Scenario: 拒绝未纳入目录的 ETF
- **WHEN** `asset_scope='cn_etf'`、`universe_mode='CUSTOM'` 且 `symbols` 包含未纳入首波目录的代码
- **THEN** resolver MUST 返回显式错误
- **THEN** 系统 SHALL NOT 静默保留未知 symbol 或回退到股票 resolver

### Requirement: Universe resolver 必须支持 ETF 预设组展开
系统 MUST 支持把 ETF 研究 preset 展开为受控 symbol 列表并进入 `cn_etf` resolver。预设组至少包括 `cn_etf_first_wave_core` 和 `cn_etf_first_wave_all`，且展开结果 MUST 与正式 ETF 目录一致。

#### Scenario: 核心批次 ETF 预设组展开
- **WHEN** 运行配置声明 `asset_scope='cn_etf'` 且 preset 为 `cn_etf_first_wave_core`
- **THEN** resolver 或其上游编译链路 MUST 展开出核心批次 6 只 ETF
- **THEN** resolver 返回的 `meta` MUST 暴露 `preset_id='cn_etf_first_wave_core'`

#### Scenario: 全批次 ETF 预设组展开
- **WHEN** 运行配置声明 `asset_scope='cn_etf'` 且 preset 为 `cn_etf_first_wave_all`
- **THEN** resolver 或其上游编译链路 MUST 展开出首波全部 9 只 ETF
- **THEN** 展开结果 MUST 不包含目录外 symbol
