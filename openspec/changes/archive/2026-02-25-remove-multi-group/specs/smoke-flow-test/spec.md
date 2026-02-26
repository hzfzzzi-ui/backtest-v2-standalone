## MODIFIED Requirements

### Requirement: Artifact integrity verification
通流脚本 SHALL 验证回测产物的完整性和结构正确性。

#### Scenario: All artifacts present
- **WHEN** 回测成功完成，result 返回
- **THEN** result 顶层包含 status=="OK"，metrics 字段（sharpe/max_drawdown/cagr）为数值类型，result.artifacts 包含 perf 和 nav 路径

#### Scenario: Missing artifacts
- **WHEN** result 缺少必要字段
- **THEN** 测试失败，报告缺失的字段名

### Requirement: Experiment launch and completion
通流脚本 SHALL 提交一个 smoke 配置的 experiment 并轮询至终态。

#### Scenario: Experiment succeeds
- **WHEN** POST /api/backtest_v2/experiment/run_async 返回 job_id
- **AND** 轮询 GET /api/backtest_v2/jobs/{job_id} 直到 status == "success"
- **THEN** 测试通过，result 为扁平结构（无 rows[] 数组）

#### Scenario: Experiment fails
- **WHEN** 轮询返回 status == "failed"
- **THEN** 测试失败，报告 job error message

#### Scenario: Poll timeout
- **WHEN** 轮询超过 120s 仍未到达终态
- **THEN** 测试失败，报告 "timeout after 120s, last status: {status}"
