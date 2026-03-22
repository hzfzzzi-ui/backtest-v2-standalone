## MODIFIED Requirements

### Requirement: 市场状态蒙版支持五态显示
系统 SHALL 允许结果图在 `weekly_five_state` 模式下显示五档市场状态蒙版：

- `BULL_MAIN`
- `TURN_STRONG`
- `LIGHT_TREND`
- `TURN_WEAK`
- `DEFENSIVE`

#### Scenario: 五态蒙版加载
- **WHEN** 实验使用 `weekly_five_state`
- **THEN** 前端 SHALL 根据 `market_state_5` 渲染对应阶段蒙版

### Requirement: 五态颜色语义可解释
系统 SHALL 为五态提供稳定且可解释的颜色语义，并在图例中明确标示状态名称与预算：

- `BULL_MAIN`：主趋势，100%
- `TURN_STRONG`：转强，70%
- `LIGHT_TREND`：轻仓趋势，40%
- `TURN_WEAK`：转弱，10%~20%
- `DEFENSIVE`：空仓防守，0%

#### Scenario: 图例可读
- **WHEN** 用户查看 weekly five-state 实验结果
- **THEN** 图上 SHALL 能直接识别各颜色对应的状态与风险预算
