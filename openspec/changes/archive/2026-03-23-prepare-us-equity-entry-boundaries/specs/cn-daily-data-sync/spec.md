## ADDED Requirements

### Requirement: 市场日更同步器必须显式声明 `cn_a_equity` adapter
系统 MUST 将当前日更同步器视为 `cn_a_equity` 专用 adapter，并在状态记录、调度和对外摘要中显式暴露该 `asset_scope`。该同步器 SHALL NOT 再以“未声明资产时的全市场默认同步器”身份存在。

#### Scenario: 查询当前 A 股同步器
- **WHEN** 调用当前市场日更同步服务且 `asset_scope='cn_a_equity'`
- **THEN** 系统 MUST 返回当前 A 股同步摘要
- **THEN** 同步记录 MUST 明确包含 `asset_scope='cn_a_equity'`

### Requirement: 未实现同步 adapter 的资产必须返回 unsupported
系统 MUST 对尚未实现 market data sync adapter 的资产返回显式 unsupported 状态，而 SHALL NOT 复用 A 股最新日期或状态记录伪装为该资产的 freshness。

#### Scenario: 查询美股个股同步状态
- **WHEN** 调用市场同步服务且 `asset_scope='us_equity'`
- **THEN** 系统 MUST 返回 unsupported 状态
- **THEN** 系统 SHALL NOT 读取或返回 A 股同步日期作为美股状态
