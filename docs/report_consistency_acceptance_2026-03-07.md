# 报告口径一致性验收记录（2026-03-07）

## 验收目标

验证“同一 `exp_id` 的报告显示值与产物口径一致”，重点覆盖：
- 回测区间一致性
- Universe 数量一致性
- 绩效指标一致性（CAGR/Sharpe/MDD）
- 漏斗来源一致性

## 验收样本

- `exp_20260306_203305`（历史问题样本）
- `exp_20260306_211811`（历史问题样本 + 本地修复后重建）
- `exp_20260307_014641`（冲突请求样本）

## 自动化结果

来源文件：`docs/report_consistency_check_2026-03-07.csv`

| exp_id | start/end 与 run_config | benchmark | 报告区间 | 绩效显示 | 漏斗来源 | source_tag | 结论 |
|---|---|---|---|---|---|---|---|
| exp_20260306_203305 | Fail | Pass | Pass | Pass | Pass | Fail | Legacy（未重算 run_meta） |
| exp_20260306_211811 | Pass | Pass | Pass | Pass | Pass | Pass | Pass |
| exp_20260307_014641 | Fail | Pass | Pass | Pass | Pass | Fail | Legacy（服务端旧镜像产物） |

## 人工抽样复核（exp_20260306_211811）

- 报告区间：`2016-03-01 ~ 2026-03-01`（与 `run_config.universe` 一致）
- 标的数量：`2833`（与 `run_meta.universe.raw_count` 一致）
- 报告章节：含 `§8 口径诊断`
- BREAKOUT 摘要：展示突破参数与组合模式（不再以 MA 快慢线作为主参数）

## 结论

- 代码层修复已生效并通过样本 `exp_20260306_211811` 验证。
- 失败样本主要来自 legacy 产物（旧 `run_meta` 未含新字段），属于预期。
- 部署时需确保服务加载新代码后重跑实验，才能在 API 直接产物中看到完整 `report_consistency` 标记。
