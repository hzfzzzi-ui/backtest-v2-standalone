## 2026-04-30 P0 verification note

Code and contract checks completed:

- `factor_insertion_contracts.py` accepts `bull_only_band_rerank` and `bull_trans_up_band_rerank`.
- `candidate_plan.py` gates rerank activation by `BULL` and `BULL+TRANS_UP`.
- Unit tests cover the new modes and the shared `band_limit` validation path.
- The study definition and generated thin script dry-run to the expected execution plan.

Blocked evidence:

- Actual `1217` execution failed before portfolio generation because the current local data set does not provide the required PIT dynamic universe constituent rows for `mode=HS300_ZZ500`, `index_code=000906.SH`.
- Existing output artifacts under `outputs/studies/conclusions/v10/moneyflow_monthly_band_rerank_state_gate_s1/` are not reliable completion evidence. The old state-gated runs recorded zero active gate days even though the same run config resolves `gate_on=True` under the current overlay resolver on sampled trading days.

P0 decision:

- Do not archive this change yet.
- Do not use the stale output artifacts to conclude whether state gating improves stability.
- Next required step is to repair or refresh the PIT membership data dependency, then rerun both `1217` and `1226` before completing tasks 3.3-3.5.

## 2026-04-30 Docker-backed correction

The earlier local-only verification was insufficient. Docker Desktop was started, `docker compose up -d` brought up the API container and host PostgreSQL proxy, and the study was rerun against the DB-backed runtime path.

Runtime defect found during the Docker rerun:

- The stage-pipeline candidate-plan adapter only read `controls.market_state`; the formal runtime state is carried by `effective_state_5` / `market_state_5`.
- Candidate, order, and daily diagnostics were recording the raw overlay snapshot gate instead of the effective state-gated rerank gate.

Minimal repair:

- Candidate planning now resolves state-gated overlay activation from `effective_state_5`, then `market_state_5`, then legacy `market_state`.
- Candidate audit rows, BUY order meta, and daily diagnostics now record the effective overlay gate after state suppression.
- `backend/scripts/update_pit_index_daily.py` now imports `json`; without this, the API container's background PIT refresh could crash while writing its summary.

Valid Docker-backed runs after the repair:

| Window | Variant | Exp ID | CAGR | Sharpe | MaxDD | Trades |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| 1217 | B0 | `exp_20260430_044641200_fa84` | 0.0225095355 | 0.2119692598 | -0.4641268692 | 390 |
| 1217 | MF_BAND20_BULL | `exp_20260430_044747185_6196` | 0.0361113505 | 0.2715500822 | -0.4223228549 | 384 |
| 1217 | MF_BAND20_BULL_TRANSUP | `exp_20260430_044953388_9341` | 0.0562444416 | 0.3586741806 | -0.4045095560 | 378 |
| 1226 | B0 | `exp_20260430_053517824_a86b` | 0.1036337900 | 0.5216465475 | -0.4641268692 | 947 |
| 1226 | MF_BAND20_BULL | `exp_20260430_054609719_4c4a` | 0.0840117139 | 0.4654882866 | -0.4223228549 | 1008 |
| 1226 | MF_BAND20_BULL_TRANSUP | `exp_20260430_051955019_45c0` | 0.1008861832 | 0.5374044368 | -0.4045095560 | 1038 |

Effective gate audit:

- `1217` B0: 0 gate-on rows.
- `1217` BULL: 777 gate-on rows, all `BULL`.
- `1217` BULL+TRANS_UP: 963 gate-on rows, `BULL=777`, `TRANS_UP=186`.
- `1226` B0: 0 gate-on rows.
- `1226` BULL: 1576 gate-on rows, all `BULL`.
- `1226` BULL+TRANS_UP: 1908 gate-on rows, `BULL=1576`, `TRANS_UP=332`.

P0 conclusion:

- State gating is now proven to affect the DB-backed runtime path; the old zero-gate artifacts are invalid.
- Versus B0, `MF_BAND20_BULL_TRANSUP` improves drawdown in both windows and improves 1217 return/sharpe, but it does not clearly improve stability over the existing ungated `band_rerank` reference.
- Do not promote state-gated rerank over ungated band-rerank. Keep this change as evaluated evidence, with `MF_BAND20_BULL_TRANSUP` as a secondary comparator rather than the main candidate.
