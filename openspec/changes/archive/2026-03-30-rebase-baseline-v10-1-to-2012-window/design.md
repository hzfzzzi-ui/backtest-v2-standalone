## Context

当前 `baseline_V10.1` 是正式主线，但它的官方台账仍指向 `2021-01-04 ~ 2026-03-20` 的 linked experiment。用户要求把“正式 baseline 台账”直接改成从 `2012-01-04` 开始，而且要求直接执行，不再保留 `2021-2026` 作为 `baseline_V10.1` 的官方锚点。

本次变更已经有一条正式实验可以作为新的官方锚点：

- 新实验：`exp_20260328_220801073_478b`
- 口径：`baseline_V10.1` 原策略逻辑不变
- 唯一实质变更：窗口起点改为 `2012-01-04`
- 结果：`CAGR 14.49% / Sharpe 0.704 / MaxDD -36.48% / Trades 628`

因此这次工作不是“重跑找结果”，而是“将现有正式结果登记为新的 baseline_V10.1 官方锚点，并同步刷新台账资产”。

## Goals / Non-Goals

**Goals**

- 让 `baseline_V10.1` 的官方配置快照固定为 `2012-01-04 ~ 2026-03-20`
- 让 `baseline_V10.1` 的 `linked_exp_id` 固定为 `exp_20260328_220801073_478b`
- 让 baseline 索引、ledger、report、digest、champion 与新的官方锚点保持一致
- 保留可回滚路径

**Non-Goals**

- 不修改 `baseline_V10.1` 策略逻辑
- 不新增或替换 baseline 版本号
- 不修改 `baseline_V10.2`
- 不顺手重构 baseline 服务

## Decisions

### 决策 1：保留 `baseline_V10.1` 的 baseline_id，不新建版本

选择：

- 直接重挂既有 `baseline_V10.1`
- 不新建 `baseline_V10.1_fullcycle`、`baseline_V10.1_2012` 之类的新版本名

原因：

- 用户要求的是“正式 baseline 台账改成从 2012-01-04 开始”
- 这次是官方锚点替换，不是平行版本扩张

### 决策 2：以已完成正式实验作为唯一 linked experiment

选择：

- 使用 `exp_20260328_220801073_478b` 作为新的官方 linked experiment

原因：

- 该实验已完成并核对过 run_config 与 perf
- 它是“原 baseline_V10.1 参数，仅起点改为 2012-01-04”的最小变更结果

### 决策 3：通过 baseline 正式资产写入函数更新官方记录

选择：

- 使用 `baseline_access.write_baseline_record()` 刷新 `baseline.json`、`config.json` 和 `index.json`
- 使用 `baseline_report_service.append_experiment_to_baseline()` 追加一条官方重挂 ledger/report 记录

原因：

- 比手工改产物更可审计
- 能保持现有台账格式一致

## Risks / Trade-offs

- 风险：`baseline_V10.1` 的历史“2021-2026 官方锚点”会退为历史事实，不再是当前官方真相  
  缓解：保留旧 experiment 目录，并在最终总结里明确旧锚点 exp_id

- 风险：`latest_champion.json` 会从旧的 study pass 结果切到新的官方重挂 entry  
  缓解：这是有意为之，保证 latest champion 至少与当前 official linked experiment 同步

- 风险：`baseline_report.md` 和 `baseline_digest.md` 会继续保留历史 study 记录，不是“纯净重建”  
  缓解：本次只要求可审计追加，不清空历史；避免破坏既有 ledger 轨迹

## Migration Plan

1. 补齐 OpenSpec proposal / design / specs / tasks
2. 用新的官方窗口配置刷新 `baseline_V10.1/config.json`
3. 将 `baseline_V10.1/baseline.json` 的 `linked_exp_id` 切到 `exp_20260328_220801073_478b`
4. 重写 `outputs/baselines/index.json`
5. 向 `baseline_V10.1` 的 machine/human 台账追加一条“official rebase”记录，并刷新 `latest_champion.json`
6. 核对产物一致性并记录回退路径

回退：

- 将 `baseline_V10.1` 的 `config.json` 与 `baseline.json` 恢复到变更前
- 将 `index.json` 回写到旧值
- 从 ledger/report 中删除本次 official rebase 追加记录
- 将 `latest_champion.json` 恢复到变更前内容
