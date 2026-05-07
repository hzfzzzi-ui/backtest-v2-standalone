## ADDED Requirements

### Requirement: 系统 SHALL 定义统一的因子插入合同
系统 SHALL 为 research/runtime hook 使用的因子定义统一的 canonical 角色合同。合同至少必须覆盖 `rank`、`veto`、`context`、`lifecycle`、`state` 五类角色，并为每类角色定义允许的插入层与动作集合。

#### Scenario: moneyflow overlay 的显式角色与动作一致
- **WHEN** 配置为 `moneyflow_overlay.factor_role=context` 且 `mode=soft_weight`
- **THEN** 合同校验 SHALL 通过

#### Scenario: holding exit fragility 的显式角色与层级一致
- **WHEN** 配置为 `holding_exit_fragility.factor_role=lifecycle` 且 `apply_layer=holding_exit`
- **THEN** 合同校验 SHALL 通过

### Requirement: 系统 SHALL 拒绝角色与插入层不匹配的接法
当因子角色与目标插入层不匹配时，系统 SHALL 生成稳定的拒绝结果，不得 silent fallback 为默认接法。

#### Scenario: lifecycle 因子被接到 candidate 层
- **WHEN** 配置为 `holding_exit_fragility.factor_role=lifecycle` 且 `apply_layer=candidate`
- **THEN** 系统 SHALL 返回明确的非法层级原因

#### Scenario: state 因子被接到 moneyflow overlay
- **WHEN** 配置为 `moneyflow_overlay.factor_role=state`
- **THEN** 系统 SHALL 返回明确的非法角色原因

### Requirement: 系统 SHALL 拒绝角色与动作不匹配的接法
当因子角色与动作语义不匹配时，系统 SHALL 拒绝该接法。

#### Scenario: context 因子尝试使用 veto 动作
- **WHEN** 配置为 `moneyflow_overlay.factor_role=context` 且 `mode=veto_bottom20`
- **THEN** 系统 SHALL 返回明确的非法动作原因

#### Scenario: lifecycle 因子尝试使用 ranking tiebreak 动作
- **WHEN** lifecycle 因子被声明为 `mode=tiebreak`
- **THEN** 系统 SHALL 返回明确的非法动作原因
