## Context

当前 runtime 已经支持 `moneyflow_overlay.mode = soft_weight`。它的真实行为不是改候选排序，而是：

- 保持 baseline 的候选顺序不变
- 只对计划买入范围内的候选，使用 `overlay_score` 覆盖 `score_weight_score`
- 再由 `weight_mode = score_weighted` 把分数映射到 `score_weight_min_scale ~ score_weight_max_scale`

也就是说，这条路径天然就符合“只在一定范围内做辅助权重调整”的目标，不需要改主排序，也不需要扩 runtime 新能力。

## Goals / Non-Goals

**Goals**

- 定义一条新的正式 `v10` study，专门评估 `monthly_divergence_rate` 作为月度辅助权重时的最小 A/B
- 保证实验能区分：
  - 只是启用 `score_weighted` sizing 的效果
  - 真正由 `moneyflow` 驱动的 soft-weight 效果
- 保持当前 baseline 主排序、regime、market_filter、exits、risk_budget 不变
- 完成 `1217 / 1226` 两窗口真实运行

**Non-Goals**

- 不替换当前 live 排序函数
- 不修改 `moneyflow_overlay` runtime 合同
- 不新增 band 限制参数或新的 overlay mode
- 不直接把结果升格为 live baseline

## Decisions

### 1. 使用现代 `daily_factor_snapshot`

继续使用：

- `outputs/studies/factors/moneyflow_factor_real_mainline_s2/1217/A_H20_CONTROL/machine/factor_snapshot.csv`
- `outputs/studies/factors/moneyflow_factor_real_mainline_s2/1226/A_H20_CONTROL/machine/factor_snapshot.csv`

原因：

- 这条路径已经在上一轮 `moneyflow_monthly_shadow_s1` 里验证过可执行
- 它与当前 `2012` 起点正式口径一致

### 2. 变体最小化为四组

- `B0`
  - 当前 baseline 控制组
- `SCORE_WEIGHT_BASE`
  - 不启用 moneyflow overlay
  - 只把 sizing 改成 `score_weighted`
  - 用当前 baseline 主分数驱动权重缩放
- `MF_SOFT_10`
  - 启用 `moneyflow_overlay.mode = soft_weight`
  - `score_weight_min_scale = 0.9`
  - `score_weight_max_scale = 1.1`
- `MF_SOFT_20`
  - 同上，但 band 更宽
  - `score_weight_min_scale = 0.8`
  - `score_weight_max_scale = 1.2`

原因：

- `B0` 回答“当前 baseline 壳表现如何”
- `SCORE_WEIGHT_BASE` 回答“只是打开 score-weighted sizing 会怎样”
- `MF_SOFT_10 / 20` 才回答“moneyflow 作为辅助权重是否有额外价值”

### 3. 执行真相继续只走 runtime config

沿用上一轮已验证的结构：

- window 级 `runtime_config_path`
- variant 级 `runtime_config_json`
- `study_runner` 递归 merge

不再回退到 `workbench_config`

### 4. “一定范围内的股票”采用现有 runtime 语义

这轮不新增新 band 参数，而直接采用当前 `soft_weight` 的现有语义：

- 只在 `build_score_weight_scale_maps()` 内对 `planned` 候选生效
- `planned` 本身只覆盖将要进入计划买入范围的 top slots 候选

这已经满足“有限范围内的股票做权重调整”，且不额外引入新的 runtime 复杂度。

### 5. 正式窗口仍只保留 `1217 / 1226`

- `1217`：`2012-01-04 ~ 2017-12-29`
- `1226`：`2012-01-04 ~ 2026-03-01`

原因：

- 这是最小可归因研究
- 足够判断辅助权重在硬门槛窗和全周期窗里是否一致

## Risks / Trade-offs

- `score_weighted` sizing 本身就会改变行为，所以必须保留 `SCORE_WEIGHT_BASE` 做控制
- `soft_weight` 改的是下单金额，不是候选排序；若候选本身已很强，收益差异可能仍然不大
- 当前 runtime 的“计划范围”由 slots/top-k 自然决定，不是显式参数化 band；这会降低解释精细度，但能避免再开一轮 runtime 改造
- 若 `monthly_divergence_rate` 对 sizing 层没有额外价值，结论应是“不适合当前 baseline 壳的辅助权重接法”，而不是因子本身无研究价值
