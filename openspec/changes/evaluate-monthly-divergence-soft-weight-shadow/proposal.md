## Why

`monthly_divergence_rate` 当前作为 `bull_only_tiebreak` 接入 `baseline_V10_1` 时，已经证明链路是通的，但在 `1217 / 1226` 两窗口里没有产生任何行为差异。原因不是因子无效，而是插入方式过弱：它只在主排序完全同分时才有机会生效。

对于一个月频、中周期的 moneyflow 因子，更合理的插入方式不是替换主排序，也不是只做同分打破，而是：

- 保留当前 baseline 主排序壳
- 每月更新一次 moneyflow 分数
- 只在计划买入范围内，对候选下单金额做辅助权重调整

这轮 change 要验证的，就是这种“月度辅助权重”接法是否比 `tiebreak` 更有机会产生可审计差异，同时又不直接推翻现有 baseline 壳。

## What Changes

- 新增正式 study `v10/moneyflow_monthly_soft_weight_s1`
- study 继续消费现代 `moneyflow_factor_real_mainline_s2` 的 `factor_snapshot.csv`
- 变体最小化为：
  - `B0`
  - `SCORE_WEIGHT_BASE`
  - `MF_SOFT_10`
  - `MF_SOFT_20`
- 继续沿用 `runtime_config_path + runtime_config_json` 作为唯一执行真相
- 增加 generated thin script，并完成真实 study 运行

## Capabilities

### New Capabilities

- `moneyflow-soft-weight-stock-baseline-study`
  - 定义 `monthly_divergence_rate` 作为 A 股 baseline 月度辅助权重的最小 shadow study
  - 支持在不改主排序的前提下，对计划买入范围内的候选做 score-weighted sizing 调整

## Impact

- 影响代码：
  - `research/studies/v10/moneyflow_monthly_soft_weight_s1.study.yaml`
  - `research/studies/v10/configs/moneyflow_monthly_soft_weight_s1/*`
  - `backend/scripts/generated/run_v10_moneyflow_monthly_soft_weight_s1.py`
  - `openspec/changes/evaluate-monthly-divergence-soft-weight-shadow/*`
- 影响系统：
  - 仅新增 research-only study 入口
  - 不改变当前 live baseline 默认行为
- 影响结论：
  - 回答 `monthly_divergence_rate` 更适合做“辅助权重”还是“继续停留在研究层”
