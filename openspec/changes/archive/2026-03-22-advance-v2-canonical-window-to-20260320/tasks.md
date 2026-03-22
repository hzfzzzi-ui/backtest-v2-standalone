## 1. 合同与默认口径对齐

- [x] 1.1 固化 change artifacts 与 delta specs，明确 `v2` 正式窗口终点升到 `2026-03-20`。DoD: proposal/design/specs/tasks 完整可校验；验证: `openspec validate advance-v2-canonical-window-to-20260320 --type change --strict`；风险: 若 spec 不更新，代码改动仍会与正式口径漂移。
- [x] 1.2 更新 `v2` 共用常量、full backfill 默认值与 audit summary 的 official window 语义。DoD: `OFFICIAL_END_DATE` 与相关默认值一致且 summary 暴露 official window；验证: 单测与本地代码检查；风险: 若仍有散落硬编码，gate 会继续误判。

## 2. 文档与回归验证

- [x] 2.1 更新正式 runbook 示例命令，避免继续引用 `2026-03-16`。DoD: `docs/db/pams_ohlcv_daily_v2_runbook.md` 与相关 side-table 文档改为当前正式窗口；验证: diff 检查；风险: 运维仍可能按旧命令误跑。
- [x] 2.2 更新或新增单测覆盖新的 official window 与 full-window gate 语义。DoD: 相关单测通过；验证: `pytest tests/unit/test_run_pams_ohlcv_daily_v2_full_backfill.py tests/unit/test_audit_pams_ohlcv_daily_v2.py -q`；风险: 若无测试，后续很容易再次把窗口改回旧值。
- [x] 2.3 重跑 `2007-01-04 ~ 2026-03-20` full-window audit 并记录 canonical gate 当前阻塞项。DoD: 产出新的 audit summary；验证: 审计产物存在且 `official_window.end=2026-03-20`；风险: 真实 unresolved 阻塞会继续存在，不能误报为已通过。
