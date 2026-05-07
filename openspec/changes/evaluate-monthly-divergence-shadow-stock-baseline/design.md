## Context

当前仓库已经具备 `moneyflow_overlay` 的正式执行合同，并且支持 `shadow`、`tiebreak`、`bull_only_tiebreak`、`soft_weight` 等以 `daily_factor_snapshot` 为输入的接法。问题不在 runtime 缺能力，而在于现有 `v10/moneyflow_overlay_2326` 研究仍依赖 legacy monthly panel、窗口口径较旧、变体过多，不适合作为当前 `2012` 起点正式研究纪律下的最小决策依据。

这轮需要的不是扩更多 overlay 模式，而是把 `monthly_divergence_rate` 做成一轮最小、可归因、可审计的 `stock baseline shadow` A/B：

- 只比较 `B0 / SHADOW / BULL_ONLY_TIEBREAK`
- 只消费现代 `moneyflow_factor_real_mainline_s2` 的 `factor_snapshot.csv`
- 只覆盖正式 `1217 / 1226` 两个窗口
- 不改变当前 baseline 默认行为

## Goals / Non-Goals

**Goals**

- 定义一条新的正式 `v10` study，专门评估 `monthly_divergence_rate` 作为 stock baseline shadow 候选的最小 A/B
- 让 study 输入切到现代 `daily_factor_snapshot` 路径，消除对 legacy monthly panel / coverage ledger 的依赖
- 保持 `baseline_V10_1` compare-only 身份，study 不自动 append baseline
- 保证新 study 具备 generated thin script，符合当前正式 study 入口治理

**Non-Goals**

- 不修改 `moneyflow_overlay` runtime 合同与候选计划逻辑
- 不直接把 `monthly_divergence_rate` 接入正式 live baseline
- 不在这一轮同时评估 `soft_weight`、`veto_bottom*` 或更多 moneyflow 接法
- 不重写 `moneyflow_factor_real_mainline_s2` 因子研究逻辑

## Decisions

### 1. 使用现代 `daily_factor_snapshot`，不复用 legacy monthly panel

选择：

- 新 study 直接消费 `outputs/studies/factors/moneyflow_factor_real_mainline_s2/<window>/A_H20_CONTROL/machine/factor_snapshot.csv`

原因：

- 当前 `moneyflow_factor_real_mainline_s2` 已验证 `H20` 比 `H60` 更适合作为主控制口径
- `factor_snapshot.csv` 是正式 study 产物，字段稳定，包含 `date / symbol / factor_id / rank_value / availability_flag`
- 避免继续把 legacy panel 变成新的运行真相

### 2. 变体只保留 `B0 / SHADOW / BULL_ONLY_TIEBREAK`

选择：

- `B0`：控制组
- `SHADOW`：只开启 overlay 诊断，不改变 baseline 行为
- `BULL_ONLY_TIEBREAK`：只在 `BULL` 状态内，用 moneyflow 作为并列打破

原因：

- 这轮目标是判断“是否值得进入 shadow 队列”，不是把所有接法一口气跑完
- `bull_only_tiebreak` 比全时段 `tiebreak` 更符合这条因子“中周期 context 增强”的研究判断
- `shadow` 组可以单独验证 overlay 是否真的被装载

### 3. 使用 `runtime_config_path` 作为唯一 window 基础真相

选择：

- `1217` 和 `1226` 各自物化一份 window base runtime config
- base config 负责：
  - 窗口范围
  - baseline 壳 runtime 参数
  - `moneyflow_overlay` 的 source metadata
- variant 只通过 `runtime_config_json` 叠加：
  - `enabled`
  - `mode`
  - `factor_role`
  - `apply_layer`

原因：

- 当前 baseline-like study 实际消费的是 backend runtime config，不是 semantic workbench config
- 若继续使用 `workbench_config_path/workbench_config`，会被 semantic schema 拒绝
- 运行真相应只有一条：`runtime_config` -> `execution_overrides`

### 4. `study_runner` 支持 window base runtime config 与 variant runtime patch 递归合并

选择：

- 当 window 和 variant 同时提供字典型 `request_overrides` 时，`study_runner` 递归合并 nested mapping，而不是只做顶层浅覆盖
- merge 完毕后再 materialize `runtime_config_json` / `workbench_config`

原因：

- moneyflow shadow study 需要 window base 提供 `factor_snapshot_path / score_source / factor_id`
- variant 只补 `enabled / mode / factor_role`
- 若保持浅合并，variant 会覆盖掉 window 已提供的 source metadata

### 5. 正式窗口只保留 `1217 / 1226`

选择：

- `1217`：`2012-01-04 ~ 2017-12-29`
- `1226`：`2012-01-04 ~ 2026-03-01`

原因：

- 这是最小 A/B，不需要把 `1222` 也拉进来
- `1217 + 1226` 足够判断该 shadow 接法是否只在长窗好看，还是对硬门槛窗也有基本稳定性

### 6. 零差异结果本身也是有效结论

事实：

- `SHADOW` 与 `BULL_ONLY_TIEBREAK` 都已真实接入 overlay 数据源
- 两窗口真实运行后，`B0 / SHADOW / BULL_ONLY_TIEBREAK` 三组绩效完全一致
- `BULL_ONLY_TIEBREAK` 的有效样本行中，不存在同日 `mf_score` 同分组

解释：

- `SHADOW` 设计上就不应改变主排序行为
- `BULL_ONLY_TIEBREAK` 只作为次级排序键，不会改变主分数
- 在当前两窗口真实运行里，它没有得到任何可打破同分的机会

这不是接入失败，而是“模式接通，但在当前 baseline 壳上行为上惰性”

## Risks / Trade-offs

- 若 `moneyflow_factor_real_mainline_s2` 产物被清理或替换，新 study 路径会失效
- `bull_only_tiebreak` 可能长期只在极少场景下生效，导致 A/B 差异天然很小
- `candidate_signals.csv` 当前暴露的是 overlay 观测值与 source gate，不完全等于 plan 层“实际参与排序”的标志，解读时需谨慎
- 这轮只做最小 shadow，不足以直接决定是否应该升格进正式 baseline
