## Artifact Read Migration Map

Desktop main path no longer uses `/api/backtest_v2/artifacts/read`.

| Old main-path read | Canonical replacement |
|---|---|
| `perf.json` via `/artifacts/read` | `GET /api/backtest_v2/experiments/{exp_id}/surface` |
| `nav.csv` via `/artifacts/read` | `GET /api/backtest_v2/experiments/{exp_id}/surface/nav` |
| `run_meta.json` via `/artifacts/read` | `GET /api/backtest_v2/experiments/{exp_id}/surface/run_meta` |
| `config.json` / `resolved_config.json` via `/artifacts/read` | `GET /api/backtest_v2/experiments/{exp_id}/surface/config` |
| `portfolio_trades.csv` via `/artifacts/read` | `GET /api/backtest_v2/experiments/{exp_id}/surface/trades` |
| `portfolio_daily.csv` via `/artifacts/read` | `GET /api/backtest_v2/experiments/{exp_id}/surface/daily` |
| `reason_codes.csv` via `/artifacts/read` | `GET /api/backtest_v2/experiments/{exp_id}/surface/reason_codes` |
| `stock_names.json` via `/artifacts/read` | `GET /api/backtest_v2/experiments/{exp_id}/surface/stock_names` |
| `stage_funnel` artifact fallback | `GET /api/backtest_v2/experiments/{exp_id}/surface/stage_funnel` |
| `symbol_stats` artifact fallback | `GET /api/backtest_v2/experiments/{exp_id}/surface/symbol_stats` |

Main path owners:

- `frontend/assets/js/pages/desktop-research-page.js`
- `frontend/assets/js/artifacts.js`
- `frontend/assets/js/pages/desktop-load-controls.js`

Allowed exception:

- Generic artifact read may remain only for ops/debug tooling, not for desktop main-path rendering.
