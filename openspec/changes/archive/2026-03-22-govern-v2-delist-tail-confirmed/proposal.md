## Why

当前 `eligible_no_source` 剩余样本已经高度收敛：主体不再是 `SH/SZ/BJ` 的侧证据误判，而是退市尾段和个别证券代码变更后的终止边界问题。继续把这类记录统一算作 `missing_in_all_sources`，会把“正式终止边界”误记成“源失败”，阻塞 `v2` canonical 审计升格。

## What Changes

- 为 `v2` 增加“终止边界治理”规则，正式区分退市尾段、代码变更退役尾段与普通 `source_unresolved`。
- 在 canonical 中新增 `delist_tail_confirmed` 行状态，仅用于有正式终止证据但无日线/停牌原始源的尾段记录。
- 调整 audit 与 runtime gate：`delist_tail_confirmed` 不再计入 `eligible_no_source`，但仍不得被 runtime 默认消费。
- 补充 `300114 -> 302132` 这类代码变更终止边界的显式治理与验证样本。

## Capabilities

### New Capabilities
- `cn-stock-v2-terminal-eligibility-governance`: 约束退市尾段和代码变更退役尾段的正式边界、证据来源与分类规则。

### Modified Capabilities
- `cn-stock-v2-canonical-quality-governance`: 扩展 canonical 行状态，增加 `delist_tail_confirmed` 的正式语义与约束。
- `cn-stock-v2-audit-gates`: 调整 `eligible_no_source` 与异常汇总口径，单列终止边界尾段而不再混入真无源缺口。
- `cn-stock-v2-runtime-compat-governance`: 明确 runtime compatibility 必须排除 `delist_tail_confirmed`。

## Impact

- 受影响代码：
  - `backend/cli/managed/update_pams_ohlcv_daily_v2.py`
  - `backend/cli/managed/audit_pams_ohlcv_daily_v2.py`
  - `backend/cli/managed/pams_ohlcv_daily_v2_common.py`
  - `tests/unit/test_update_pams_ohlcv_daily_v2.py`
  - `tests/unit/test_audit_pams_ohlcv_daily_v2.py`
- 受影响数据库与合同：
  - `pams_ohlcv_daily_v2`
  - `pams_ohlcv_daily_v2_exceptions`
  - `pams_ohlcv_daily_v2_runtime`
  - `pit_security_master`
  - `pit_security_symbol_lineage`
  - `docs/db/pams_ohlcv_daily_v2_apply.sql`
