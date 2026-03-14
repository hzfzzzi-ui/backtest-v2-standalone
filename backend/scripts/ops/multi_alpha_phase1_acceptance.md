# Multi Alpha Phase 1 Acceptance Run

## Request File

- `backend/scripts/ops/multi_alpha_phase1_acceptance.request.json`

## Repro Command

Preferred on this workstation: run inside the `backtest-v2-standalone` container so it reuses the existing Docker network and `PG*` environment.

```powershell
docker exec backtest-v2-standalone sh -lc "cd /app && python - <<'PY'
import json
from pathlib import Path
from backend.scripts._internal_helper import run_internal_experiment_sync

root = Path('/app')
payload = json.loads(
    (root / 'backend' / 'scripts' / 'ops' / 'multi_alpha_phase1_acceptance.request.json').read_text(encoding='utf-8')
)
result = run_internal_experiment_sync(payload)
print(json.dumps({
    'exp_id': result.get('exp_id'),
    'status': result.get('status'),
    'results_dir': result.get('results_dir'),
}, ensure_ascii=False, indent=2))
PY"
```

Host-shell fallback: use a PostgreSQL endpoint that exposes the `pams` database with historical market data and export valid `PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD` first.

## Expected Artifacts

- `input_config.json`
- `resolved_config.json`
- `compiled_plan.json`
- `audit.json`
- `orders.csv`
- `trades.csv`
- `run_meta.json`
- `manifest.json`

## Local Environment Note

- Verified sample run: `exp_20260309_011329170_a9f5`
- Verified artifacts include `compiled_plan.json`, `audit.json`, `orders.csv`, `trades.csv`, `input_config.json`, and `resolved_config.json`
- Strategy clock is unchanged by this acceptance flow: signals are generated on `t` close and executed on `t+1` open by the runtime itself
