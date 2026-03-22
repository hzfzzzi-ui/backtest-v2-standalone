## Why

当前 `V2` 剩余 `eligible_no_source` 已经收敛到极少数 symbol。`sh600680` 和 `sh601268` 已有上交所正式停牌/终止证据，但现有 `delist_tail_confirmed` 规则仍要求“晚于最后原始源日期”，导致这两只因为 `adj_factor/stk_limit` 等辅助原始源延续而无法收口，继续被误记为真无源。

## What Changes

- 为 `V2` 增加一份显式、可审计的“官方 terminal override”元数据，只覆盖已核实的 `sh600680` 与 `sh601268`。
- 允许 canonical 在命中显式 override 时，将原本的 `source_unresolved` 行改记为 `delist_tail_confirmed`，不再受“最后原始源日期”单一启发式限制。
- 保持 runtime 默认过滤口径不变；`delist_tail_confirmed` 继续被 runtime 排除。
- 在 audit 中继续把这些行单列为 `delist_tail_confirmed`，而不是计入 `eligible_no_source`。
- 对 `sh600680`、`sh601268` 做定向 slice rebuild，并重跑 full-window audit 验证影响范围。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `cn-stock-v2-terminal-eligibility-governance`: 允许使用显式、经官方证据审过的 symbol override 来确认 terminal boundary，不再只依赖“最后原始源日期之后”的单一规则。
- `cn-stock-v2-canonical-quality-governance`: 明确 canonical 可以基于显式官方 override 将特定 `source_unresolved` 行落为 `delist_tail_confirmed`。
- `cn-stock-v2-audit-gates`: 明确命中官方 terminal override 的行不得继续计入 `eligible_no_source`，必须单列为 `delist_tail_confirmed`。

## Impact

- 受影响代码：
  - `backend/cli/managed/pams_ohlcv_daily_v2_common.py`
  - `backend/cli/managed/update_pams_ohlcv_daily_v2.py`
  - `backend/cli/managed/audit_pams_ohlcv_daily_v2.py`
  - `tests/unit/test_update_pams_ohlcv_daily_v2.py`
  - `tests/unit/test_audit_pams_ohlcv_daily_v2.py`
- 受影响合同与文档：
  - `docs/db/pams_ohlcv_daily_v2_schema_contract.md`
  - `docs/db/pams_ohlcv_daily_v2_runtime_contract.md`
- 受影响数据产物：
  - `pams_ohlcv_daily_v2`
  - `pams_ohlcv_daily_v2_exceptions`
  - full-window audit summary
