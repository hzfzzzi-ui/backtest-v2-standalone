## ADDED Requirements

### Requirement: semantic config 编译 SHALL 执行因子插入合同校验
当 `config_json` 中包含 `asset_context.moneyflow_overlay` 或 `asset_context.holding_exit_fragility` 时，semantic config 编译 SHALL 在逻辑校验阶段执行统一合同校验，并对非法接法返回结构化错误。

#### Scenario: semantic config 拒绝非法 moneyflow 接法
- **WHEN** `config_json.asset_context.moneyflow_overlay` 显式声明非法角色或动作组合
- **THEN** `validate_semantic_config_json` SHALL 抛出 400 错误并包含对应路径

### Requirement: runtime 请求构建 SHALL 执行同一套合同校验
当 `runtime_config_json` 或 `workbench_config` 携带 `asset_context.moneyflow_overlay` 或 `asset_context.holding_exit_fragility` 时，runtime 请求构建 SHALL 在实验启动前执行与 semantic 编译一致的合同校验。

#### Scenario: runtime_config_json 拒绝非法 holding_exit_fragility 接法
- **WHEN** `runtime_config_json.asset_context.holding_exit_fragility` 声明非法层级
- **THEN** `run_experiment_request_body` SHALL 在调用实验入口前返回 400 错误

### Requirement: resolver SHALL 保留可审计的局部无效状态
即使外部调用直接绕过 semantic 编译与 runtime 请求构建，hook resolver 仍 SHALL 对非法接法返回稳定的无效状态与原因，便于研究审计。

#### Scenario: 直接调用 holding fragility resolver 处理非法层级
- **WHEN** 直接调用 resolver 且 `apply_layer=candidate`
- **THEN** resolver SHALL 返回 `valid=false` 和稳定的 `invalid_layer` 状态

#### Scenario: 直接调用 moneyflow overlay resolver 处理非法角色动作组合
- **WHEN** 直接调用 resolver 且 `factor_role=context`、`mode=veto_bottom20`
- **THEN** resolver SHALL 返回 `gate_on=false` 和稳定的合同非法原因
