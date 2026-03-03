# SCHEMA: run_meta.json

```json
{
  "run_id": "run_xxx",
  "exp_id": "exp_xxx",
  "group_id": "GROUP_A",
  "preset": "TREND_QUALITY_VALIDATE_v1",
  "data": {
    "start": "2021-01-01",
    "end": "2026-02-01",
    "benchmark": "000300.SH",
    "compare_symbol": "000001.SH",
    "universe_mode": "db_index_constituents",
    "universe_size": 812,
    "universe_limit": 1000,
    "filters": {
      "exclude_st": true,
      "exclude_suspended": true,
      "min_list_days": 120,
      "min_avg_turnover_20d": 100000000
    }
  },
  "code": {
    "git_commit": null,
    "engine_mode": "VECTOR_FAST_STRICT",
    "execution_profile": "tradable",
    "fast_mode": true
  },
  "pipeline": [
    {
      "name": "Universe过滤",
      "enabled": true,
      "params": {},
      "counters": {}
    }
  ],
  "counters": {
    "raw_signal": 1000,
    "blocked": 300,
    "orders": 400,
    "skipped": 10,
    "closed_trades": 320,
    "gate_on_rate": 0.55,
    "mf_rank_applied_rate": 0.21,
    "trend_slope_block_count": 78,
    "atr_stop_exit_count": 35,
    "atr_trail_exit_count": 64,
    "atr_trail_update_count": 0
  },
  "artifacts": {
    "run_meta": "groups/GROUP_A/run_meta.json",
    "perf": "groups/GROUP_A/perf.json",
    "nav": "groups/GROUP_A/nav.csv",
    "funnel": "groups/GROUP_A/funnel.csv",
    "reason_codes": "groups/GROUP_A/reason_codes.csv",
    "config": "groups/GROUP_A/config.json",
    "symbol_performance": "groups/GROUP_A/symbol_performance.csv"
  },
  "missing_fields": [],
  "legacy_hits": {
    "reason_codes_filename": 0,
    "counters_field_alias": 0
  }
}
```

约束：
- 数值字段必须为 `number` 或 `null`。
- `missing_fields` 允许记录缺失统计，但不允许缺失必出文件。
- 缺失命名固定使用精确键名（示例）：
  - `missing_nav_source`
  - `missing_funnel_source`
  - `missing_reason_code_source`
  - `missing_symbol_performance_source`
  - `missing_atr_trigger_counters`
- 新写出的 `counters` 只使用短名；读取侧兼容窗口可回退 `*_count` 旧字段。
