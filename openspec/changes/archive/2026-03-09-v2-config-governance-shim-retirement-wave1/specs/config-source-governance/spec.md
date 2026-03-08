## ADDED Requirements

### Requirement: runtime config source resolution 在 helper 下沉后必须保持行为不变
系统 SHALL 在下沉 shared helper 后继续保持 config provenance、resolved config mode 与 conflict policy 行为不变。

#### Scenario: config source resolution 行为保持稳定
- **WHEN** 系统使用 core helper 解析 config source
- **THEN** 产生的 `config_source`、`resolved_config_mode`、`resolved_config_hash` 与 `config_conflict_policy` 不得发生语义漂移
