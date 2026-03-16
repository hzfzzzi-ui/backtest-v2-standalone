## ADDED Requirements

### Requirement: Runtime config compile 必须先编译 asset boundary
系统 MUST 在 runtime config compile 的第一阶段解析 canonical `asset_scope`、`asset_profile` 和 `market_profile`，然后才允许 universe、signal、risk/exit 和 bundle compile 继续执行。

#### Scenario: 编译桌面草稿
- **WHEN** 系统从桌面 config draft 编译 runtime config
- **THEN** compile 流程 MUST 先产出 canonical asset boundary
- **THEN** 后续各配置域模块 MUST 消费这份 boundary，而不是各自重复推断

#### Scenario: 编译 study 运行请求
- **WHEN** 系统从 study 定义编译 runtime config
- **THEN** study 提供的 asset scope MUST 进入 compile 第一阶段
- **THEN** 最终 runtime config 和 semantic bundle MUST 记录该 canonical asset boundary

### Requirement: Config compile 不得再把 A 股默认散落到各配置域
系统 MUST 收口当前散落在 universe、signal、risk/exit 和 builtin config library 中的 A 股隐式默认，使其由 canonical asset boundary 或对应 A 股 adapter 明确提供。

#### Scenario: 编译当前 A 股 baseline
- **WHEN** 系统编译 `baseline_V10.1`
- **THEN** compile 后的 canonical runtime config MUST 与当前 `V10.1` 语义等价
- **THEN** 任何差异 MUST 被视为行为漂移，而不是结构整理
