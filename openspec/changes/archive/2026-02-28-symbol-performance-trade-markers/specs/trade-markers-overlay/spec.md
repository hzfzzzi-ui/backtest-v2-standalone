## ADDED Requirements

### Requirement: 个股对照图必须叠加买卖箭头标记
系统 MUST 在个股对照曲线上叠加交易标记：买入为绿色上箭头，卖出为红色下箭头，标记时间以成交日期为准。

#### Scenario: 选中个股且存在交易记录
- **WHEN** 用户选择某个 symbol 且该 symbol 存在 BUY/SELL 成交
- **THEN** 图表 SHALL 在对应日期绘制买卖箭头
- **THEN** BUY 标记 SHALL 为绿色上箭头，SELL 标记 SHALL 为红色下箭头

### Requirement: 标记必须支持与基准对照同时展示
系统 MUST 在“个股 vs 基准”同图展示场景下保持时间轴一致，交易标记与价格点对齐，不得破坏现有基准对照能力。

#### Scenario: 打开基准对照并展示个股标记
- **WHEN** 用户在个股模式下启用基准显示
- **THEN** 个股曲线、基准曲线与交易标记 SHALL 使用统一时间轴
- **THEN** 缩放与平移 SHALL 同步作用于曲线与标记

### Requirement: 标记渲染必须按当前筛选个股隔离
系统 MUST 仅渲染当前选中 symbol 的交易标记，避免多标的混叠造成误读。

#### Scenario: 切换选中 symbol
- **WHEN** 用户从 symbol A 切换到 symbol B
- **THEN** 图表 SHALL 清除 A 的标记并加载 B 的标记
- **THEN** 不得显示非当前 symbol 的交易箭头
