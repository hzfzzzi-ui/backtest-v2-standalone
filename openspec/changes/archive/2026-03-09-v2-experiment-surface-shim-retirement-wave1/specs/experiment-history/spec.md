## ADDED Requirements

### Requirement: experiment history 读面可在删除 surface shim 后继续工作
系统 SHALL 在删除 `_experiment_surface.py` 后继续通过 manifest 驱动 experiment history、compare 与 report 读取。

#### Scenario: history 与 compare 继续基于 manifest
- **WHEN** `_experiment_surface.py` 被删除
- **THEN** `list_experiments`、`compare_experiments`、`get_experiment_report` 仍可正常工作
