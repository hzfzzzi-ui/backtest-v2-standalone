## MODIFIED Requirements

### Requirement: UI 支持选择 weekly five-state engine
系统 SHALL 在 regime 配置 UI 中提供 `regime_engine.engine` 选择项：

- `ma200_legacy`
- `weekly_five_state`

#### Scenario: 选择 weekly five-state
- **WHEN** 用户在工作台选择 `weekly_five_state`
- **THEN** 配置草稿 SHALL 正确序列化该 engine

### Requirement: UI 只暴露低自由度参数
当 `regime_engine.engine = weekly_five_state` 时，UI MUST 保持低自由度。

允许暴露：

- engine 选择
- `TURN_WEAK` 风险预算
- 基准指数只读展示为 `000001.SH`

不得暴露：

- 任意新增宏观参数
- 任意额外趋势/广度/量能窗口
- 任意复杂状态阈值面板

#### Scenario: 周度五态 UI 保持简单
- **WHEN** 用户切换到 `weekly_five_state`
- **THEN** 界面 SHALL 显示固定规则说明，而不是大量可调参数
