## ADDED Requirements

### Requirement: internal helper 不得依赖 API endpoint surface shim
系统 SHALL 保证 internal script helper 不依赖 `backend.api.endpoints._experiment_surface` 这类 API shim。

#### Scenario: internal helper 依赖下沉
- **WHEN** internal helper 需要读取实验目录、manifest 或 artifact path
- **THEN** 它 MUST 通过 core helper 完成，而不是 import API endpoint shim
