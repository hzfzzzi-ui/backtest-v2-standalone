## Why

当前 `V2` formal audit 已经能稳定产出 `2016-2026 / 2012-2017 / 2007-2026` 三窗口 summary，但 hard gate 仍把 `2007-2026` 作为阻断条件。这会把“全周期参考审计”和“正式升格硬门槛”混在一起：

- `2016-2026` 和 `2012-2017` 更贴近当前研究纪律里的开发窗与硬门槛窗
- `2007-2026` 更适合作为全周期参考审计，用来继续追踪历史尾部异常和长窗稳定性
- 当前剩余 `critical_exception_rows` 的大头也确实主要集中在全周期长尾问题，而不是当前 hard gate 想先卡死的正式窗口

因此需要把 `2007-2026` 从 hard gate 中移出，但继续保留为 advisory audit。

## What Changes

- 将 `V2 formal audit` 的 hard gate 从三窗口调整为双窗口：
  - `2016-2026`
  - `2012-2017`
- 保留 `2007-2026` 作为全周期参考审计窗口，不再计入 hard gate。
- 更新 formal audit 汇总产物：
  - `required_windows` 仅表示 hard gate 窗口
  - 新增 `advisory_windows`
  - `formal_windows_complete` 仅反映 hard gate 是否齐全
  - 新增 `all_windows_complete` 反映全部运行窗口是否齐全
- 更新 gate spec、runbook 和测试。
- 重跑 formal audits，并继续审计 `critical_exception_rows` 的结构分布。

## Capabilities

### Modified Capabilities

- `cn-stock-v2-formal-audit-runner`: 将 `2007-2026` 从 hard gate 改为 advisory，但保留统一编排和汇总。
- `cn-stock-v2-audit-gates`: hard gate 仅要求 `2016-2026 / 2012-2017`，`2007-2026` 仅作为全周期参考审计。

## Impact

- 受影响代码：
  - `backend/cli/managed/pams_ohlcv_daily_v2_common.py`
  - `backend/cli/managed/run_pams_ohlcv_daily_v2_formal_audits.py`
  - `tests/unit/test_run_pams_ohlcv_daily_v2_formal_audits.py`
- 受影响规格与文档：
  - `openspec/specs/cn-stock-v2-audit-gates/spec.md`
  - `docs/db/pams_ohlcv_daily_v2_runbook.md`
- 受影响产物：
  - `outputs/ops/.../summary.json`
  - `outputs/ops/.../audit_2007_2026/summary.json`
