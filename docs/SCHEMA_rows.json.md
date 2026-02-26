# SCHEMA: experiment result.rows

每个 `rows[i]` 必须是严格 JSON 对象：

```json
{
  "group_id": "GROUP_A",
  "status": "OK",
  "tier": "T2",
  "total_return": 0.16,
  "max_drawdown": -0.09,
  "cagr": 0.11,
  "sharpe": 1.42,
  "calmar": 1.22,
  "trades": 356,
  "turnover": 0.18,
  "top10_profit_concentration": 0.51,

  "raw_signal": 1200,
  "blocked": 350,
  "orders": 430,
  "skipped": 15,
  "closed_trades": 330,

  "gate_on_rate": 0.61,
  "mf_rank_applied_rate": 0.19,
  "trend_slope_block_count": 66,
  "atr_stop_exit_count": 29,
  "atr_trail_exit_count": 70,
  "atr_trail_update_count": 0,

  "group_dir": "groups/GROUP_A",
  "group_files": {
    "run_meta": "groups/GROUP_A/run_meta.json",
    "perf": "groups/GROUP_A/perf.json",
    "nav": "groups/GROUP_A/nav.csv",
    "funnel": "groups/GROUP_A/funnel.csv",
    "reason_codes": "groups/GROUP_A/reason_code_counts.csv",
    "config": "groups/GROUP_A/config.json"
  },
  "red_flags": ["NOT_EFFECTIVE_OR_NOT_INSTRUMENTED"]
}
```

约束：
- 允许新增字段；不得删除/改名上述字段。
- 数值只允许 `number|null`，禁止字符串数值与 `NaN/Inf`。
- 禁止 PowerShell `"@{...}"` 风格行对象。
