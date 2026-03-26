## ADDED Requirements

### Requirement: 桌面研究台必须提供全局控制层
桌面研究台 MUST 在顶栏下方提供正式的 `Global Control Strip`，用于承载全系统共享的控制与摘要。该控制层 MUST 至少包含：
- `asset_scope`
- 研究时间范围
- `market_regime_engine` 摘要与编辑入口
- `global_portfolio_governor` 摘要与编辑入口

该控制层 SHALL NOT 被实现为某个资产特化抽屉的一部分。

#### Scenario: 页面加载时展示全局控制层
- **WHEN** 用户打开桌面研究台
- **THEN** 页面 MUST 在顶栏下方展示全局控制层
- **THEN** 左侧抽屉 SHALL NOT 再单独承担全局资产范围、Regime 或 Governor 的主编辑职责

### Requirement: 全局控制层必须在不同资产范围下保持稳定
当用户在 `cn_a_equity`、`cn_etf` 或未来其他正式资产范围之间切换时，顶层全局控制层 MUST 保持稳定的布局和字段语义。资产切换 MAY 改变摘要内容，但 SHALL NOT 使顶层控制层整体消失或退化为资产特化配置。

#### Scenario: 从 A股个股切换到 A股ETF
- **WHEN** 用户将 `asset_scope` 从 `cn_a_equity` 切换到 `cn_etf`
- **THEN** 页面顶层全局控制层 MUST 继续展示资产范围、时间范围、Regime 和 Governor
- **THEN** 资产切换带来的差异 MUST 主要体现在左侧特化抽屉而不是顶层控制层

### Requirement: 全局控制层必须优先展示摘要而不是完整表单
`Global Control Strip` MUST 以摘要优先的方式展示公共配置，避免页面顶部变成完整巨型表单。页面 MAY 提供展开、抽屉或弹层形式编辑详细字段，但默认视图 MUST 优先展示当前摘要与状态。

#### Scenario: 顶层默认视图保持紧凑
- **WHEN** 用户首次进入页面或未主动展开高级编辑
- **THEN** 顶部全局控制层 MUST 以摘要态展示关键字段
- **THEN** 页面 SHALL NOT 在顶部默认展开全部 Regime 与 Governor 详细配置
