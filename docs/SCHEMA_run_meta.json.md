# SCHEMA_run_meta.json

## 1. 文件位置

- `outputs/experiments/<exp_id>/run_meta.json`
- `examples/experiment_contract_minimal/run_meta.json`

生成宿主:

- `backend/api/backtest_v2/artifacts_finalize.py`

## 2. 顶层结构

当前正式字段:

```json
{
  "exp_id": "exp_20260314_144548534_7db9",
  "tier": "T0",
  "status": "OK",
  "created_at": "2026-03-14T14:47:23.847357",
  "data": {},
  "code": {},
  "counters": {},
  "price_adj_mode": "hfq",
  "adj_factor_stats": {},
  "missing_fields": [],
  "warmup": {},
  "asset_context": {},
  "report_consistency": {},
  "universe": {},
  "data_bundle": {},
  "candidate": {},
  "stage_pipeline": {}
}
```

说明:

- `universe`、`data_bundle`、`candidate`、`stage_pipeline` 是条件出现字段
- 不要求所有运行都带这些字段

## 3. 必需字段

- `exp_id: string`
- `tier: string`
- `status: "OK" | "FAILED" | "CANCELED" | string`
- `created_at: string`
- `data: object`
- `code: object`
- `counters: object`
- `missing_fields: list[string]`
- `asset_context: object`
- `report_consistency: object`

## 4. `data`

当前主线最小字段:

```json
{
  "start": "2016-03-01",
  "end": "2026-03-01",
  "benchmark": "000300.SH",
  "compare_symbol": null,
  "universe_limit": null,
  "asset_scope": "cn_a_equity",
  "universe_mode": "HS300_ZZ500"
}
```

## 5. `code`

当前主线最小字段:

```json
{
  "engine_mode": "VECTOR_FAST_STRICT",
  "execution_profile": "tradable",
  "fast_mode": true
}
```

## 6. `counters`

最小 canonical counters:

```json
{
  "raw_signal": 237,
  "blocked": 0,
  "orders": 467,
  "skipped": 0,
  "closed_trades": 230
}
```

允许扩展字段:

- `avg_positions`
- `max_positions`
- `gate_on_rate`
- `mf_rank_applied_rate`
- `atr_stop_exit_count`
- `atr_trail_exit_count`
- `atr_trail_update_count`
- `buy_stage_funnel`
- 以及其他诊断计数器

约束:

- canonical funnel 字段必须保持:
  - `raw_signal`
  - `blocked`
  - `orders`
  - `skipped`
  - `closed_trades`
- 不再使用旧式 `*_count` 替代这些 canonical 字段

## 7. `missing_fields`

`missing_fields` 记录协议补齐时的缺口来源，例如:

- `missing_nav_source`
- `missing_funnel_source`
- `missing_reason_code_source`
- `missing_symbol_performance_source`

缺失必须记录到这里，而不是通过省略文件掩盖。

## 8. `asset_context`

最小字段:

```json
{
  "asset_scope": "cn_a_equity",
  "asset_profile_id": "cn_a_equity_mainline",
  "market_profile_id": "cn_a_mainland_equity_market",
  "execution_profile_id": "cn_a_tplus1_next_open"
}
```

## 9. `report_consistency`

最小字段:

```json
{
  "sources": {
    "start": "run_config.universe.start",
    "end": "run_config.universe.end",
    "benchmark": "run_config.universe.benchmark",
    "funnel": "funnel.csv"
  },
  "config_source": "config_json",
  "config_conflict_policy": "config_json_preferred",
  "resolved_config_mode": "semantic_config_run",
  "resolved_config_id": null,
  "resolved_config_hash": "c49cc61c95aa9829c860aa842633c78a2c733198",
  "resolved_config_meta": {}
}
```

## 10. 兼容规则

- 允许新增字段
- 不允许删除第 3 节列出的必需字段
- 数值必须是 `number|null`
- 不允许 `NaN`/`Inf`
