## 1. Formal Audit 窗口常量与 runner

- [x] 1.1 在 `pams_ohlcv_daily_v2_common.py` 中固化 formal audit 三窗口为 `2016-2026 / 2012-2017 / 2007-2026`；DoD：窗口日期可被 runner 和测试共用；验证：单测；风险：窗口定义散落导致规则漂移。
- [x] 1.2 新增 `run_pams_ohlcv_daily_v2_formal_audits.py`，按固定三窗口编排 audit 并输出统一汇总；DoD：三窗口子目录和总 summary 同时生成；验证：runner 单测；风险：只跑单窗口、总汇总缺失。

## 2. CLI 与全量流程接线

- [x] 2.1 在 `data_refresh` 中增加 `pams_ohlcv_daily_v2_formal_audits` target；DoD：CLI 可列出并调用；验证：CLI 单测；风险：目标不可发现。
- [x] 2.2 在 `run_pams_ohlcv_daily_v2_full_backfill.py` 中追加 `audit_formal_windows` 步骤；DoD：full backfill 计划默认包含 formal audits；验证：full backfill 单测；风险：后续正式回填仍漏跑三窗口。

## 3. Spec、文档与实跑

- [x] 3.1 更新 `cn-stock-v2-audit-gates` delta spec，把 `2007-2017` 调整为 `2012-2017`，并要求 formal audit 汇总可复核；DoD：`openspec validate --strict` 通过；验证：OpenSpec 校验；风险：规则变更未落文档。
- [x] 3.2 更新 runbook，补充 formal audit runner 的执行命令与产物说明；DoD：后续无需手工拼三次 audit 命令；验证：文档复核；风险：操作口径继续漂移。
- [x] 3.3 实际运行三窗口 formal audits，产出 `2016-2026 / 2012-2017 / 2007-2026` 三份 summary 和总汇总；DoD：总汇总显示三窗口齐全；验证：实跑产物；风险：规则已改但正式产物仍缺失。
