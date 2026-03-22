## Why

当前 `V2` formal audit 的 `critical_exception_rows` 会把 `BJ pre-2021-11-15` 的 `turnover_rate_imputed_zero` 直接算成 hard gate 阻塞项。实库核查已经证明，这批样本的主因不是构建错误，也不是可继续靠 lineage 清理的映射失败，而是：

- `raw_tushare_daily` 在该阶段存在；
- `raw_tushare_daily_basic` 对 `.BJ` 基本从 `2018-10-09` 才开始，`2012-2017` 几乎为空；
- `AkShare` 也没有形成稳定可审计的 `turnover_rate` fallback。

继续把这批样本混在泛化的 `critical_exception_rows` 里，会让 formal gate 把“已知免费源断层”误当成“构建失败”，不利于区分：

- 需要继续修代码/修构建的问题；
- 已经确认但当前没有正式免费补源的问题。

## What Changes

- 为 `BJ pre-2021-11-15` 的 `daily_basic` 缺口建立正式 source policy。
- formal audit 的 canonical gate 新增显式 `known_source_gap_rows`，用于统计已知源断层。
- `turnover_rate_imputed_zero + bj_pre_daily_basic_gap` 不再计入 hard gate 的 `critical_exception_rows`，但必须继续在 summary 中显式暴露。
- runtime gate 继续保守：这批行仍按低 `turnover_rate_confidence` 排除，不放开 `can_consume_v10_1`。
- 重刷 `2016-2021` 受影响的 `BJ pre` 切片，消除旧 `mapping_failure` 残留，再重跑 formal audits。

## Capabilities

### Modified Capabilities

- `cn-stock-v2-audit-gates`: hard gate 区分“已知源断层”与“真实 critical 构建异常”。
- `cn-stock-v2-formal-audit-runner`: summary 输出 `critical_exception_rows_raw / known_source_gap_rows / critical_exception_rows`。
- `cn-stock-v2-runtime-compat-governance`: runtime 继续排除 `BJ pre` 低置信 `turnover_rate`，但单独暴露这批已知源断层。

## Impact

- 受影响代码：
  - `backend/cli/managed/pams_ohlcv_daily_v2_common.py`
  - `backend/cli/managed/audit_pams_ohlcv_daily_v2.py`
- 受影响测试：
  - `tests/unit/test_audit_pams_ohlcv_daily_v2.py`
- 受影响文档：
  - `docs/db/v2_source_matrix.md`
  - `docs/db/pams_ohlcv_daily_v2_runbook.md`
  - `openspec/specs/cn-stock-v2-audit-gates/spec.md`
- 受影响产物：
  - `outputs/ops/.../audit_2012_2017/summary.json`
  - `outputs/ops/.../audit_2016_2026/summary.json`
