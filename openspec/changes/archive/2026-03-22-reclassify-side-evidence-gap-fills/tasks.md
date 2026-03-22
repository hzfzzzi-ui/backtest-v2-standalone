## 1. 规格与分类规则

- [x] 1.1 固化 side-evidence gap fill 的 OpenSpec 变更，明确 `synthetic_gap_fill` 与 `source_unresolved` 的边界。DoD: proposal/design/specs/tasks 完整；验证: `openspec validate reclassify-side-evidence-gap-fills --type change --strict`；风险: 若先改代码不改 spec，`eligible_no_source` 含义会继续漂移。

## 2. 实现与回归

- [x] 2.1 修改 `update_pams_ohlcv_daily_v2.py`，让 `SH/SZ` 中带侧证据但缺 `daily/suspend_d` 的行记为 `synthetic_gap_fill`，并输出独立 exception。DoD: 真无源行仍保留 `source_unresolved + eligible_no_source`；验证: 单测覆盖两种分支；风险: 若误伤 `BJ`，会洗掉 mapping 问题。
- [x] 2.2 修改 `audit_pams_ohlcv_daily_v2.py`，让 `eligible_missing_daily_count` 只统计真正无源行。DoD: `synthetic_gap_fill` 不再混入 `eligible_no_source`，但 runtime exclusion 保持不变；验证: 定向单测；风险: 若 audit 与 build 规则不同步，gate 会失真。
- [x] 2.3 更新相关单测。DoD: `tests/unit/test_update_pams_ohlcv_daily_v2.py` 与 `tests/unit/test_audit_pams_ohlcv_daily_v2.py` 覆盖 side-evidence / true-no-source 两分支；验证: `pytest tests/unit/test_update_pams_ohlcv_daily_v2.py tests/unit/test_audit_pams_ohlcv_daily_v2.py -q`；风险: 无测试时极易回归。

## 3. 数据修复与验证

- [x] 3.1 用 symbol slice 先重建头部 `SH/SZ` unresolved 簇。DoD: 头部簇对应 symbol 的 `source_unresolved` 降低，`synthetic_gap_fill` 上升；验证: slice rebuild 后查库；风险: 若直接全量重建，成本过高且难以归因。
- [x] 3.2 重跑 full-window audit，记录 `eligible_no_source`、`critical_exception_rows` 和 runtime exclusion 的变化。DoD: 新 summary 产出并可对比旧 run；验证: `outputs/ops/.../summary.json`；风险: 只看局部 slice 不看全局审计，会误判治理效果。
