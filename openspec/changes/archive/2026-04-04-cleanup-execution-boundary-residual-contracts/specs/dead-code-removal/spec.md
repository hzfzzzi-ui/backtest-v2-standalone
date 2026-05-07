## ADDED Requirements

### Requirement: 执行边界清理不得先于替代路径稳定
系统 SHALL 在 `dead-code-removal` 中明确：执行边界残留清理必须以后继正式路径已经稳定落地为前提，不得提前删除仍承担 compat 作用的代码。

#### Scenario: 仍有 compat 作用的残留不得被提前删除
- **WHEN** 某段旧合同或 helper 仍承担 compat 或回退作用
- **THEN** 系统 MUST 不得将其提前删除
