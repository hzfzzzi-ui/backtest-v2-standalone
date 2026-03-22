# SCHEMA_rows.json

## 1. 说明

当前仓库没有单独落盘的 `rows.json` 文件。

这里的 `rows schema` 指当前稳定的行式 public payload:

- `GET /api/backtest_v2/experiments` 的 history rows
- `POST /api/backtest_v2/experiments/compare` 的 compare rows

历史版本里出现过 group-level rows，但当前主线对外稳定面已经收敛到
history/compare 这两类 row-shaped payload。

## 2. History Row

来源:

- `backend/api/backtest_v2/contracts/responses.py::HistoryListItem`
- `backend/core/services/experiment_query_service.py::list_experiments`

最小字段:

```json
{
  "exp_id": "exp_20260314_144548534_7db9",
  "label": "exp_20260314_144548534_7db9",
  "created_at": "2026-03-14T14:47:24.076894",
  "has_manifest": true,
  "has_core_artifacts": true,
  "asset_scope": "cn_a_equity",
  "asset_profile_id": "cn_a_equity_mainline",
  "market_profile_id": "cn_a_mainland_equity_market",
  "perf": {
    "cagr": 0.2032763161631579,
    "max_drawdown": -0.29025259513173496,
    "sharpe": 0.8891097010317657,
    "total_return": 4.425630011081876,
    "trades": 467
  }
}
```

约束:

- `exp_id`: `string`, 非空
- `label`: `string`, 非空
- `created_at`: `string|null`
- `has_manifest`: `boolean`
- `has_core_artifacts`: `boolean`
- `asset_scope`, `asset_profile_id`, `market_profile_id`: `string|null`
- `perf`: `object`
- `perf` 内数值字段必须是 `number|null`
- 不允许 `NaN`/`Inf`

## 3. Compare Item Row

来源:

- `backend/core/services/experiment_history_service.py::compare_experiments`

最小字段:

```json
{
  "exp_id": "exp_a",
  "label": "A",
  "created_at": "2026-03-08T01:00:00",
  "has_manifest": true,
  "has_core_artifacts": true,
  "perf": {
    "total_return": 0.3,
    "cagr": 0.1,
    "sharpe": 1.2,
    "max_drawdown": -0.2,
    "trades": 5
  },
  "nav": [
    {"date": "2024-01-01", "nav": 1.0},
    {"date": "2024-01-02", "nav": 1.1}
  ]
}
```

约束:

- `nav` 是 `list[object]`
- 每个 `nav` row 至少包含:
  - `date: string`
  - `nav: number`
- compare payload 顶层还会返回:
  - `items: list[compare row]`
  - `skipped: list[{exp_id, reason}]`

## 4. 兼容规则

- 允许新增字段
- 不允许删除 `exp_id`、`label`、`perf`
- 不允许把数值改成字符串
- 不允许输出 PowerShell `@{...}` 风格字符串
