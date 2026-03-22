## 1. 规格与边界

- [x] 1.1 补齐 `BJ post-2021-11-15` side-evidence 归类的 OpenSpec proposal/design/specs/tasks。DoD: proposal/design/specs/tasks 完整，且 `openspec validate classify-bj-post-20211115-side-evidence --type change --strict` 通过；风险：如果 spec 不先固化，`bj_post_20211115` 与 `bj_pre_20211115` 的边界会继续漂移。

## 2. 实现与回归

- [x] 2.1 修改 `update_pams_ohlcv_daily_v2.py`，让 `bj_post_20211115` 中带同日侧证据但缺 `daily/suspend_d` 的行记为 `synthetic_gap_fill`。DoD: `bj_post_20211115` 这类行不再落入 `source_unresolved`，且 `bj_pre_20211115` 分支保持不变；验证：单测覆盖正反两条分支；风险：如果误扩到 `bj_pre_20211115`，会洗掉 mapping failure。
- [x] 2.2 更新相关单测。DoD: `tests/unit/test_update_pams_ohlcv_daily_v2.py` 覆盖 `bj_post_20211115` side-evidence 分类和 `bj_pre_20211115` 非回归；验证：`pytest tests/unit/test_update_pams_ohlcv_daily_v2.py tests/unit/test_audit_pams_ohlcv_daily_v2.py -q`；风险：无测试时容易回归到把 BJ 全部继续算成 `eligible_no_source`。

## 3. 数据修复与验证

- [x] 3.1 先对头部 `BJ post-2021-11-15` unresolved symbol 做 slice rebuild。DoD: 头部批次对应 symbol 的 `source_unresolved` 下降、`synthetic_gap_fill` 上升；验证：slice rebuild 后查库；风险：直接全量重建成本高且难归因。
- [x] 3.2 重跑 full-window audit，记录 `eligible_no_source`、`critical_exception_rows`、`synthetic_gap_fill_rows` 和 runtime 变化。DoD: 产出新的 `summary.json` 且可与上一轮正式 run 对比；验证：`outputs/ops/.../summary.json`；风险：只看局部 rebuild 不看全窗口 audit 会误判治理效果。
