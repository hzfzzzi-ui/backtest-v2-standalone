## ADDED Requirements

### Requirement: Runtime config compile 必须支持从单一锚点编译多 sleeve 运行配置
当输入配置显式启用 `governed_a_share.stock_alpha_core` 与 `governed_a_share.etf_beta` 时，runtime config compile MUST 能从单一前端锚点编译出 unified runtime 所需的组合级配置和 sleeve 级配置片段。编译流程 SHALL NOT 因存在 ETF sleeve 就把全局 `asset_scope` 粗暴切换为 `cn_etf`，也 SHALL NOT 因存在股票 sleeve 就丢弃 ETF 运行配置。

#### Scenario: 编译 A股个股+ETF 统一锚点
- **WHEN** 系统编译 `cfg_cn_stock_etf_v1`
- **THEN** compile 结果 MUST 同时包含组合级 governed 配置和两个 sleeve 的最小运行片段
- **THEN** compile 结果 MUST 可被统一运行入口直接消费

#### Scenario: 单 sleeve 旧配置保持原行为
- **WHEN** 系统继续编译仅包含股票 alpha 或仅包含 ETF beta 的旧配置
- **THEN** compile 结果 MUST 保持当前单 sleeve 行为
- **THEN** 系统 SHALL NOT 因支持 unified runtime 而改变既有单资产运行语义
