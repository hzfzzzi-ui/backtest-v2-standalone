# SCHEMA_manifest.json

## 1. 文件位置

- `outputs/experiments/<exp_id>/manifest.json`
- `examples/experiment_contract_minimal/manifest.json`

生成宿主:

- `backend/api/backtest_v2/artifacts_manifest.py`

当前 schema version:

- `backtest_v2_experiment_manifest@2`

## 2. 顶层结构

```json
{
  "exp_id": "exp_20260314_144548534_7db9",
  "experiment_id": "exp_20260314_144548534_7db9",
  "status": "OK",
  "created_at": "2026-03-14T14:47:24.076894",
  "schema_version": "backtest_v2_experiment_manifest@2",
  "artifacts": {},
  "config_snapshots": {},
  "core_artifacts": {},
  "baseline_compare_status": "NOT_RUN",
  "metrics": {},
  "stage_pipeline": {},
  "stage_summary": {},
  "asset_scope": "cn_a_equity",
  "asset_profile_id": "cn_a_equity_mainline",
  "market_profile_id": "cn_a_mainland_equity_market",
  "execution_profile_id": "cn_a_tplus1_next_open",
  "asset_context": {}
}
```

## 3. 必需字段

- `exp_id: string`
- `experiment_id: string`
- `status: string`
- `created_at: string`
- `schema_version: string`
- `artifacts: object`
- `config_snapshots: object`
- `core_artifacts: object`
- `baseline_compare_status: string`
- `metrics: object`

## 4. `artifacts`

`artifacts` 是完整的相对路径映射，当前常见 key 包括:

- `perf`
- `nav`
- `funnel`
- `reason_codes`
- `config`
- `run_meta`
- `trades`
- `daily`
- `orders`
- `symbol_performance`
- `audit`
- `stage_summary`
- `input_config`
- `resolved_config`
- `compiled_plan`
- `execution_lineage_ledger`

说明:

- 并不是所有 key 都必须出现
- 但 `core_artifacts` 中出现的 key 必须在结果目录实际存在

## 5. `core_artifacts`

这是实验主协议文件映射，当前主线最小集通常包括:

- `perf`
- `nav`
- `funnel`
- `reason_codes`
- `config`
- `run_meta`

常见扩展:

- `trades`
- `daily`
- `audit`
- `stage_summary`
- `input_config`
- `resolved_config`
- `compiled_plan`
- `execution_lineage_ledger`

## 6. `metrics`

当前正式字段:

```json
{
  "total_return": 4.425630011081876,
  "max_drawdown": -0.29025259513173496,
  "cagr": 0.2032763161631579,
  "sharpe": 0.8891097010317657,
  "trades": 467,
  "turnover": 0.02077596030035478,
  "effective_execution_start_date": "2016-08-29",
  "metrics_from_effective_start": true
}
```

## 7. `stage_pipeline` 与 `stage_summary`

- `stage_pipeline` 保存主链运行摘要
- `stage_summary` 当前是对 `stage_summary.json` 的轻量引用

当前 `stage_summary` 形态:

```json
{
  "artifact": "stage_summary.json",
  "schema_version": "stage_pipeline_summary@1"
}
```

## 8. 兼容规则

- 允许新增 artifact key
- 不允许删除第 3 节中的必需字段
- `schema_version` 升级时必须同步更新本文档和示例目录
