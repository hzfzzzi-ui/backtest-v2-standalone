## ADDED Requirements

### Requirement: Runtime config 编译必须按配置域拆分
系统 MUST 将 workbench/runtime config 编译按配置域拆分为独立模块。`runner_config_helpers.py` SHALL 只保留 façade 和总装配职责，具体编译 MUST 至少分为 `base`、`universe`、`signal`、`risk-exit` 和 `bundle` 五类模块。

#### Scenario: 编译 workbench 草稿
- **WHEN** 系统从 workbench 草稿编译 runtime config
- **THEN** façade MUST 调度配置域模块逐块生成 canonical runtime config
- **THEN** 单一 helper 文件 SHALL NOT 再同时承载所有配置域的编译细节

#### Scenario: 编译 locked candidate 请求
- **WHEN** 系统接收 locked candidate 执行请求
- **THEN** 相关 candidate 上下文构建 MUST 与通用 config compile 分层维护
- **THEN** façade MUST 仍提供统一的请求入口

### Requirement: 配置域模块必须返回 canonical partial config
系统 MUST 要求各配置域模块返回可合并的 canonical partial config，而不是直接在任意位置随意修改整棵运行配置。总装配 SHALL 仅发生在 façade 层。

#### Scenario: universe 模块编译
- **WHEN** universe 编译模块处理时间范围、股票池和 filters
- **THEN** 模块 MUST 仅返回 universe 相关 canonical 配置片段
- **THEN** 模块 SHALL NOT 直接写入 signal、risk 或 artifact 相关字段

#### Scenario: signal 模块编译
- **WHEN** signal 编译模块处理 strategy_pack、signal_generation 和 multi-alpha payload
- **THEN** 模块 MUST 只返回 signal 相关 canonical 配置片段
- **THEN** 其他域的 merge MUST 由 façade 层完成

### Requirement: 编译模块化不得改变 runtime config 语义
系统 MUST 保持拆分前后的 runtime config 语义一致。模块化 SHALL NOT 改变字段名、默认值解释或由 workbench 草稿推导出的运行时口径。

#### Scenario: baseline compile 对照
- **WHEN** 系统对 `baseline_V10.1` 运行一次拆分前后 compile 对照
- **THEN** canonical runtime config 和 semantic bundle MUST 保持等价
- **THEN** 任一差异都 MUST 被视为行为漂移而不是“结构性优化”
