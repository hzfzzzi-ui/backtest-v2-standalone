## 1. Hard Gate 语义调整

- [x] 1.1 在 `pams_ohlcv_daily_v2_common.py` 中显式区分 hard gate windows 与 advisory windows；DoD：formal runner 和测试不再把 `2007_2026` 当成 required；验证：单测；风险：汇总语义继续混淆。
- [x] 1.2 更新 `run_pams_ohlcv_daily_v2_formal_audits.py` summary，输出 `required_windows / advisory_windows / formal_windows_complete / all_windows_complete`；DoD：hard gate 只看两窗口；验证：runner 单测；风险：旧 summary 字段误导使用者。

## 2. Spec 与文档同步

- [x] 2.1 更新 `cn-stock-v2-audit-gates` 主 spec，写明 `2007-2026` 为 advisory audit；DoD：spec 不再把它写成 hard gate；验证：OpenSpec 校验；风险：实现与规则脱节。
- [x] 2.2 更新 runbook，写明“两硬一参考”；DoD：操作口径可复核；验证：文档复核；风险：使用方仍把三窗口当成同级 hard gate。

## 3. 回归与继续审计

- [x] 3.1 更新 `tests/unit/test_run_pams_ohlcv_daily_v2_formal_audits.py`；DoD：新 summary 语义受测试保护；验证：pytest；风险：后续回归把 `2007_2026` 又带回 hard gate。
- [x] 3.2 重跑 formal audits，产出新 summary；DoD：summary 显示 `required_windows = 2016_2026 / 2012_2017`；验证：实跑产物；风险：规则已改但正式产物未刷新。
- [x] 3.3 基于新 summary 继续审计 `critical_exception_rows` 的 issue_type / phase / top symbols；DoD：能给出下一步治理优先级；验证：产物分析；风险：继续停留在笼统总数。
