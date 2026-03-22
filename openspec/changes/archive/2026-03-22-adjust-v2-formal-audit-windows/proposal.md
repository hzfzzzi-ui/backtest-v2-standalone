## Why

当前 `V2` 审计门禁文档仍写着 `2016-2026 / 2007-2017 / 2007-2026` 三窗口，但实际代码只稳定产出 `full-window` 单窗口 audit，formal audit 没有固定编排器，也没有把缺失窗口显式沉淀成统一产物。这样即使手工补跑过，也难以稳定复核“正式三窗口是否齐了”。

## What Changes

- 将 `V2` formal audit 的三窗口口径明确固化为：
  - `2016-2026`
  - `2012-2017`
  - `2007-2026`
- 新增一个专门的 `pams_ohlcv_daily_v2_formal_audits` runner，按固定三窗口顺序执行 audit，并产出汇总状态文件。
- 保持单窗口 `audit_pams_ohlcv_daily_v2` 的实现不变，由 formal runner 在其之上做编排，不改 canonical/runtime 规则。
- 让 `full_backfill` 在完成 `audit_full_window` 后继续执行 `audit_formal_windows`，把 formal audit 变成固定流程的一部分。
- 更新 CLI target、runbook、测试和 gate spec，使 formal audit 补齐可复现、可追踪。

## Capabilities

### New Capabilities

- `cn-stock-v2-formal-audit-runner`: 负责按固定三窗口编排 `V2` formal audit，并输出统一汇总产物。

### Modified Capabilities

- `cn-stock-v2-audit-gates`: 将 formal audit 三窗口中的硬门槛窗口从 `2007-2017` 调整为 `2012-2017`，并要求三窗口结果可被统一复核。

## Impact

- 受影响代码：
  - `backend/cli/managed/pams_ohlcv_daily_v2_common.py`
  - `backend/cli/managed/run_pams_ohlcv_daily_v2_formal_audits.py`
  - `backend/cli/managed/run_pams_ohlcv_daily_v2_full_backfill.py`
  - `backend/cli/commands/data_refresh.py`
  - `tests/unit/test_run_pams_ohlcv_daily_v2_formal_audits.py`
  - `tests/unit/test_run_pams_ohlcv_daily_v2_full_backfill.py`
  - `tests/unit/test_cli_main.py`
- 受影响规格与文档：
  - `openspec/specs/cn-stock-v2-audit-gates/spec.md`
  - `docs/db/pams_ohlcv_daily_v2_runbook.md`
- 受影响产物：
  - `outputs/ops/.../audit_2016_2026/summary.json`
  - `outputs/ops/.../audit_2012_2017/summary.json`
  - `outputs/ops/.../audit_2007_2026/summary.json`
  - `outputs/ops/.../summary.json`
