# weekly-five-state-regime-engine Specification

## Purpose
浠?2026-03-22 褰掓。鍙樻洿鎭㈠鐨勪富瑙勬牸銆?
## Requirements

### Requirement: Weekly five-state regime engine 只使用固定五项输入
系统 MUST 提供 `weekly_five_state` regime engine，并且该引擎只允许使用以下输入构建市场状态：

- 上证指数收盘价是否高于 `MA120`
- `MA120_today > MA120_20d_ago`
- `60d return > 0`
- `120d return > 0`
- `ADX(20)`

系统 MUST 禁止为该引擎引入额外宏观变量、额外广度变量、额外量能变量或未来数据。

#### Scenario: 固定输入集
- **WHEN** 系统以 `weekly_five_state` 运行
- **THEN** 状态分数仅来自上述五项输入

### Requirement: 周度打分模型
系统 SHALL 仅在周度观察点计算原始分数，默认周度观察点为每周最后一个交易日。

打分规则 SHALL 为：

- `close > MA120`：`+1`
- `MA120 slope > 0`：`+1`
- `60d return > 0`：`+1`
- `120d return > 0`：`+1`
- `ADX20 >= 25`：`+1`
- `20 <= ADX20 < 25`：`0`
- `ADX20 < 20`：`-1`

#### Scenario: 周度观察点打分
- **WHEN** 到达周度观察点
- **THEN** 系统 SHALL 计算 `market_state_score_raw`

### Requirement: 五态映射
系统 SHALL 将周度原始总分映射为五档状态：

- `5` -> `BULL_MAIN`
- `4` -> `TURN_STRONG`
- `3` -> `LIGHT_TREND`
- `1~2` -> `TURN_WEAK`
- `<=0` -> `DEFENSIVE`

#### Scenario: 满分映射为主趋势
- **WHEN** 周度原始总分等于 `5`
- **THEN** `market_state_5_raw = BULL_MAIN`

#### Scenario: 低分映射为空仓防守
- **WHEN** 周度原始总分小于等于 `0`
- **THEN** `market_state_5_raw = DEFENSIVE`

### Requirement: 周度防抖
系统 MUST 对周度原始状态应用防抖：

- 升级需要连续 `2` 个周度观察点确认
- 降级只需 `1` 个周度观察点

系统 SHALL 输出：

- `market_state_5_raw`
- `market_state_5`
- `market_state_transition_reason`

#### Scenario: 升级两周确认
- **WHEN** 候选升级状态连续两个周度观察点都成立
- **THEN** 平滑状态 SHALL 升级

#### Scenario: 降级立即生效
- **WHEN** 候选降级状态在当前周度观察点成立
- **THEN** 平滑状态 SHALL 在该周立即降级

### Requirement: 日频前向填充
系统 SHALL 将周度平滑状态前向填充到下一周观察点之前的全部交易日，以供主线每日路由与风险预算消费。

#### Scenario: 周内状态保持
- **WHEN** 当前交易日不是新的周度观察点
- **THEN** 当日 `market_state_5` SHALL 继承最近一个周度观察点的平滑状态

### Requirement: 五态风险预算映射
系统 SHALL 为五档状态输出固定风险预算乘子：

- `BULL_MAIN` -> `1.00`
- `TURN_STRONG` -> `0.70`
- `LIGHT_TREND` -> `0.40`
- `TURN_WEAK` -> 默认 `0.15`
- `DEFENSIVE` -> `0.00`

#### Scenario: 转弱风险预算
- **WHEN** `market_state_5 = TURN_WEAK`
- **THEN** `risk_budget_multiplier = 0.15`

### Requirement: 可审计输出
系统 SHALL 在 daily 产物中输出以下字段：

- `market_state_5_raw`
- `market_state_5`
- `market_state_score_raw`
- `risk_budget_multiplier`
- `weekly_observation_flag`
- `market_state_transition_reason`

#### Scenario: 运行完成后可审计
- **WHEN** 启用 `weekly_five_state` 的回测完成
- **THEN** 用户 MUST 能从产物中回答“今天是什么状态、为什么升级或降级”
