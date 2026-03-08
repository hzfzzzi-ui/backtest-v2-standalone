## ADDED Requirements

### Requirement: 运行前 SHALL 解析出唯一 runtime config json
系统 MUST 在运行或执行预览前，将当前配置来源解析为一份唯一的 runtime config json，并将其作为后端编译与执行的唯一真相。系统 MUST NOT 允许 `config_id` 与 `workbench_config` 并行决定最终运行配置。

#### Scenario: 草稿运行
- **WHEN** 用户未加载配置或已编辑成脏草稿后点击运行
- **THEN** 前端 SHALL 提交一份基于当前草稿解析得到的 runtime config json
- **THEN** 后端 SHALL 仅以该 runtime config json 作为编译输入

#### Scenario: 已保存配置运行
- **WHEN** 用户加载一份已保存配置且未再修改后点击运行
- **THEN** 前端 SHALL 先解析出对应 runtime config json 再发起运行
- **THEN** 请求中如包含 `config_id`，该字段 SHALL 仅用于 provenance，不得覆盖 runtime config json

### Requirement: preview 与 run SHALL 共享相同 handoff 规则
`execution_preview` 与 `run_async` MUST 使用同一个 runtime config resolver、同一套冲突处理规则和同一套 provenance 字段。

#### Scenario: 同一来源下 preview 与 run 一致
- **WHEN** 用户对同一配置先执行预览再执行正式运行
- **THEN** preview 与 run SHALL 使用同一份解析后的 runtime config json
- **THEN** 两者返回的来源元信息 SHALL 一致
