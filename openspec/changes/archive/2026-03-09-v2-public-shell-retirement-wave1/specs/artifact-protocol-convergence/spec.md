## ADDED Requirements

### Requirement: 公开实验读取不得保留 legacy result payload
系统 SHALL 只通过 `experiment_id + manifest + declared artifacts` 暴露公开实验读取面。公开 API MUST 不再保留 legacy `/results/{run_id}` payload。

#### Scenario: 旧 result route 被删除
- **WHEN** 客户端尝试访问公开 legacy `/api/backtest_v2/results/{run_id}`
- **THEN** 该公开路由不存在，系统主读取面保持为 manifest-driven artifacts
