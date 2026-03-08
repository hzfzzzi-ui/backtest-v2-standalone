## ADDED Requirements

### Requirement: 实验读取主面必须围绕 experiment manifest
实验历史、对比与产物读取 SHALL 围绕 `experiment_id + manifest` 组织；当前系统 MUST 不再把 legacy result payload 视为公开读取主面。

#### Scenario: 实验历史继续基于 manifest 工作
- **WHEN** 系统删除 legacy result route
- **THEN** 实验历史、对比与产物读取能力仍通过 manifest 和 declared artifacts 正常工作
