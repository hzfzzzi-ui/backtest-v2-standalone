## ADDED Requirements

### Requirement: 桌面端正式运行链只得提交 FrontendSemanticConfig 正式字段
桌面端 `config_workspace`、`run_orchestration` 和 `save_orchestration` 在向后端提交 `config_json` 时 MUST 构造严格符合 `FrontendSemanticConfig` 的正式 payload。该 payload SHALL NOT 透传 `asset_context`、`unified_runtime`、历史 `data_role` 包装字段或其他仅供前端本地 workspace 使用的遗留字段。

#### Scenario: 从已加载实验草稿发起运行
- **WHEN** 用户加载一个包含历史兼容字段的实验配置并直接点击运行
- **THEN** 前端提交给后端的 `config_json` MUST 只保留正式 schema 允许的字段
- **THEN** 前端 SHALL NOT 因透传 `asset_context`、`unified_runtime` 或等效遗留字段导致后端 schema 校验失败

#### Scenario: 从当前草稿保存基线
- **WHEN** 用户对当前桌面草稿执行保存基线或其他正式配置提交动作
- **THEN** 提交载荷 MUST 使用与运行链一致的正式字段裁剪规则
- **THEN** 前端本地 workspace 辅助字段 MAY 继续保留在内存态，但 SHALL NOT 进入后端正式接口 payload
