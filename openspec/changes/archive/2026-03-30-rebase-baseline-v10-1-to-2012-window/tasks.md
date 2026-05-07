## 1. Change Artifacts

- [x] 1.1 补齐 `rebase-baseline-v10-1-to-2012-window` 的 proposal / design / delta specs，明确这是既有官方 baseline 锚点重挂，不是新 baseline 注册；验证：`openspec validate --changes "rebase-baseline-v10-1-to-2012-window"` 通过；风险：把重挂误写成新 baseline，导致台账语义继续分叉。

## 2. Official Baseline Rebase

- [x] 2.1 将 `baseline_V10.1` 的官方配置快照改为 `2012-01-04 ~ 2026-03-20`，并把 `linked_exp_id` 重挂到 `exp_20260328_220801073_478b`；验证：`baseline.json`、`config.json`、`index.json` 三处一致；风险：只改一处导致 baseline 元数据和索引漂移。
- [x] 2.2 向 `baseline_V10.1` 的 baseline ledger/report 追加一条 official rebase 记录，并在 PASS 情况下刷新 `latest_champion.json`；验证：`experiment_ledger.jsonl`、`report_index.json`、`baseline_report.md`、`baseline_digest.md`、`latest_champion.json` 都出现新条目；风险：最新 champion 仍指向旧 study pass，而不是当前 official linked experiment。

## 3. Verification

- [x] 3.1 核对新的 `baseline_V10.1` 官方锚点确实对应 `2012-01-04` 起点和 `exp_20260328_220801073_478b`；验证：检查 baseline 产物与新实验 `perf/run_config`；风险：窗口和 linked experiment 对不上。
- [x] 3.2 记录风险、回退和与旧官方锚点的差异；验证：最终总结必须给出旧 exp、新 exp 和关键指标差异；风险：只给新结果，不给回退与旧锚点上下文。
