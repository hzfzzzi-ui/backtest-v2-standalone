## ADDED Requirements

### Requirement: 左侧抽屉必须按资产范围切换特化模块
桌面研究台的左侧抽屉 MUST 以 `asset_scope` 为主驱动，展示当前资产或 sleeve 的特化配置模块。左侧抽屉 SHALL NOT 再同时承载全局 Regime、Governor 和所有资产通用配置。

#### Scenario: A股个股模式显示股票特化配置
- **WHEN** 当前 `asset_scope='cn_a_equity'`
- **THEN** 左侧抽屉 MUST 展示股票范围、股票 alpha 参数及其相关局部控制
- **THEN** 左侧抽屉 SHALL NOT 把 ETF beta 特有的调仓或排序逻辑作为默认表单展示

#### Scenario: A股ETF模式显示ETF特化配置
- **WHEN** 当前 `asset_scope='cn_etf'`
- **THEN** 左侧抽屉 MUST 展示 ETF 候选池、ETF beta 排序、调仓或定投相关特化配置
- **THEN** 左侧抽屉 SHALL NOT 继续以“股票池 / 个股排序 / PIT 成分”作为默认文案和表单结构

### Requirement: 左侧主导航不得再以 S1-S9 作为唯一正式组织方式
桌面研究台 MAY 继续保留 `S1-S9` 兼容入口，但正式主导航 MUST 改为按资产特化模块组织。`S1-S9` SHALL NOT 继续作为页面架构唯一真相源。

#### Scenario: 新布局优先展示资产特化导航
- **WHEN** 用户进入新版桌面研究台
- **THEN** 页面 MUST 优先展示资产特化导航或与之等价的模块导航
- **THEN** 若保留 `S1-S9` 兼容入口，其角色 MUST 被限制为过渡层而不是正式主结构

### Requirement: 左侧抽屉切换不得改变全局公共控制语义
当左侧抽屉在股票 alpha、ETF beta 或其他特化模块之间切换时，页面 MUST 保持顶层公共控制的真相不变。左侧抽屉 SHALL NOT 覆盖、复制或静默重写顶层 `Regime` 与 `Governor` 配置。

#### Scenario: 切换到 ETF beta 抽屉
- **WHEN** 用户从股票 alpha 配置切换到 ETF beta 配置
- **THEN** 左侧抽屉 MUST 仅切换资产特化参数
- **THEN** 顶层 Regime 和 Governor 摘要 MUST 保持同一套全局真相
