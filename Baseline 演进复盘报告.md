# Baseline 演进复盘报告

- 更新日期：`2026-03-14`
- 当前正式 baseline：`baseline_V10`
- 当前前端可加载参考 baseline：`baseline_V10.1`（内部 ID：`baseline_V10_1`）
- 基线目录：[baseline_V10](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/baselines/baseline_V10)
- 参考基线目录：[baseline_V10_1](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/baselines/baseline_V10_1)
- 基线报告：[report.md](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/baselines/baseline_V10/report.md)
- 研究门槛：[research_policy.json](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/baselines/baseline_V10/research_policy.json)

## 1. 当前总判断

- 事实：`baseline_V10` 仍然是 `16-26` 主开发窗口的正式锚点。
- 事实：`baseline_V10.1` 已由 `S1_INDUSTRY_ONLY` 固化为前端可加载参考基线，但它不是正式主线。
- 事实：同版 breakout 路径下：
  - `16-26`：`Total Return 409.67% / CAGR 19.51% / MaxDD -28.98% / Sharpe 0.858`
  - `07-17`：`Total Return 31.48% / CAGR 3.03% / MaxDD -39.16% / Sharpe 0.251`
- 事实：`baseline_V10.1` 对应 `S1_INDUSTRY_ONLY`，在完成行业 PIT 映射、历史申万指数桥接和 `07-17/16-26` 复验后，当前可信口径是：
  - `16-26`：`Total Return 442.56% / CAGR 20.33% / MaxDD -29.03% / Sharpe 0.889`
  - `07-17`：`Total Return 16.46% / CAGR 1.68% / MaxDD -44.74% / Sharpe 0.184`
- 事实：当前正式门槛已经固定：
  - `16-26` 是主评分窗口
  - `07-17` 是硬门槛，`CAGR < 10%` 直接淘汰核心候选
  - `07-26` 只做最终审计
- 结论：`baseline_V10` 适合作为当前市场结构下的开发基线，但不是核心跨周期候选。
- 结论：`baseline_V10.1` 只作为现代窗口参考基线保留，供前端加载和对照，不替代正式 `baseline_V10`。

## 2. baseline 演进摘要

### 2.1 第一阶段：建立可运行 breakout 基线

- `V1`：建立最小可运行趋势框架。
- `V2`：打开 `market_filter`，验证市场状态过滤存在独立贡献。
- `V3`：`breakout_window 55 -> 45`，确认更快 breakout 更适配当前股票池与执行框架。

### 2.2 第二阶段：补风险结构

- `V4`：加入 `risk_off_exit`，把系统从单纯趋势追踪升级为带风险切换的趋势系统。
- `V5 ~ V8`：围绕风险预算和仓位弹性做结构优化。
- 阶段结论：`risk_off` 是必要结构，不是可选装饰。

### 2.3 第三阶段：补强 alpha 与利润保护

- `V9`：切到 `residual_only`，完成核心选股 alpha 升级。
- `V9.1`：加入利润保护 trailing。
- `V9.3`：`residual_window 60 -> 40`。
- `V9.4`：加入 `pre_profit_breakout_failure_*`。
- `V10`：合并 `V9.3` 与 `V9.4`，形成当前正式 baseline。

## 3. 重要修复与口径统一

- 事实：`CSI800` 相关历史数据已补齐到 `2007`，PIT 成分、指数日线、价格覆盖和主数据关键问题已修复。
- 事实：`pams_ohlcv_daily.limit_up/limit_down` 的历史口径已按源规则重建并完成分批验收。
- 事实：warmup 与绩效统计口径已修复，`07-17` 与 `16-26` 现在按同一把尺子比较。
- 事实：旧的错误 `07-17` artifact 已废弃；正式对比只认 breakout 同版路径。

## 4. 当前研究框架

### 4.1 三窗口分工

- `16-26`：主开发窗口
- `07-17`：硬红线窗口
- `07-26`：全周期审计窗口

### 4.2 固定门槛

- 第一关：`16-26` 不允许做坏
- 第二关：`07-17 CAGR >= 10%`
- 第三关：只有同时通过前两关的版本，才进入 `07-26`

## 5. 已归档实验

### 5.1 Rotation Replace

- 研究原因：
  - `2009` 与 `2014-2015` 出现“组合冻结”迹象，怀疑满仓后旧仓不换新强者
  - 需要先验证问题是否发生在 `planner` 末端
- 实验改动范围：
  - 只在满仓时增加单票替换
  - `B0` 对照，`R1 / R1b` 仅改变替换分差阈值
  - 不改股票池、成本、执行、退出、风险预算、评分口径
- 事实：
  - `07-17` 上 `R1 / R1b` 与 `B0` 完全一致，没有实际替换发生
  - `2009` 与 `2014-2015` 关键阶段没有触发面
  - `16-26` 上触发后，收益下降、交易增加，整体劣于 baseline
- 结论：
  - 这条方向没有打到问题点
  - 当前瓶颈不在 `planner` 末端换仓层
- 下一步计划：
  - 归档，不再继续扩展 planner 层 rotation
  - 研究重心转回上游候选生成与强度评分

### 5.2 S0 市场环境代理来源最小对照

- 研究原因：
  - 当前 baseline 用 `HS300` 作为 benchmark 与 regime 代理，但交易池实际覆盖更宽的 `CSI800` 机会集
  - 需要验证当前不足是否来自“大盘环境代理错配”
- 实验改动范围：
  - `B0_HS300`：原始 baseline
  - `R_CSI800_BENCH`：只把大盘代理从 `000300.SH` 改成 `000906.SH`
  - `R_BREADTH_REGIME`：关闭 `benchmark_regime`，改用 `breadth_momo -> dynamic max_positions`
  - 不改个股信号、股票池、退出、成本、执行
- 事实：
  - `B0_HS300`：`CAGR 19.50% / Sharpe 0.858 / MaxDD -28.99%`
  - `R_CSI800_BENCH`：`15.21% / 0.698 / -38.25%`
  - `R_BREADTH_REGIME`：`10.29% / 0.512 / -47.27%`
  - 两个变体都明显做坏 `16-26` 主窗口
- 结论：
  - 当前 V10 的主问题不在“大盘环境代理来源”
  - `HS300` 仍是更合适的 regime 代理
- 下一步计划：
  - `S0` 归档，不继续优先推进
  - 后续重心回到个股层强度评分

### 5.3 S1 Residual Structure Split

- 研究原因：
  - 当前瓶颈更像“上游强度评分 / 同日候选排序”
  - `residual_only` 混合了“大盘相对强”和“行业相对强”两条支路，需要先拆开诊断 edge 来源
- 实验改动范围：
  - 只拆 `residual_only` 内部两条支路权重
  - 比较 `0.5/0.5`、`1.0/0.0`、`0.0/1.0`、`0.7/0.3`、`0.3/0.7`
  - 保持 `residual_window=40`，不改股票池、benchmark、regime、退出、成本、执行
- 事实：
  - `S1_INDUSTRY_ONLY` 是 `16-26` 最优变体，`CAGR 20.60% / Sharpe 0.907`
  - 所有 `S1` 变体都未通过 `07-17 CAGR >= 10%`
  - 最好的 `07-17` 结果是 `S1_B30_I70`，但 `CAGR` 只有 `5.39%`
  - `S1_INDUSTRY_ONLY` 已固化为前端可加载参考基线：
    - 显示名：`baseline_V10.1`
    - 内部 ID：`baseline_V10_1`
    - 目录：[baseline_V10_1](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/baselines/baseline_V10_1)
    - 绑定实验：`exp_20260313_063629693_1d3c`
    - 配置差异：仅将 `residual_benchmark_weight / residual_industry_weight` 从 `0.5 / 0.5` 改成 `0.0 / 1.0`
  - 后续在行业 PIT 历史映射、申万历史代码桥接修复后，`baseline_V10.1` 的可信复验口径下修为：
    - `16-26`：`Total Return 442.56% / CAGR 20.33% / MaxDD -29.03% / Sharpe 0.889`
    - `07-17`：`Total Return 16.46% / CAGR 1.68% / MaxDD -44.74% / Sharpe 0.184`
- 结论：
  - `S1_INDUSTRY_ONLY` 记为“现代窗口最优参考变体”
  - 但它只赢了 `16-26`，没有过硬门槛，所以不升主线
- 下一步计划：
  - 不再继续细调 residual 混合权重
  - 后续若沿强度评分线推进，应优先考虑更上层的排序结构

### 5.4 S2 V10_ONSET_INGRESS_MINIMAL

- 研究原因：
  - `Rotation Replace` 与 `S0` 已说明问题不优先在 planner 末端，也不优先在大盘环境代理来源
  - 当前 baseline 不存在额外确认、延迟或 entry buffer，剩余最直接的入口假设是 `45` 日 breakout 可能过慢、过窄
- 实验改动范围：
  - 只增加更早的双 breakout ingress 通道
  - `B0`：baseline
  - `S2_A_30_45`：`dual_breakout or`，`30/45`
  - `S2_B_20_45`：`dual_breakout or`，`20/45`
  - 不改股票池、benchmark、regime、pullback、planner、exit、成本、执行
- 事实：
  - `16-26` 主窗口：
    - `B0`：`CAGR 19.50% / Sharpe 0.858 / MaxDD -28.99%`
    - `S2_A_30_45`：`16.58% / 0.760 / -28.19%`
    - `S2_B_20_45`：`16.15% / 0.741 / -28.20%`
  - `07-17` 硬门槛窗口：
    - `B0`：`CAGR 3.03%`
    - `S2_A_30_45`：`3.65%`
    - `S2_B_20_45`：`1.67%`
  - 两个变体都显著增加了原始信号和候选数，但没有形成稳定的跨窗口改善
- 结论：
  - 旧窗口的问题不是简单的“入口太慢 / 太窄”
  - 更早 ingress 带来的更多是噪音，而不是稳定 edge
  - `S2` 不通过，不进入主线
- 下一步计划：
  - 不继续沿 `dual_breakout ingress` 细调
  - 后续若继续走上游主线，应回到更高质量的候选排序与强度评分结构

### 5.5 S3 更高质量同日候选排序

- 研究原因：
  - `S1` 与 `S2` 已说明，问题不只是 residual 两支路配比，也不只是更早 ingress
  - 当前 baseline 更像“候选进来后直接按总强度排”，缺少对“追高、失真、太晚”的前置过滤
  - 需要验证旧窗口失效是否来自同日候选质量不够，而不是 alpha 强度本身无效
- 实验改动范围：
  - 只新增 `QUALITY_THEN_RESIDUAL` 二段式排序
  - 第一层：按 breakout quality 做硬门槛过滤
  - 第二层：在通过质量门槛的候选内，继续按 residual 强度排序
  - `B0`：baseline
  - `S3_A_Q55`：质量门槛 `0.55`
  - `S3_B_Q65`：质量门槛 `0.65`
  - 不改股票池、benchmark、regime、planner、exit、成本、执行
- 事实：
  - `16-26` 主窗口：
    - `B0`：`CAGR 19.50% / Sharpe 0.858 / MaxDD -28.99%`
    - `S3_A_Q55`：`16.61% / 0.833 / -30.72%`
    - `S3_B_Q65`：`8.48% / 0.513 / -34.95%`
  - `07-17` 硬门槛窗口：
    - `B0`：`CAGR 3.03%`
    - `S3_A_Q55`：`1.89%`
    - `S3_B_Q65`：`4.39%`
  - `S3` 确实提高了买点质量：
    - 平均买入质量分数上升
    - 平均追高幅度、开盘缺口、日内回落都下降
  - 但质量门槛带来的结果不是稳健改善：
    - `S3_A_Q55` 明显改善了 `2019-2021`
    - 但同时显著拖累了 `2021-2022` 和 `2024-2026`
    - `S3_B_Q65` 对旧窗口部分阶段有改善，但全窗口仍远低于 `07-17 CAGR >= 10%`
- 结论：
  - `S3` 不通过
  - “更高质量买点”这条信息本身是有用的，但不能用硬门槛过滤来替代当前 residual 主排序
  - 当前旧窗口的核心问题，不是简单靠提高同日候选质量就能修复
- 下一步计划：
  - 不继续沿质量硬门槛做阈值细调
  - 如果继续沿这条线推进，只考虑“质量作为同日分层 / tie-break”，不再做硬过滤主线

### 5.6 D1 现有买点四标签纯诊断

- 研究原因：
  - `S0 ~ S3` 已说明，旧窗口问题不优先在 planner 末端、regime 来源、更早 ingress 或更严同日质量门槛
  - 需要先回答：`07-17` 与 `16-26` 的既有买点，究竟死在开盘微观结构、涨停拥挤、行业/风格领导，还是机构化代理这几层
  - 因此本轮只做纯诊断，不碰任何交易逻辑
- 实验改动范围：
  - 不改信号、不改股票池、不改执行、不改 exit、不改打分
  - 只对既有 `07-17` 与 `16-26` BUY 交易补 4 组标签：
    - `CTO / overnight pressure`
    - `near-limit / recent-limit-hit`
    - `industry leader bucket`
    - `factor leader bucket`
    - `institutionalization proxy bucket`
  - 标签口径：
    - `CTO`：信号日收盘到执行日开盘的 raw gap
    - `near-limit / recent-limit-hit`：执行日前最近 3 个交易日的涨停贴边 / 触板拥挤
    - `industry leader`：PIT 行业映射下，对应申万一级行业指数的 40 日强弱桶
    - `factor leader`：`size/liquidity/volatility` 三维风格桶的 40 日强弱桶
    - `institutionalization proxy`：`流通市值代理 + 20d amount` 的横截面分层；这是代理，不是真实机构持仓
- 事实：
  - 诊断产物：
    - [summary_by_bucket.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/v10_buy_tag_diagnostic_20260313/summary_by_bucket.csv)
    - [tagged_roundtrips.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/v10_buy_tag_diagnostic_20260313/tagged_roundtrips.csv)
    - [diagnosis_summary.json](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/v10_buy_tag_diagnostic_20260313/diagnosis_summary.json)
  - `CTO / overnight pressure`
    - `07-17`：`HEAVY_GAP_UP` 平均回报 `-2.55%`
    - `16-26`：`HEAVY_GAP_UP` 平均回报 `+3.61%`
    - `16-26` 的 `MILD_GAP_UP` 最强，平均回报 `+13.91%`；`07-17` 同桶只有 `+6.38%`
  - `near-limit / recent-limit-hit`
    - `07-17`：`RECENT_LIMIT_HIT_ONLY` 平均回报 `-1.78%`
    - `16-26`：同桶平均回报 `+12.60%`
    - 说明“最近触板后再做 breakout”在旧窗口更像拥挤噪音，在现代窗口反而能延续
  - `factor leader bucket`
    - `07-17`：`LEADER +3.70% / MID -2.38% / LAGGARD +1.27%`
    - `16-26`：`LEADER +6.09% / MID +6.93% / LAGGARD +1.70%`
    - 说明现代窗口的风格扩散更宽，旧窗口则更窄，一旦落到中间层风格桶，收益就明显转差
  - `institutionalization proxy bucket`
    - `07-17`：`LEADER +5.65% / MID -1.65% / LAGGARD +1.73%`
    - `16-26`：`LEADER +5.64% / MID +6.78% / LAGGARD +2.74%`
    - 说明旧窗口不是“机构化代理完全无效”，而是只有高机构化代理桶还能稳定赚钱，中间层会拖净值
  - 风格桶细看：
    - `07-17` 真正显著有效的是 `BIG_LIQ_LOWVOL`，平均回报 `+14.08%`
    - `16-26` 则不止这一桶有效，`BIG_LIQ_LOWVOL +11.13%`、`SMALL_LIQ_HIGHVOL +7.44%`、`BIG_LIQ_HIGHVOL +5.95%`
    - 说明现代窗口的可赚钱风格分布更宽，旧窗口更依赖窄风格
  - `industry leader bucket` 需要谨慎解释：
    - `07-17` 有较高 `UNKNOWN`
    - 主因是早期行业指数覆盖与映射缺口，不是交易标签全失效
    - 因此行业桶可以参考，但不应作为当前最强证据
- 结论：
  - 当前旧窗口的核心问题，确实不是“简单提高同日候选质量”就能修复
  - 更接近的事实是：
    - `07-17` 的可赚钱买点分布更窄，更怕高开拥挤和“最近触板后再追”
    - `07-17` 对中间层风格桶和中间层机构化代理桶更脆弱
    - `16-26` 的 edge 更宽，适合更多 mild gap / recent-limit-hit / 中间层扩散结构
  - 推断：
    - 旧窗口与现代窗口的主要断裂，更像“开盘微观结构 + 风格扩散宽度 + 参与者结构”三层变化
    - 而不是 stock-level breakout 候选质量本身
- 下一步计划：
  - 不建议回到 `S3` 那种全局质量硬门槛
  - 如果继续推进，优先方向应改为：
    - 条件化排序：按 `CTO / recent-limit-hit / institution proxy / factor leadership` 做分层或 tie-break
    - 而不是统一阈值或统一加权
  - 行业桶在继续使用前，应先补一轮早期行业指数覆盖/映射审计

### 5.7 S4 条件化分层 / tie-break 最小实验

- 研究原因：
  - `D1` 已说明，旧窗口问题不是单纯的同日候选质量，而更接近“开盘拥挤 + 风格扩散宽度 + 参与者结构”三层差异
  - 因此这轮不再做全局质量硬门槛，而是只验证：在不改交易逻辑的前提下，能否用 `t` 日已知的条件标签，对同日候选做轻量 tie-break
  - 它要回答的问题是：旧窗口的失效，是否可以靠“更高质量的条件化同日排序”修复
- 实验改动范围：
  - 只新增 `residual_refine_mode=conditional_tiebreak`
  - `B0`：baseline
  - `S4_A_TB10`：`conditional_tiebreak + weight=0.10`
  - `S4_B_TB20`：`conditional_tiebreak + weight=0.20`
  - tie-break 只使用 `t` 日已知代理：
    - `breakout_quality_score`
    - `recent_limit_hit_3d / near_limit_up`
    - `factor_leader_score`
    - `institutionalization_proxy_score`
  - 不改股票池、benchmark、regime、planner、exit、成本、执行
  - 审计约束：这轮没有把 `CTO` 直接带入实盘排序，因为 `CTO` 依赖 `t+1 open`，会引入未来信息
- 事实：
  - 代码层只改了：
    - `breakout_signal_provider.py`：新增条件化 tie-break 分数与审计元数据
    - `_semantic_config_compiler.py`：接受 `CONDITIONAL_TIEBREAK`
    - 对应单测与研究脚本：`run_v10_conditional_tiebreak_s4_research.py`
  - `16-26` 主窗口：
    - `B0`：`CAGR 19.50% / Sharpe 0.858 / MaxDD -28.99%`
    - `S4_A_TB10`：`14.96% / 0.703 / -36.27%`
    - `S4_B_TB20`：`16.45% / 0.759 / -37.44%`
  - `07-17` 硬门槛窗口：
    - `B0`：`CAGR 3.03%`
    - `S4_A_TB10`：`3.21%`
    - `S4_B_TB20`：`1.49%`
  - `S4` 确实改变了买点结构：
    - `16-26` 的平均 `breakout_quality_score` 从 `0.605` 提高到 `0.636 / 0.640`
    - `16-26` 的 `recent_limit_hit_buy_ratio` 从 `45.15%` 降到 `39.67% / 40.95%`
    - `16-26` 的 `near_limit_up_buy_ratio` 从 `36.71%` 降到 `31.82% / 33.62%`
    - `07-17` 上却没有同方向改善，`recent_limit_hit_buy_ratio` 和 `near_limit_up_buy_ratio` 反而升到 `31.47% / 25.38%` 与 `32.99% / 27.92%`
  - 分阶段看，`S4` 没有形成稳健收益结构：
    - `16-26`：
      - `2019-2021`：`B0 158.46%`，`S4_A 150.30%`，`S4_B 161.51%`
      - `2021-2022`：`B0 -8.86%`，`S4_A -16.43%`，`S4_B -16.08%`
      - `2024-2026`：`B0 92.52%`，`S4_A 59.42%`，`S4_B 66.48%`
    - `07-17`：
      - `2009`：`B0 10.73%`，`S4_A 10.95%`，`S4_B 16.46%`
      - `2010-2013`：`B0 -19.93%`，`S4_A -29.76%`，`S4_B -29.37%`
      - `2014-2015`：`B0 92.17%`，`S4_A 130.23%`，`S4_B 104.38%`
      - `2015-2017`：`B0 -31.00%`，`S4_A -30.43%`，`S4_B -39.78%`
  - 门槛结果：
    - `S4_A_TB10`、`S4_B_TB20` 都没有通过 `16-26` 主窗口
    - 两者也都没有通过 `07-17 CAGR >= 10%`
    - 因此没有版本进入 `07-26` 审计
  - 产物：
    - [summary_all.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/v10_conditional_tiebreak_s4_20260313/summary_all.csv)
    - [gate_results.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/v10_conditional_tiebreak_s4_20260313/gate_results.csv)
    - [comparison.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/v10_conditional_tiebreak_s4_20260313/comparison.csv)
- 结论：
  - `S4` 不通过
  - 事实是，这条条件化 tie-break 确实能改变买点分布，也能在局部阶段提高买点质量
  - 但推断上，它仍然没有打中旧窗口的主矛盾，反而把 `16-26` 主窗口明显做坏
  - 当前旧窗口的问题，不是简单靠“条件化同日排序”就能修复
- 下一步计划：
  - 不继续细调 `S4` 的 tie-break 权重
  - 如果继续推进，应从“状态条件化路由”或“更明确的领导因子层”入手，而不是继续做全局同日 tie-break

### 5.8 R2 状态条件化 residual 路由

- 研究原因：
  - `S1` 已经说明，`industry_only` 在 `16-26` 是现代窗口最优参考变体，但它全窗口直切会死在 `07-17`
  - 因此需要回答一个更窄的问题：不增加新因子时，是否可以只在 `strong_risk_on` 阶段把 residual 路由到更行业化的权重，而在其余阶段保留 baseline 的 `0.5 / 0.5`
  - 这轮要验证的不是“行业相对强有没有用”，而是“它是否只该在强势状态下使用”
- 实验改动范围：
  - 只新增 `residual_weight_regime_mode`
  - `B0`：baseline
  - `R2_A_STRONG_IND_ONLY`：仅 `strong_risk_on` 时使用 `0.0 / 1.0`，其余日期回退到 `0.5 / 0.5`
  - `R2_B_STRONG_B30_I70`：仅 `strong_risk_on` 时使用 `0.3 / 0.7`，其余日期回退到 `0.5 / 0.5`
  - 固定不变：
    - `residual_window=40`
    - 股票池
    - benchmark / regime 来源
    - planner
    - exit
    - 成本
    - 成交时点
  - 代码层只补了最小参数化与透传：
    - `_semantic_config_compiler.py`
    - `_experiment_runner_api.py`
    - `breakout_trend.py`
    - `registry.py`
    - `multi_alpha_signal_provider.py`
    - `breakout_signal_provider.py`
    - 研究脚本：`run_v10_state_conditional_residual_r2_research.py`
- 事实：
  - 审计上，这轮没有引入新因子、没有改执行时点；状态定义直接复用既有 `strong_risk_on`
  - 额外修复了一处实现细节：fallback 权重读取不能用 `or`，否则合法的 `0.0` 会被误判成“未配置”
  - 单测通过：
    - `test_semantic_config_compiler.py`
    - `test_experiment_runner_multi_alpha_compile.py`
    - `test_breakout_signal_provider.py`
  - `16-26` 主窗口：
    - `B0`：`CAGR 19.50% / Sharpe 0.858 / MaxDD -28.99%`
    - `R2_A_STRONG_IND_ONLY`：`20.64% / 0.902 / -29.06%`
    - `R2_B_STRONG_B30_I70`：`18.95% / 0.832 / -29.13%`
  - `07-17` 硬门槛窗口：
    - `B0`：`CAGR 3.03% / MaxDD -39.16%`
    - `R2_A_STRONG_IND_ONLY`：`2.48% / -51.96%`
    - `R2_B_STRONG_B30_I70`：`4.22% / -39.16%`
  - 分阶段看：
    - `16-26`
      - `2019-2021`：`B0 158.46%`，`R2_A 185.86%`，`R2_B 150.11%`
      - `2021-2022`：`B0 -8.86%`，`R2_A -11.96%`，`R2_B -13.79%`
      - `2024-2026`：`B0 92.52%`，`R2_A 89.87%`，`R2_B 94.43%`
    - `07-17`
      - `2009`：`B0 10.73%`，`R2_A 1.15%`，`R2_B 10.73%`
      - `2010-2013`：`B0 -19.93%`，`R2_A -28.51%`，`R2_B -19.93%`
      - `2014-2015`：`B0 92.17%`，`R2_A 130.27%`，`R2_B 92.17%`
      - `2015-2017`：`B0 -31.00%`，`R2_A -23.41%`，`R2_B -23.36%`
  - 权重实际生效情况不是空跑：
    - `16-26` 买点里，`R2_A` 平均有效权重约 `0.120 / 0.880`，`strong_risk_on` 买入占比约 `76.03%`
    - `07-17` 买点里，`R2_A` 平均有效权重约 `0.315 / 0.685`，`strong_risk_on` 买入占比约 `37.06%`
    - `07-17` 的 `R2_B` 平均有效权重约 `0.424 / 0.576`
  - 门槛结果：
    - `R2_A_STRONG_IND_ONLY` 通过了 `16-26` 主窗口，但没有通过 `07-17 CAGR >= 10%`
    - `R2_B_STRONG_B30_I70` 没有通过 `16-26` 主窗口，也没有通过 `07-17` 硬门槛
    - 因此没有版本进入 `07-26` 审计
  - 产物：
    - [summary_all.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/v10_state_conditional_residual_r2_20260314/summary_all.csv)
    - [gate_results.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/v10_state_conditional_residual_r2_20260314/gate_results.csv)
    - [comparison.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/v10_state_conditional_residual_r2_20260314/comparison.csv)
- 结论：
  - `R2` 整体不通过
  - 事实是，`R2_A` 证明了“强势状态下更行业化的 residual 路由”对现代窗口确实有帮助
  - 但推断上，这仍然没有打中旧窗口主矛盾，甚至把 `07-17` 的脆弱性进一步放大
  - 因此：
    - `R2_A_STRONG_IND_ONLY` 记为“现代窗口条件路由参考变体”，但不升主线
    - `R2_B_STRONG_B30_I70` 直接否决
- 下一步计划：
  - 不继续细调同一条 `residual` 路由配比
  - 如果继续在“不增加因子”的约束下推进，应优先考虑：
    - 现有信息驱动的生命周期分层 exit
    - 仅在特定 state 下启用的结构切换，而不是继续微调 `0.1` 权重

### 5.9 R3 状态条件化 residual window

- 研究原因：
  - `R2_A` 已经证明，现代窗口对“强势状态下更行业化的 residual 路由”有反应，但这条线没有修复旧窗口
  - 因此需要进一步判断：问题是否不在 residual 支路，而在 residual 的节奏本身
  - 这轮只验证一个更窄的问题：是否应该在 `strong_risk_on` 保持 `window=40`，在非强势阶段切回更慢的 `60/80`
- 实验改动范围：
  - 不改策略逻辑，直接复用现有 `residual_window_regime_mode`
  - `B0`：baseline
  - `R3_A_STRONG40_ELSE60`：仅 `strong_risk_on` 用 `40`，其余日期回退到 `60`
  - `R3_B_STRONG40_ELSE80`：仅 `strong_risk_on` 用 `40`，其余日期回退到 `80`
  - 固定不变：
    - residual 权重仍是 baseline 的 `0.5 / 0.5`
    - 股票池
    - benchmark / regime 来源
    - planner
    - exit
    - 成本
    - 成交时点
  - 代码层没有新增策略逻辑；只新增一份研究脚本：
    - `run_v10_state_conditional_window_r3_research.py`
- 事实：
  - 审计上，这轮没有新增任何交易因子，也没有改变信号生成时点与成交时点
  - 复用的状态定义仍是既有 `strong_risk_on`
  - 研究脚本语法校验通过：`python -m py_compile backend/scripts/run_v10_state_conditional_window_r3_research.py`
  - `16-26` 主窗口：
    - `B0`：`CAGR 19.50% / Sharpe 0.858 / MaxDD -28.99%`
    - `R3_A_STRONG40_ELSE60`：`15.47% / 0.724 / -28.98%`
    - `R3_B_STRONG40_ELSE80`：`17.11% / 0.787 / -29.02%`
  - `07-17` 硬门槛窗口：
    - `B0`：`CAGR 3.03% / MaxDD -39.16%`
    - `R3_A_STRONG40_ELSE60`：`3.24% / -46.93%`
    - `R3_B_STRONG40_ELSE80`：`0.68% / -47.79%`
  - 分阶段看：
    - `16-26`
      - `2019-2021`：`B0 158.46%`，`R3_A 81.66%`，`R3_B 94.37%`
      - `2021-2022`：`B0 -8.86%`，`R3_A -8.76%`，`R3_B -8.79%`
      - `2024-2026`：`B0 92.52%`，`R3_A 89.26%`，`R3_B 98.07%`
    - `07-17`
      - `2009`：`B0 10.73%`，`R3_A 3.51%`，`R3_B 15.48%`
      - `2010-2013`：`B0 -19.93%`，`R3_A -30.19%`，`R3_B -33.99%`
      - `2014-2015`：`B0 92.17%`，`R3_A 165.61%`，`R3_B 101.56%`
      - `2015-2017`：`B0 -31.00%`，`R3_A -37.24%`，`R3_B -36.80%`
  - window 实际生效情况不是空跑：
    - `16-26` 买点里，`R3_A` 平均有效 window `44.81`，`R3_B` 平均有效 window `50.37`
    - `07-17` 买点里，`R3_A` 平均有效 window `52.45`，`R3_B` 平均有效 window `65.00`
    - 两个变体的 `residual_window_conditional_active_ratio` 都接近 `strong_risk_on` 买入占比，说明路由实际生效
  - 门槛结果：
    - `R3_A_STRONG40_ELSE60` 与 `R3_B_STRONG40_ELSE80` 都没有通过 `16-26` 主窗口
    - 两者也都没有通过 `07-17 CAGR >= 10%`
    - 因此没有版本进入 `07-26` 审计
  - 产物：
    - [summary_all.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/v10_state_conditional_window_r3_20260314/summary_all.csv)
    - [gate_results.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/v10_state_conditional_window_r3_20260314/gate_results.csv)
    - [comparison.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/v10_state_conditional_window_r3_20260314/comparison.csv)
- 结论：
  - `R3` 不通过
  - 事实是，把 residual 在非强势阶段做慢，既没有修复旧窗口，也明显损伤了 `16-26`
  - 推断上，这说明当前问题不是“快节奏 residual 用错了状态”，而更像 residual 之外的结构问题
  - `R3_A` 和 `R3_B` 都不保留为参考变体
- 下一步计划：
  - 不继续细调 `40/60/80` 这条 residual window 路由
  - 如果继续在“不增加因子”的约束下推进，应优先考虑：
    - 现有信息驱动的生命周期分层 exit
    - 仅在特定 state 下启用的结构切换，但不要继续围绕 residual window 做参数摆动

### 5.10 L1 领导层路由最小实验

- 研究原因：
  - 前面的诊断已经表明，旧窗口的核心问题不像是“同日候选质量不够”，而更像 V10 缺少一个位于 stock residual 之上的“领导层路由”
  - 因此这轮不再做全局 tie-break，也不再调 residual 权重，而是直接验证一个更接近结构层的问题：
    - 是否应该先按“领导层 bucket”分层，再在层内按 residual 排序
  - 目标不是增加新原始因子，而是复用现有诊断标签，看这层结构本身有没有价值
- 实验改动范围：
  - 只新增一个 `ranking_mode=leadership_then_residual`
  - 路由分数只复用已有两条支路：
    - `conditional_factor_leader_score`
    - `conditional_institution_proxy_score`
  - 不新增新原始因子，不改股票池、benchmark / regime 来源、planner、exit、成本、成交时点
  - `B0`：baseline
  - `L1_A_BUCKET2`：二桶路由，先按领导层二桶分层，桶内再按 residual 排序
  - `L1_B_BUCKET3`：三桶路由，先按领导层三桶分层，桶内再按 residual 排序
  - 代码层改动范围：
    - `breakout_signal_provider.py`：新增领导层分桶路由、路由元数据
    - `_semantic_config_compiler.py`：接受 `LEADERSHIP_THEN_RESIDUAL` 与 `leadership_route_bucket_count`
    - `_experiment_runner_api.py`、`registry.py`、`breakout_trend.py`：配置透传
    - 单测与研究脚本：`run_v10_leadership_route_l1_research.py`
- 事实：
  - 审计上，这轮没有引入未来信息；领导层路由只使用 `t` 日已知的历史横截面标签，仍是 `t` 日收盘出信号、`t+1 open` 执行
  - provider 分桶实现里的 `NaN -> int` warning 已修掉，并重新完成正式跑批
  - 静态校验与最小单测通过：
    - `python -m py_compile`
    - `test_breakout_signal_provider.py`
    - `test_semantic_config_compiler.py`
    - `test_experiment_runner_multi_alpha_compile.py`
  - `16-26` 主窗口：
    - `B0`：`CAGR 19.50% / Sharpe 0.858 / MaxDD -28.99%`
    - `L1_A_BUCKET2`：`19.77% / 0.866 / -29.00%`
    - `L1_B_BUCKET3`：`18.58% / 0.812 / -36.64%`
  - `07-17` 硬门槛窗口：
    - `B0`：`CAGR 3.03% / Sharpe 0.251 / MaxDD -39.16%`
    - `L1_A_BUCKET2`：`4.33% / 0.314 / -40.15%`
    - `L1_B_BUCKET3`：`3.46% / 0.271 / -37.62%`
  - 路由实际生效，不是空跑：
    - `16-26`
      - `B0` 平均 `leadership_route_score` 约 `0.678`
      - `L1_A` 提升到 `0.738`，`top_bucket_buy_ratio` 约 `89.73%`
      - `L1_B` 提升到 `0.756`，`top_bucket_buy_ratio` 约 `87.39%`
    - `07-17`
      - `B0` 平均 `leadership_route_score` 约 `0.624`
      - `L1_A` 提升到 `0.673`，`top_bucket_buy_ratio` 约 `90.91%`
      - `L1_B` 提升到 `0.684`，`top_bucket_buy_ratio` 约 `76.19%`
  - 分阶段看，领导层路由有明确 trade-off：
    - `16-26`
      - `2019-2021`：`B0 158.46%`，`L1_A 187.19%`，`L1_B 177.27%`
      - `2021-2022`：`B0 -8.86%`，`L1_A -11.37%`，`L1_B -14.22%`
      - `2024-2026`：`B0 92.52%`，`L1_A 79.83%`，`L1_B 83.88%`
    - `07-17`
      - `2009`：`B0 10.73%`，`L1_A 9.67%`，`L1_B 19.97%`
      - `2010-2013`：`B0 -19.93%`，`L1_A -25.94%`，`L1_B -29.53%`
      - `2014-2015`：`B0 92.17%`，`L1_A 118.38%`，`L1_B 121.57%`
      - `2015-2017`：`B0 -31.00%`，`L1_A -19.22%`，`L1_B -28.03%`
  - 门槛结果：
    - `L1_A_BUCKET2` 通过了 `16-26` 主窗口，但没有通过 `07-17 CAGR >= 10%`
    - `L1_B_BUCKET3` 没有通过 `16-26` 主窗口，也没有通过 `07-17` 硬门槛
    - 因此没有版本进入 `07-26` 审计
  - 产物：
    - [summary_all.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/v10_leadership_route_l1_20260314/summary_all.csv)
    - [gate_results.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/v10_leadership_route_l1_20260314/gate_results.csv)
    - [comparison.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/v10_leadership_route_l1_20260314/comparison.csv)
- 结论：
  - `L1` 整体不通过
  - 事实是，领导层路由这条结构层方向本身有信息量，不是完全无效：
    - `L1_A` 轻微改善了 `16-26`
    - `L1_A` 也把 `07-17 CAGR` 从 `3.03%` 抬到 `4.33%`
  - 但推断上，这个“硬分桶后再 residual 排”的实现仍然过于粗糙：
    - 它能提升进攻阶段，如 `2019-2021`、`2014-2015`
    - 但会伤害过渡/弱市阶段，如 `2010-2013`、`2021-2022`
    - 因而仍然跨不过 `07-17` 硬门槛
  - 因此：
    - `L1_A_BUCKET2` 记为“现代窗口领导层参考变体”，但不升主线
    - `L1_B_BUCKET3` 直接否决
- 下一步计划：
  - 不继续在 `2 桶 / 3 桶` 上做细碎参数摆动
  - 如果继续沿这条线推进，应优先考虑：
    - 状态条件化的领导层路由，而不是全局硬分桶
    - 把领导层作为软前置层或条件路由，而不是直接全局硬覆盖 residual 排序

### 5.11 07-26 五年滚动稳定性验证

- 研究原因：
  - 前面的单窗口门槛已经说明：`16-26` 能做，`07-17` 过不了硬线
  - 但这还不足以回答一个更结构性的问题：
    - V10 在 `07-26` 的时间稳定性到底是什么形状
    - 它是“全程都一般”，还是“某一段特别强、某一段特别差”
  - 这轮审计只做稳定性画像，不改策略逻辑
- 实验改动范围：
  - 不改任何策略代码、参数、股票池、benchmark、exit、成本、执行
  - 只做滚动审计：
    - 评估窗口：`5` 年
    - 步长：`1` 年
    - 评估起点：`2007-07-23`
    - 终点上限：`2026-03-01`
  - 为避免每个 5 年窗的 warmup 被吃掉，这轮不是直接用配置起点做绩效，而是：
    - 每个评估窗前额外留 `1` 年 warmup buffer
    - 回测后只截取目标 5 年评估区间统计
  - 说明：
    - 原本尝试过单条 `07-26` 全窗口回测后再在同一条 `NAV` 上滚动，但容器内全窗口运行被 `OOM kill`
    - 因此这轮采用“每个 5 年窗单独回测 + 统一 warmup buffer”的审计实现
- 事实：
  - 共得到 `14` 个 5 年滚动窗口
  - 汇总统计：
    - `positive_cagr_ratio = 78.57%`
    - `cagr_ge_10pct_ratio = 50.00%`
    - `positive_sharpe_ratio = 78.57%`
    - `median_cagr = 9.90%`
    - `mean_cagr = 9.34%`
    - `min_cagr = -8.51%`
    - `max_cagr = 23.07%`
    - `median_max_drawdown = -26.79%`
    - `worst_max_drawdown = -42.90%`
    - `median_sharpe = 0.611`
  - 最佳 5 年窗：
    - `2014-07-23 ~ 2019-07-23`
    - `CAGR 23.07% / Sharpe 1.057 / MaxDD -27.05%`
  - 最差 5 年窗：
    - `2009-07-23 ~ 2014-07-23`
    - `CAGR -8.51% / Sharpe -0.540 / MaxDD -39.32%`
  - 时间结构非常明显：
    - 早期三窗持续为负：
      - `2007-07-23 ~ 2012-07-23`：`-3.10%`
      - `2008-07-23 ~ 2013-07-23`：`-5.24%`
      - `2009-07-23 ~ 2014-07-23`：`-8.51%`
    - 中段显著转强：
      - `2011-07-23 ~ 2016-07-23`：`10.71%`
      - `2013-07-23 ~ 2018-07-23`：`11.51%`
      - `2014-07-23 ~ 2019-07-23`：`23.07%`
      - `2015-07-23 ~ 2020-07-23`：`17.63%`
      - `2016-07-23 ~ 2021-07-23`：`19.89%`
      - `2017-07-23 ~ 2022-07-23`：`21.50%`
      - `2018-07-23 ~ 2023-07-23`：`13.58%`
    - 后段开始回落：
      - `2019-07-23 ~ 2024-07-23`：`9.10%`
      - `2020-07-23 ~ 2025-07-23`：`5.83%`
  - 这轮结果不是单纯交易次数太少导致的假象：
    - 各窗交易数大多在 `120 ~ 338` 之间
    - 最弱窗与最强窗都有足够交易样本
  - 产物：
    - [rolling_5y.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/v10_rolling_stability_0726_5y_20260314/rolling_5y.csv)
    - [summary.json](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/v10_rolling_stability_0726_5y_20260314/summary.json)
    - [run_result.json](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/v10_rolling_stability_0726_5y_20260314/run_result.json)
- 结论：
  - 这轮稳定性验证说明，V10 不是“全程都不稳”，而是有非常明确的时间依赖
  - 事实是：
    - 它在 `2007-2014` 重叠窗里明显失效
    - 在 `2011-2023` 重叠窗里表现较强
    - 到最近两窗又出现边际回落
  - 推断上，这进一步支持前面的整体判断：
    - V10 更像一个“现代 A 股中段有效”的结构
    - 它不是全周期稳定策略
    - 即使不看 `07-17` 硬门槛，单看 `07-26` 滚动稳定性，也能看到明显的年代分层
  - 因此，V10 仍然只能作为现代窗口开发锚点，不能因为中段很强就误判为跨周期主线
- 下一步计划：
  - 不需要继续围绕“V10 本体是否跨周期稳定”重复审计，这个结论已经足够明确
  - 如果继续推进，应把重点放在：
    - 能否缩小 `2007-2014` 这段结构性失效
    - 能否避免 `2019-2025` 之后的边际走弱

### 5.12 S7 行业内二次筛选 soft rank

- 研究原因：
  - 修复后的 `V10.1` 诊断显示，`16-26` 的 losers 很多不是“不强”，而是“行业内相对强仍然很高，但更后段、更热、更挤、持续性更差”的票
  - 因此这轮不改行业主支路定义，只验证一个更窄的问题：
    - 能否仅对高 `industry_relative_score` 候选，加一层“不过热 / 不拥挤 / persistence 足够 / breadth 未过热”的行业内二次 soft rank
  - 它要修复的是现代窗口里的“行业内二次筛选不够”，而不是跨行业排序本身
- 实验改动范围：
  - 只新增 `residual_refine_mode=industry_second_stage`
  - `B0`：当前修复后的 `baseline_V10.1`
  - `S7_A_SOFT15`：`industry_second_stage + weight=0.15`
  - `S7_B_SOFT25`：`industry_second_stage + weight=0.25`
  - 二次筛选只在高 `industry_relative_score` 候选上启用，使用的都是 `t` 日可得历史信息：
    - `breakout_margin`
    - `ret10 / distance_to_ma20`
    - `vol_expansion + recent_limit`
    - `industry_breadth_change_10d`
    - `industry_rank_persistence_10d`
  - 不改行业主支路、不改股票池、benchmark / regime 来源、planner、exit、成本、执行
- 事实：
  - 审计上，这轮没有新增未来函数，也没有改成交时点；仍是 `t` 日收盘出信号、`t+1 open` 执行
  - 相关单测通过：`113` 个
  - `16-26` 主窗口：
    - `B0`：`CAGR 20.33% / Sharpe 0.889 / MaxDD -29.03% / Trades 467`
    - `S7_A_SOFT15`：`14.35% / 0.710 / -27.40% / 446`
    - `S7_B_SOFT25`：`9.82% / 0.556 / -30.66% / 456`
  - `07-17` 硬门槛窗口：
    - `B0`：`CAGR 1.68% / Sharpe 0.184 / MaxDD -44.74% / Trades 400`
    - `S7_A_SOFT15`：`5.44% / 0.370 / -38.31% / 486`
    - `S7_B_SOFT25`：`3.39% / 0.270 / -39.36% / 479`
  - 这轮不是空跑，二次筛选实际介入比例较高：
    - `16-26 active_ratio`：`88.99% / 89.22%`
    - `07-17 active_ratio`：`76.13% / 70.42%`
  - 分阶段看，trade-off 很明确：
    - `16-26`
      - `2019-2021`：`B0 168.16%`，`S7_A 90.23%`，`S7_B 98.44%`
      - `2021-2022`：`B0 -11.55%`，`S7_A -7.76%`，`S7_B -9.34%`
      - `2024-2026`：`B0 94.00%`，`S7_A 56.20%`，`S7_B 12.33%`
    - `07-17`
      - `2009`：`B0 8.90%`，`S7_A 29.34%`，`S7_B 25.78%`
      - `2010-2013`：`B0 -26.96%`，`S7_A -26.03%`，`S7_B -27.07%`
      - `2014-2015`：`B0 86.28%`，`S7_A 99.08%`，`S7_B 74.72%`
      - `2015-2017`：`B0 -30.22%`，`S7_A -23.94%`，`S7_B -23.61%`
  - 产物：
    - [summary_all.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/v10_industry_second_stage_s7_20260314/summary_all.csv)
    - [gate_results.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/v10_industry_second_stage_s7_20260314/gate_results.csv)
    - [comparison.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/v10_industry_second_stage_s7_20260314/comparison.csv)
- 结论：
  - `S7` 不通过
  - 事实是，这层行业内二次筛选信息不是空的；它确实改善了旧窗口一部分阶段，也改善了两窗的部分回撤
  - 但推断上，这版全局 soft rank 过于保守，系统性压制了 `V10.1` 在 `2019-2021` 和 `2024-2026` 的主升段热 leader
  - 因此：
    - `S7_A_SOFT15`：否决
    - `S7_B_SOFT25`：否决
- 下一步计划：
  - 不继续加大 `S7` 权重
  - 如果后续还沿这条线推进，只考虑更窄的实现：
    - 只在非强主升状态启用
    - 或只做高 `industry_relative` 候选之间的 tie-break，不直接并入主排序

## 6. 当前角色定位

- `baseline_V10` 是当前 `16-26` 开发锚点。
- `baseline_V10.1` 是当前前端可加载的现代窗口参考基线。
- `baseline_V10` 不是当前核心跨周期候选。
- 归档判断：
  - `Rotation Replace`：否决
  - `S0`：否决
  - `S1`：保留为现代窗口参考变体，但不升主线
  - `S2`：否决
  - `S3`：否决
  - `S4`：否决
  - `R2_A`：保留为现代窗口条件路由参考变体，但不升主线
  - `R2_B`：否决
  - `R3`：否决
  - `L1_A`：保留为现代窗口领导层参考变体，但不升主线
  - `L1_B`：否决
  - `S7`：否决

## 7. 后续顺序

1. 先在 `16-26` 找当前市场仍有 edge 的结构。
2. 任何新结构先过 `16-26` 主窗口，不允许把主窗口做坏。
3. 再检查 `07-17` 是否至少达到 `CAGR >= 10%`。
4. 只有通过前两关的版本，才进入 `07-26` 全周期审计。
