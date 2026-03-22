## ADDED Requirements

### Requirement: Regime UI 必须区分 legacy 模式与正式框架模式
配置工作台中的市场状态/信号面板 MUST 显式区分：
- `ma200_legacy`
- `market_regime_framework`

系统 MUST 不再把 MA200 参数直接当成唯一 regime 配置，而应首先暴露 `regime_engine` 选择。

#### Scenario: 用户选择 legacy 模式
- **WHEN** 用户在 UI 中选择 `ma200_legacy`
- **THEN** 工作台仅显示现有 MA200/斜率相关配置，并隐藏正式框架特征组

#### Scenario: 用户选择正式框架模式
- **WHEN** 用户在 UI 中选择 `market_regime_framework`
- **THEN** 工作台 MUST 显示正式框架的输入块、persistence 参数和 fallback 配置

### Requirement: Regime UI 必须按输入块分层展示参数
当正式框架启用时，UI SHALL 将配置至少拆分为以下分层块：
- 趋势块
- 风险块
- 广度块
- 参与度块
- persistence / hysteresis
- fallback / 审计

#### Scenario: 正式框架参数分层展示
- **WHEN** 用户展开市场状态配置
- **THEN** 工作台 MUST 能按输入块查看和编辑参数，而不是把所有 regime 参数堆在一个均线面板里

### Requirement: UI 配置编译必须保留 regime engine 唯一真相
前端配置草稿、后端 API payload 和运行时编译结果 MUST 保持同一个 `regime_engine` 与参数结构，不得在前端推导、重命名或隐式补默认值导致字段漂移。

#### Scenario: 配置往返一致
- **WHEN** 用户保存并重新加载一条使用正式框架的实验
- **THEN** `regime_engine`、输入块参数和 persistence 参数 MUST 被完整回填
