## Context

当前仓库已经有两条可复用能力：

- `baseline_V10.1` 的正式执行链路，实际通过 `enable_multifactor_rank + mf_score_map` 在下游组合构建阶段消费排序分数。
- 独立的 `A 股主力资金分歧率` 月频 study，已经能输出 `monthly_factor_panel.csv` 与 `monthly_coverage_ledger.csv`，并且 `2326_HC` 窗口具备较高覆盖率。

这次用户要的是一条 `2023-2026` 局部接入实验，而不是把 `moneyflow` 直接写入正式 baseline。约束有三点：

- 不能改写 `baseline_V10.1` 的默认正式配置。
- 不能把 `moneyflow` 缺失当成低分，也不能把月频观察做成未来函数。
- 要能直接运行实验，并且在结果里看见 overlay 是否真的启用、何时启用、按什么模式启用。

## Goals / Non-Goals

**Goals:**

- 新增一条默认关闭的 `moneyflow overlay` 运行时能力，通过 `asset_context.moneyflow_overlay` 开启。
- 首轮 `23-26` 实验只复用既有月频分歧率 study 产物，读取 `monthly_factor_panel.csv` 与 `monthly_coverage_ledger.csv`，不重新定义因子口径。
- 支持三种模式：`shadow`、`tiebreak`、`soft_weight`。
- 保证慢频合同为“月末观察、次交易日生效、月内冻结”，并用月份覆盖率 gate 控制启停。
- 输出最小但足够的诊断信息，至少能回答：当天 overlay 是否生效、当前冻结自哪个观察日、当前分数源是否可用。

**Non-Goals:**

- 不把 `moneyflow` 直接并入 `baseline_V10.1` 默认配置或正式 baseline 归档。
- 不在本次实现中新增数据库级 monthly factor materialization。
- 不在本次实现中推进 `2007-2017` 或 `2007-2026` 全窗口实验。
- 不在本次实现中改变 breakout 主信号、benchmark regime、exit rules、risk budget。

## Decisions

### D1: Overlay 源采用既有月频 study 产物，而不是直接读 side table

首轮实验直接读取既有 `A 股主力资金分歧率` study 产物中的：

- `monthly_factor_panel.csv`
- `monthly_coverage_ledger.csv`

并通过 `asset_context.moneyflow_overlay.factor_panel_path / coverage_ledger_path` 指向具体文件。

原因：

- 这两份文件已经固化了 `23-26` 的覆盖率门槛与月频因子口径。
- 直接读 CSV 比在 baseline 运行时重做 SQL 聚合更小、更稳、更容易回退。
- 用户当前要的是“先做 `23-26` 接入实验”，不是把 monthly factor 生产化。

备选方案：

- 运行时直接从 `pit_stock_moneyflow` / `pit_stock_moneyflow_v2` 聚合月频因子。放弃原因：改动范围更大，且会把“因子定义”和“接入实验”绑在一起。

### D2: Overlay 配置放在 `asset_context.moneyflow_overlay`

新增运行时契约：

- `asset_context.moneyflow_overlay.enabled`
- `asset_context.moneyflow_overlay.mode`
- `asset_context.moneyflow_overlay.factor_panel_path`
- `asset_context.moneyflow_overlay.coverage_ledger_path`
- `asset_context.moneyflow_overlay.score_field`

默认关闭；只有 study variant 显式 patch 时才开启。

原因：

- `experiment_runner` 会原样保留 `config_json` 里的未知字段，并在 `foundation_shell` 里把 `asset_context` 透传到 stage pipeline。
- 这样不需要改动公共 API 输入 schema，也不需要污染正式配置字段。

备选方案：

- 复用 execution override 顶层字段。放弃原因：当前 override 白名单较窄，且本次只是实验能力，不值得扩张公共 override 面。

### D3: 冻结合同按“观察日驱动 decision date”

`monthly_factor_panel.csv` 中已经同时给出：

- `observation_date`
- `execution_date`

在当前 `next_open` 执行合同下，真正需要在运行时消费的是 `decision date` 侧的冻结值：

- 从 `observation_date` 当天收盘后的决策开始生效
- 影响次交易日开盘成交
- 之后一直冻结到下一次 `observation_date` 前一日

原因：

- 当前引擎的买入决策发生在收盘后，下单执行发生在次日开盘。
- 如果把分数从 `execution_date` 当天才开始用于日内决策，会错过本应在次日开盘执行的首日入场。

备选方案：

- 直接按 `execution_date` 映射 decision date。放弃原因：会让首个生效日延后一根 bar。

### D4: `shadow / tiebreak / soft_weight` 分别走不同的最小干预路径

- `shadow`
  - 加载 overlay 与 gate
  - 仅写入诊断，不改变排序与仓位
- `tiebreak`
  - 仍以 baseline 当前主排序分数为主键
  - 仅把 overlay 分数作为同主分数下的次级排序键
- `soft_weight`
  - 维持 baseline 当前排序顺序
  - 用 overlay 分数驱动 `score_weighted` 仓位缩放

原因：

- 这三种模式分别对应“只观察”“改排序不改主壳”“不改排序只改仓位”。
- 它们都能在现有 `mf_score_map` / `score_weighted` 体系上最小落地，不需要重写 breakout provider。

备选方案：

- 直接把 overlay 分数替换为新的主排序分数。放弃原因：这等价于改 baseline 主壳，风险过高。

### D5: 组合构建新增显式 overlay mode 分支，而不是隐式复用旧 `mf_score_map` 语义

现有运行时把 `mf_score_map` 当成单一排序分数使用。为了避免“排序”和“仓位加权”都被 overlay 一起改掉，本次在组合构建里增加显式 `overlay_mode` 分支：

- `off` / `shadow`：维持旧行为
- `tiebreak`：按 `baseline_score desc, overlay_score desc, symbol asc`
- `soft_weight`：按 `baseline_score` 排序，但用 `overlay_score` 做 `score_weighted`

原因：

- 旧逻辑把排序和加权耦合在同一个 `mf_score_map` 上，不足以表达这次实验要的三种模式。
- 显式分支更容易审计，也更容易确认“这次只改了哪一层”。

## Risks / Trade-offs

- [Risk] Overlay 源来自 study 产物路径，存在路径失配或旧产物被覆盖的风险
  → Mitigation：运行前校验两个 CSV 路径存在且字段齐全，路径写入 `run_meta` 与 diagnostics。

- [Risk] `soft_weight` 仍依赖现有 `score_weighted` 语义，若某天 overlay score 缺失，可能回退到中性 0.5
  → Mitigation：缺失与低覆盖统一 gate 掉；gate 关闭时整天回到 baseline 行为，不允许半启用。

- [Risk] `tiebreak` 实际效果可能较弱，因为它只在主排序接近时发挥作用
  → Mitigation：保留 `soft_weight` 对照组，并在结果里单独比较交易数、换手、持仓差异。

- [Risk] 首轮实验使用现有 `23-26` factor panel，若后续因子 study 口径更新，overlay 结果会跟着变化
  → Mitigation：study variant 把输入文件路径写死到具体产物目录，本次实验先追求可复现，不追求“永远读最新”。

## Migration Plan

1. 新增 OpenSpec 工件，固定 `23-26` overlay 试验边界。
2. 实现 overlay loader 与冻结映射，默认关闭。
3. 在组合构建阶段增加 `shadow / tiebreak / soft_weight` 分支，并补最小诊断字段。
4. 新增 `research/studies/v10` 下的 `23-26` study，包含 `B0 / TIEBREAK / SOFT_WEIGHT` 变体。
5. 运行 `23-26` study，并用 `baseline_V10.1` 做对照。

回退策略：

- 删除 study YAML 与 overlay loader/分支代码即可回退；正式 baseline 配置不需要回滚。
- 若实验结果不可靠，只保留 change 工件与结果目录，不合并到正式 baseline。

## Open Questions

- `shadow` 是否需要单独写出 overlay 候选 CSV。当前先依赖 `portfolio_daily.csv` 与 `portfolio_candidates.csv` 的新增诊断列，不额外新增独立工件。
- `soft_weight` 的缩放区间是否需要进一步收紧。当前先用保守区间 `0.9 ~ 1.1`。 
