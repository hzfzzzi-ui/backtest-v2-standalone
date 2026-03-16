# api-runtime-config-compilation Specification

## Purpose
定义 runtime config compile 的模块边界，确保 `runner_config_helpers.py` 只保留 facade 与总装配职责，具体配置域编译拆分到独立模块，同时不改变 `baseline_V10.1` 的 runtime config 语义。
## Requirements
### Requirement: Runtime config 编译必须按配置域拆分
系统 MUST 将 workbench/runtime config 编译按配置域拆分为独立模块。`runner_config_helpers.py` SHALL 只保留 facade 和总装配职责，具体编译 MUST 至少拆分为 `base`、`universe`、`signal`、`risk-exit` 和 `bundle` 五类模块。

#### Scenario: 编译 workbench 草稿
- **WHEN** 系统从 workbench 草稿编译 runtime config
- **THEN** facade MUST 调度配置域模块逐块生成 canonical runtime config
- **THEN** 单一 helper 文件 SHALL NOT 再同时承载所有配置域的编译细节

#### Scenario: 编译 locked candidate 请求
- **WHEN** 系统接收 locked candidate 执行请求
- **THEN** 相关 candidate 上下文构建 MUST 与通用 config compile 分层维护
- **THEN** facade MUST 仍提供统一的请求入口

### Requirement: 配置域模块必须返回 canonical partial config
系统 MUST 要求各配置域模块返回可合并的 canonical partial config，而不是直接在任意位置随意修改整棵运行配置。总装配 SHALL 仅发生在 facade 层。

#### Scenario: universe 模块编译
- **WHEN** universe 编译模块处理时间范围、股票池和 filters
- **THEN** 模块 MUST 仅返回 universe 相关 canonical 配置片段
- **THEN** 模块 SHALL NOT 直接写入 signal、risk 或 artifact 相关字段

#### Scenario: signal 模块编译
- **WHEN** signal 编译模块处理 `strategy_pack`、`signal_generation` 和 multi-alpha payload
- **THEN** 模块 MUST 只返回 signal 相关 canonical 配置片段
- **THEN** 其他域的 merge MUST 由 facade 层完成

### Requirement: 编译模块化不得改变 runtime config 语义
系统 MUST 保持拆分前后的 runtime config 语义一致。模块化 SHALL NOT 改变字段名、默认值解释或由 workbench 草稿推导出的运行时口径。

#### Scenario: baseline compile 对照
- **WHEN** 系统对 `baseline_V10.1` 运行一次拆分前后 compile 对照
- **THEN** canonical runtime config 和 semantic bundle MUST 保持等价
- **THEN** 任一差异都 MUST 被视为行为漂移，而不是“结构性优化”

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

