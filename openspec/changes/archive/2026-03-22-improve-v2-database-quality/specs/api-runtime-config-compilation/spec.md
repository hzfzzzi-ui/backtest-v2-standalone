## ADDED Requirements

### Requirement: Runtime config compile MUST 显式编译 v2 数据角色
系统 MUST 允许 runtime config compile 显式区分 `v2` 的 canonical 角色与 runtime compatibility 角色。编译后的 runtime config MUST 能表达 baseline 当前消费的是 `v1`、canonical `v2`，还是 runtime `v2`，并保留该选择的可审计元信息。

#### Scenario: 编译 baseline 使用 v2 runtime
- **WHEN** 用户或研究配置指定 baseline 使用 `v2` runtime compatibility 数据角色
- **THEN** compile 结果 MUST 明确记录该数据角色
- **THEN** compile 结果 MUST 指向 compat 层，而不是 canonical 全量表

#### Scenario: 编译 baseline 使用 canonical v2 做对照
- **WHEN** 用户或研究配置指定 baseline 使用 canonical `v2` 做对照实验
- **THEN** compile 结果 MUST 明确记录该数据角色
- **THEN** 运行产物 MUST 能区分该实验是 canonical 对照，而非正式 runtime 消费
