## ADDED Requirements

### Requirement: 共享 experiment artifact access 必须位于 core helper
系统 SHALL 将实验目录、manifest 与 declared artifact path 的共享访问能力放在 core/shared helper 中，而不是放在 API endpoint shim 中。

#### Scenario: live callers 迁移到 core helper
- **WHEN** `backtest_v2.py`、`_experiment_history.py`、`internal_script_helper.py` 需要读取 experiment 目录或 manifest
- **THEN** 它们 MUST 依赖 core helper，而不是 `backend.api.endpoints._experiment_surface`

#### Scenario: shim 删除后主表面不变
- **WHEN** `_experiment_surface.py` 被删除
- **THEN** manifest-driven artifact 读取与 experiment history 行为保持不变
