## ADDED Requirements

### Requirement: 市场状态蒙版必须展示正式 regime 语义
当结果页加载使用正式 `market-regime-framework` 的实验时，图表蒙版 SHALL 直接展示正式 regime 输出，而不是假定当前颜色等同于 MA200 简化状态机。前端 MUST 能识别：
- `regime_engine`
- `market_state`
- `trade_mode`
- `regime_confidence`

#### Scenario: 正式框架实验显示正式状态
- **WHEN** 实验产物中的 `regime_engine = market_regime_framework`
- **THEN** 图表蒙版 MUST 以正式状态字段绘制阶段分区

### Requirement: 图表蒙版必须显示状态图例与语义说明
结果图在显示市场状态蒙版时 MUST 同时提供可见图例或状态说明，明确告知用户颜色表示的是：
- 市场结构状态
- 交易模式
- legacy/fallback 与正式框架的差异

#### Scenario: 用户无需猜测颜色含义
- **WHEN** 用户查看带阶段蒙版的结果图
- **THEN** 页面 MUST 存在可见图例，解释每种颜色对应的状态语义

### Requirement: 图表蒙版必须保留 legacy 兼容
当实验使用 `ma200_legacy` fallback 时，图表蒙版 SHALL 继续显示现有状态段，但 MUST 明确标记其为 legacy regime，而不是正式多因子 regime。

#### Scenario: legacy 实验显示兼容标签
- **WHEN** 实验产物中的 `regime_engine = ma200_legacy`
- **THEN** 图表蒙版或图例 MUST 显示该实验正在使用 legacy MA200 状态机
