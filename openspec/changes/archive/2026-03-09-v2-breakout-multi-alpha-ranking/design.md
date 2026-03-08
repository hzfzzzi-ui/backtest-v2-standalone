## Context

当前生产 runtime 中，`breakout_trend` 走专用 provider 路径：[breakout_signal_provider.py](C:\Users\hzfzzzi\openclaw\backtest_V2_standalone\backend\core\engine_vector\breakout_signal_provider.py)，候选进入统一组合层排序/下单：[portfolio_builder.py](C:\Users\hzfzzzi\openclaw\backtest_V2_standalone\backend\core\portfolio\portfolio_builder.py)。这条路径已经支持：

- breakout 候选矩阵预计算
- `momentum_top_pct` 前置筛选
- `enable_strength_rank` / `enable_multifactor_rank` 排序钩子
- `portfolio_candidates.csv` 候选审计输出

但当前仍有两个明显缺口：

1. alpha 来源单一，候选稀疏，仓位利用率不足；
2. 行业相关逻辑当前使用 `load_industry_mapping()` 读取最新行业记录，不适合作为新的行业排序依据。

## Goals / Non-Goals

**Goals:**

- 在不破坏 baseline 可复现性的前提下，为 breakout 主路径补充默认关闭的 pullback 候选。
- 在统一排序层增加 residual / sector / volume_price 三类分数，并支持小范围权重组合。
- 保留 `t` 日收盘生成信号、`t+1` 执行的现有日频契约。
- 让每笔候选和每笔最终入选都能追溯 alpha 来源和分数贡献。
- 通过三阶段最小实验直接给出 AB 结果，而不是先改 UI 或做大规模参数搜索。

**Non-Goals:**

- 不替换或删除现有 breakout 模块。
- 不修改手续费、滑点、股票池、benchmark、成交规则或评价口径。
- 不引入机器学习模型、回归残差拟合器或大规模调参。
- 不把这轮研究结果直接升级为新的默认 baseline。

## Decisions

### D1: 复用 breakout provider，不新建第二套 runtime

pullback 候选直接并入 `BreakoutTrendProvider.precompute()/day_signals()`，与 breakout 共用同一组矩阵、benchmark、tradable 掩码和 `t+1` 执行通路。  
不采用“新增第二个策略类 + 双引擎合并”方案，因为那会扩大 diff、增加口径漂移风险，也不利于三阶段 AB。

### D2: 新 alpha 与新排序全部走 `strategy.params` 显式开关

所有新增能力默认关闭，并通过 `strategy.params` 控制，例如：

- `enable_pullback_alpha`
- `pullback_variant`
- `enable_residual_rank`
- `enable_sector_quality_rank`
- `multi_alpha_score_weights`

不采用 API 顶层散落字段，以避免再次引入配置源分裂。

### D3: 候选分数优先通过 `Signal.meta` 与 `candidate_audit` 透传

provider 负责在 buy signal 上写入：

- `alpha_source`
- `residual_strength_score`
- `sector_strength_score`
- `volume_price_quality_score`
- `final_score`

组合层 `build_rebalance_orders()` 负责读取这些 meta 做排序，并把相同字段写入 `candidate_audit`。  
不扩展新的跨层全局 map 结构，避免同时修改 `DaySignals` 协议、多个 runtime 路径和 report 层。

### D4: Phase 3 前必须引入 PIT-safe 行业日级映射矩阵

行业强度和行业相对强弱只允许使用 `pit_industry_history` 在当日可见的行业归属。实现上新增 provider 方法，按 `symbols + start + end` 读取区间内行业历史，并构造日级行业矩阵。  
不复用当前 `load_industry_mapping()` 的“最新有效记录”逻辑，因为那会把未来行业归属带回历史。

### D5: 排序层增量实现，不推翻现有选股器

组合层继续使用 `build_rebalance_orders()`，只增加一个更高优先级的 `final_score` 排序分支：

- Phase 1: 不启用统一排序，只验证 pullback 是否补充候选
- Phase 2: 若 `enable_residual_rank=true`，按 residual score 排序
- Phase 3: 若 `enable_sector_quality_rank=true`，按综合分排序

不重做新的 order planner，以保持选股、仓位、下单、资金检查口径一致。

### D6: 诊断产物以现有 `portfolio_candidates.csv` 为主，再派生研究 csv

运行期继续输出 `portfolio_candidates.csv`，研究脚本再派生：

- `candidate_signals.csv`
- `alpha_funnel.csv`
- `score_diagnostics.csv`
- `ab_summary.csv`

不把所有研究摘要直接塞进 `run_meta.json`，避免污染主协议；`run_meta.json` 只增加必要的 audit 摘要与产物路径引用。

## Risks / Trade-offs

- [风险] pullback 候选会显著增多，可能把交易数和噪音一起放大。  
  缓解：Phase 1 只做 2 到 3 个朴素变体，先看候选数、持仓数、MaxDD，不做大范围参数扫描。

- [风险] 行业映射若仍沿用最新记录，会直接污染 Phase 3 结论。  
  缓解：把 PIT-safe 行业矩阵作为 Phase 3 的硬前置；若行业历史加载失败，Phase 3 必须阻断。

- [风险] 排序层若直接做硬过滤，可能把“alpha 增加”误做成“门控收紧”。  
  缓解：残差、行业、量价先只做排序分，不做硬过滤。

- [风险] 新增诊断字段过多，可能让 `portfolio_candidates.csv` 体积明显变大。  
  缓解：默认只在 `fast_mode=false` 的研究实验中输出完整 candidate audit；主线快速运行仍允许轻量模式。

- [风险] 综合分权重过多会演变成隐性调参。  
  缓解：权重只固定测试 2 到 3 组，写死在研究脚本中，不开放网格搜索。

## Migration Plan

1. 先补 OpenSpec 和 PIT-safe 行业映射加载接口。
2. 在 breakout provider 中接入 pullback 候选与 per-signal score meta，默认关闭。
3. 在 `build_rebalance_orders()` 中接入统一排序分支与候选审计字段。
4. 新增研究脚本，固定 baseline 派生 4 组实验：baseline / phase1 / phase2 / phase3。
5. 仅在审计通过后输出 AB 汇总；若发现时间错位或行业映射穿越，立即停止 Phase 3。
6. 回退方式：关闭新增参数或停止使用研究脚本；baseline 默认行为不变。

## Open Questions

- pullback 朴素版优先保留几种变体最合适：2 个还是 3 个。
- `score_diagnostics.csv` 是否只保留每日 top 20 候选，避免文件过大。
- 是否需要把 `candidate_signals.csv` 正式加入标准 artifact 协议，还是先保持研究脚本侧产物。
