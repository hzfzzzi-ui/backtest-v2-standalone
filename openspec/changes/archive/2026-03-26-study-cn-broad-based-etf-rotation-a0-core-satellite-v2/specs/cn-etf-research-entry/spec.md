## ADDED Requirements

### Requirement: cn_etf 研究入口必须支持 A0 V2 的受控标准替换候选
当 `cn_etf` 被宽基轮动模板 A0 V2 消费时，研究入口 MUST 允许在受控研究模式下引入以下标准替换候选：
- `159845.SZ` 作为 `512100.SH` 的标准中证1000替换候选
- `510880.SH` 作为 `512890.SH` 的标准红利替换候选

该能力 SHALL NOT 自动把这些标准 ETF 并入当前正式 `first_wave_core` 或 `first_wave_all` 主线。

#### Scenario: A0 V2 研究入口消费标准替换候选
- **WHEN** 用户运行 A0 V2 的替换 AB
- **THEN** 研究入口 MUST 允许解析上述两个标准 ETF
- **THEN** 研究入口 MUST 将其标记为 A0 V2 替换候选，而不是默认正式池

## MODIFIED Requirements

### Requirement: cn_etf 研究入口必须支持正式ETF beta sleeve语义
当 `cn_etf` 被 A 股 governed multi-sleeve 主线消费时，系统 MUST 将 `cn_etf` 研究入口明确标记为 `cn_etf_beta` 的正式来源之一，而 SHALL NOT 继续把它仅视为孤立的 ETF research entry。

当 `cn_etf` 被宽基轮动模板 A0 V2 消费时，研究入口 additionally MUST 能暴露：
- `template_asset_pool_version`
- `proxy_replacement_mode`
- `formal_replacement_pairs`

#### Scenario: ETF 研究入口进入 governed 主线
- **WHEN** Governor 启用 `cn_etf_beta` sleeve
- **THEN** 系统 MUST 允许从 `cn_etf` 研究入口解析正式 ETF beta 候选池
- **THEN** 相关产物 MUST 将该入口标识为 beta sleeve 来源而不是独立旁路实验

#### Scenario: A0 V2 明确替换关系
- **WHEN** 用户运行 A0 V2 的标准替换实验
- **THEN** `run_meta` 或等价产物 MUST 明确说明哪只标准 ETF 替换了哪只 proxy
