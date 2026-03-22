# Design

## Context

现有证据已经说明两点：

- `V10.2 legacy` 仍然比所有新 market filter / regime 替代方案更可信。
- 主线最该优化的，不是整套市场状态机，而是 `BULL / TREND_MAIN` 内部那些会快速失败的 breakout。

同时，前面的拆解也说明：

- 好交易和坏交易大多都在 `BULL` 入场。
- 能区分 `BULL` 内部大赢家和早死交易的，主要是：
  - `residual_strength_score`
  - `breakout_margin_score`
  - 次级特征如 `leadership_route_score`、`conditional_institution_proxy_score`
- 若继续改市场过滤器，会直接改写交易集合，容易漏掉早期 runner。

因此这轮设计目标不是“再造状态机”，而是做一个**只在 `BULL / TREND_MAIN` 内部生效的单侧 veto**。

## Goals / Non-Goals

**Goals**

- 在不改变默认主线的前提下，为 breakout provider 增加一个可选的 `bull_breakout_quality_veto`。
- 只使用现有预计算特征，不引入新数据链或新宏观变量。
- 只拦截明显差样本，不重写主排序核。
- 让 veto 在产物中可审计：能看到阻断次数、阻断原因、阈值配置。
- 跑一轮最小 A/B，验证：
  - 是否减少 `BULL` 内部失败 breakout
  - 是否不明显伤害早期 runner

**Non-Goals**

- 不替换 `ma200_legacy`
- 不改 `market_state / trade_mode` 定义
- 不改股票池、exit、资金管理主壳
- 不在本轮引入多特征打分模型或学习型阈值
- 不把 veto 推到非 `BULL` 阶段

## Decisions

### 决策 1：veto 只作用于 `BULL / TREND_MAIN`

原因：

- 当前要解决的是 `BULL` 内部失败 breakout。
- `legacy` 语义下 `BULL` 就是主趋势开闸区，不需要额外扩展 `DayContext.trade_mode` 合同。
- 只依赖 `ctx.market_state == "BULL"` 且 `ctx.risk_on == True`，改动最小。

### 决策 2：首轮只用两个粗阈值

首轮只启用：

- `min_residual_strength_score`
- `min_breakout_margin_score`

原因：

- 这两个特征在前面 cohort 分析里已经表现出区分力。
- 低自由度、易解释。
- 避免把 veto 变成新的复杂排序器。

本轮不把 `ATR%`、`leadership_route`、`institution_proxy` 一起绑进 veto，以免一次引入多个主改动。

### 决策 3：veto 只打 breakout / overlap，不打 pure pullback

原因：

- 当前问题定义是“坏 breakout veto”。
- `alpha_source in {"breakout", "pullback_overlap"}` 仍然覆盖了 breakout 主路径。
- 不把 pure pullback 一并误伤，保持问题边界干净。

### 决策 4：用 provider 层阻断，而不是后段清空订单

原因：

- 这样可以在 `portfolio_candidates.csv` 和 `diag_reason_counts` 里留下清晰阻断痕迹。
- 便于审计“信号存在但被 veto”，而不是后段无痕消失。
- 不改订单规划和填单壳。

### 决策 5：AB 只跑一个 B 版本

原因：

- 研究纪律要求单轮只做一个主改动。
- 本轮 A/B 定义为：
  - A = `baseline_V10.2`
  - B = `baseline_V10.2 + bull_breakout_quality_veto`
- 阈值先固定为粗阈值，不同时扫多个参数。

建议首轮阈值：

- `min_residual_strength_score = 0.94`
- `min_breakout_margin_score = 0.55`

这两个值位于前面赢家/失败组均值之间，属于可解释的粗阈值，不做精细优化。

## Technical Plan

1. 配置层
   - 在 `StrategyConfig.params` / semantic ranking 配置透传：
     - `bull_breakout_quality_veto_enabled`
     - `bull_breakout_quality_veto_min_residual_strength_score`
     - `bull_breakout_quality_veto_min_breakout_margin_score`

2. provider config/runtime
   - 在 `BreakoutProviderConfig` 增加上述字段
   - 在 `build_breakout_provider_config()` / `apply_breakout_provider_config()` 完成透传

3. provider day_signals
   - 在 breakout candidate loop 中，在 `buy_sigs.append(...)` 前执行 veto：
     - `ctx.market_state == "BULL"`
     - `ctx.risk_on == True`
     - `alpha_source in {"breakout", "pullback_overlap"}`
     - `residual_strength_score < threshold` 或 `breakout_margin_score < threshold`
   - 命中时：
     - `continue`
     - 计入稳定 reason/counter

4. 诊断与产物
   - provider 增加：
     - `bull_breakout_quality_veto_block_count`
     - `bull_breakout_quality_veto_residual_block_count`
     - `bull_breakout_quality_veto_margin_block_count`
   - `DaySignals.diagnostics` 加入当日 veto 统计
   - `result_bridge` / metrics / run_meta 输出这些计数器

5. AB 脚本
   - 复用当前正式 `baseline_V10.2` 输入配置
   - 唯一 intended diff 是上述 3 个 veto 参数
   - 产出：
     - `summary.json`
     - `report.md`
     - `performance_comparison.csv`
     - `bull_trade_quality_comparison.csv`

## Risks / Trade-offs

- [风险] 粗阈值仍可能误伤早期 runner  
  -> 在 AB 后专门拆 `baseline-only` 的早期 runner 是否被 veto。

- [风险] provider 层阻断会改变 candidate 数与现金/槽位竞争顺序  
  -> 这是本轮 intended effect，但要额外输出 `SKIP_NO_CASH` 变化，避免误把“候选减少”当成“过滤更准”。

- [风险] 只用两个特征可能改善有限  
  -> 这是可接受的；本轮目标是验证方向，不追求一次性收益最大化。

## Migration Plan

1. 补齐 delta specs 与 tasks
2. 实现可选 veto 配置与 provider 阻断
3. 补单测，确保默认配置行为不变
4. 运行最小 A/B
5. 输出正式对照报告

回退策略：

- 删除新增配置字段
- 删除 provider veto 逻辑与计数器
- 删除本轮 AB 脚本和产物
- 默认 baseline 不受影响，可直接回到现状

## Open Questions

- 如果这轮 A/B 方向成立，下一轮是优先加 `ATR%` 还是 `leadership_route`，本 change 不预先承诺。
- 如果 veto 减少坏交易但同时损失 early runner，是否优先转去现金/槽位层，本 change 不处理。
