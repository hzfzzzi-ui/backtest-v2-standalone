# Capability: smoke-flow-test

## Purpose

End-to-end smoke test that exercises the critical path of the backtest system -- from DB health verification through experiment execution, artifact validation, benchmark overlay, and config roundtrip -- ensuring the deployed environment is functional. Tests are isolated behind a `pytest.mark.smoke` marker so they only run on explicit invocation.
## Requirements
### Requirement: DB health check gate
通流脚本 SHALL 在执行回测前先验证数据库可达性。通过调用 benchmark API 确认 DB 连接正常且数据表有记录。

#### Scenario: DB healthy
- **WHEN** GET /api/backtest_v2/series/benchmark 返回 200 且 points 非空
- **THEN** 测试通过，继续后续 steps

#### Scenario: DB unreachable
- **WHEN** GET /api/backtest_v2/series/benchmark 返回非 200 或 points 为空
- **THEN** 测试立即失败，报告 "DB health check failed"

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

### Requirement: Artifact integrity verification
通流脚本 SHALL 验证回测产物的完整性和结构正确性。

#### Scenario: All artifacts present
- **WHEN** 回测成功完成，result 返回
- **THEN** result 顶层包含 status=="OK"，metrics 字段（sharpe/max_drawdown/cagr）为数值类型，result.artifacts 包含 perf 和 nav 路径

#### Scenario: Missing artifacts
- **WHEN** result 缺少必要字段
- **THEN** 测试失败，报告缺失的字段名

### Requirement: Benchmark overlay validation
通流脚本 SHALL 验证基准线 API 返回有效的归一化 NAV 序列。

#### Scenario: Valid benchmark series
- **WHEN** GET /api/backtest_v2/series/benchmark 使用回测同期日期范围
- **THEN** points 非空，首个 nav ≈ 1.0 (误差 < 0.001)，dates 递增

### Requirement: Config save-load roundtrip
通流脚本 SHALL 验证配置保存后再加载，内容完全一致。

#### Scenario: Roundtrip equality
- **WHEN** POST /api/backtest_v2/configs 保存 smoke_config
- **AND** GET /api/backtest_v2/configs/{cfg_id} 加载
- **THEN** loaded.config_json == original config_json (deep equal)

### Requirement: Smoke marker isolation
通流脚本 SHALL 使用 pytest.mark.smoke 标记，默认 pytest 运行时不执行。

#### Scenario: Default pytest excludes smoke
- **WHEN** 运行 `pytest` (无 -m 参数)
- **THEN** smoke flow test 不被执行

#### Scenario: Explicit smoke run
- **WHEN** 运行 `pytest -m smoke`
- **THEN** smoke flow test 被执行

