## ADDED Requirements

### Requirement: ResultsWorkbenchSnapshot 必须携带 assetContext
系统 MUST 在 `ResultsWorkbenchSnapshot` 中提供统一的 `assetContext`，至少包含 `asset_scope`、`asset_profile_id`、`asset_family` 和 `market_profile_id`，并作为工作台展示的正式资产真相。

#### Scenario: 页面壳加载实验结果
- **WHEN** 页面壳完成 manifest、surface 和 section 的拉取
- **THEN** 页面壳 MUST 组装包含 `assetContext` 的 snapshot
- **THEN** Vue workbench MUST 通过 snapshot 而不是其他隐式字段理解当前资产归属

#### Scenario: 切换实验时更新资产上下文
- **WHEN** 用户切换到另一个实验
- **THEN** 页面壳 MUST 连同结果 snapshot 一起更新 `assetContext`
- **THEN** 工作台 SHALL NOT 沿用上一个实验的市场语义

### Requirement: 前端不得再从 A 股专属字段推断市场语义
系统 MUST 禁止桌面页壳、旧控制器和 workbench 组件从行业、停牌、benchmark 名称或 A 股专有字段反推资产类型。资产归属 MUST 只来自 `assetContext`。

#### Scenario: 渲染 A 股实验
- **WHEN** 当前实验属于 A 股 profile
- **THEN** 前端 MAY 基于 `assetContext` 显示 A 股专属文案或标签
- **THEN** 前端 SHALL NOT 仅因为存在行业/ST 字段就推断该实验一定是 A 股
