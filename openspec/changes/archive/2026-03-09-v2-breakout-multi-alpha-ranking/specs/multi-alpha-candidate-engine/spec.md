## ADDED Requirements

### Requirement: Breakout runtime SHALL 支持并行 multi-alpha 候选
当策略为 `breakout_trend` 且显式启用 multi-alpha 扩展时，运行时 SHALL 在保留原 breakout 候选的同时，额外生成 pullback 候选，并把两类候选统一交给现有组合层做选前 N 名。

#### Scenario: baseline 默认不变
- **WHEN** `pullback.enabled = false` 且 `alpha_ranking.mode = "none"`
- **THEN** 运行时 SHALL 只生成 breakout 候选
- **THEN** 候选数量、排序行为和 `t+1` 执行语义 SHALL 与原 breakout baseline 一致

#### Scenario: 显式启用 pullback 候选
- **WHEN** `pullback.enabled = true`
- **THEN** 运行时 SHALL 生成 breakout 与 pullback 的并集候选
- **THEN** 每个候选 SHALL 标记 `alpha_source`

### Requirement: Pullback 候选 SHALL 只使用 t 日及以前数据
pullback 候选的所有 rolling、局部高点、均线和量价条件 SHALL 只使用交易日 `t` 收盘及以前可见数据；若候选在 `t` 日生成，则订单 MUST 在 `t+1` 执行。

#### Scenario: PB1 回踩均线再启动
- **WHEN** `pullback.variant = "pb1"`
- **THEN** 候选 SHALL 仅基于 `close > MA60`、`MA20 > MA60`、最近固定 lookback 内回踩 MA20、以及 `t` 日收盘突破最近短窗口高点生成
- **THEN** 不得读取 `t+1` 或未来 bar

#### Scenario: PB2 与 PB3 变体保持同样对齐
- **WHEN** `pullback.variant` 为 `pb2` 或 `pb3`
- **THEN** 变体条件 SHALL 只使用 `t` 日及以前的价格/成交量/ATR 派生字段
- **THEN** 任一变体都不得在 `t` 日信号日直接成交

### Requirement: 统一排序 SHALL 先保留候选，再决定优先级
统一排序层 SHALL 对 breakout 与 pullback 候选做排序，而不是先用残差/行业/量价质量分数硬过滤掉大部分候选。

#### Scenario: 候选少于 buy slots
- **WHEN** 当日候选数不超过可买槽位
- **THEN** 排序层 SHALL 不得额外拦截候选
- **THEN** 入选顺序仍须可追溯输出分数字段

#### Scenario: 候选多于 buy slots
- **WHEN** 当日候选数超过可买槽位
- **THEN** 排序层 SHALL 使用统一评分决定优先级
- **THEN** 最终入选与落选均 SHALL 保留分数字段和 `reject_reason`

### Requirement: 残差相对强弱排序 SHALL 可解释
当 `alpha_ranking.mode` 包含 residual ranking 时，系统 SHALL 为同一交易日可见 universe 中的候选计算 `stock_ret_window`、`benchmark_ret_window`、`sector_ret_window` 和 `residual_strength_score`，并以该分数参与最终排序。

#### Scenario: residual 分数字段完整
- **WHEN** `alpha_ranking.mode = "residual"`
- **THEN** 每个候选 SHALL 记录 `rs_vs_bench`、`rs_vs_sector`、`residual_strength_score`
- **THEN** 最终排序 SHALL 可回溯到这些字段

#### Scenario: 横截面只基于当日可见样本
- **WHEN** 系统对 residual 分数做横截面排序或标准化
- **THEN** 样本集合 SHALL 仅包含当日可交易且当日候选中的股票
- **THEN** 不得引用未来日期或退市后样本

### Requirement: 行业与量价质量排序 SHALL 默认关闭且可组合
当 `alpha_ranking.mode = "multi_score"` 时，系统 SHALL 在 residual 分数基础上叠加 `sector_strength_score` 与 `volume_price_quality_score`，并按显式权重组合成 `final_score`。

#### Scenario: 综合评分默认关闭
- **WHEN** `alpha_ranking.mode` 不为 `multi_score`
- **THEN** 行业分数与量价质量分数 SHALL 不参与最终排序

#### Scenario: 综合评分显式启用
- **WHEN** `alpha_ranking.mode = "multi_score"`
- **THEN** `final_score` SHALL 由 `residual_strength_score`、`sector_strength_score`、`volume_price_quality_score` 与显式权重组合得到
- **THEN** 权重配置 SHALL 可写入运行时配置与产物快照
