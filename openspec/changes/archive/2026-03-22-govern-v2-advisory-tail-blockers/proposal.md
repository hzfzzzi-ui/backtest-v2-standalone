## Why

`2016-2026` 与 `2012-2017` 的 formal hard gate 已经清零，但 `2007-2026` advisory 全周期还剩 `740` 行 blocker。

其中真正还需要处理的只剩两类：

- `sh600286 / sz000583 / sz000699` 的 `244` 行真无源尾巴。它们都从 `2007-01-04` 起连续无源直到 `delist_date`，而且都能找到 formal window 起点之前已暂停上市的证据。
- `bj920047 / bj920090` 的 `8` 行 `mapping_failure`。这不是新规则问题，而是旧 build 未重刷留下的当前异常。

这轮目标不是放宽 runtime，也不是泛化 terminal heuristic，而是把剩余 advisory blocker 收敛到零。

## What Changes

- 为 `sh600286 / sz000583 / sz000699` 增加显式 terminal override，只覆盖 `2007-01-04 ~ delist_date` 的连续无源尾段。
- override 仍复用 `delist_tail_confirmed`，不新增新的 row status。
- BJ 两只 symbol 不改规则，只做定点 slice rebuild，清掉旧 `mapping_failure`。
- 重跑 formal audits，验证 `2007-2026` advisory 的 `critical_exception_rows` 是否归零。

## Capabilities

### Modified Capabilities

- `cn-stock-v2-canonical-quality-governance`
- `cn-stock-v2-audit-gates`
- `cn-stock-v2-source-governance`

## Impact

- 受影响代码：
  - `backend/cli/managed/pams_ohlcv_daily_v2_common.py`
  - `tests/unit/test_update_pams_ohlcv_daily_v2.py`
- 受影响合同与变更说明：
  - `docs/db/pams_ohlcv_daily_v2_schema_contract.md`
  - `openspec/changes/govern-v2-advisory-tail-blockers/*`
- 受影响数据产物：
  - `pams_ohlcv_daily_v2`
  - `pams_ohlcv_daily_v2_exceptions`
  - `pams_ohlcv_daily_v2_formal_audits`
