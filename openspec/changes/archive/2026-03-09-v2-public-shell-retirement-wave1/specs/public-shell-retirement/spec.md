## ADDED Requirements

### Requirement: 已冻结且无 live caller 的公开旧壳必须按 wave 退役
系统 SHALL 按 wave 删除已冻结且无 live caller 的公开旧壳。每个 wave MUST 提供删除证据、retirement ledger 与基线门禁结果。

#### Scenario: wave1 删除旧 result route
- **WHEN** `/api/backtest_v2/results/{run_id}` 已确认无 live caller
- **THEN** 系统删除该路由与其 legacy payload helper，并以 ledger 记录删除依据

#### Scenario: wave1 删除空转 helper
- **WHEN** `_read_result()`、`_resolve_experiment_dir()`、`_preview_rejected_fields()`、`_load_runtime_cfg_obj()` 已确认无 live caller
- **THEN** 系统删除这些 helper 与对应 import，且不改变公开主表面
