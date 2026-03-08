## ADDED Requirements

### Requirement: Breakout 主路径支持并行 pullback 候选
系统 SHALL 在 `breakout_trend` 主路径中支持默认关闭的 pullback 候选，与 breakout 候选在同一交易日并行产出，并继续遵守“使用 `t` 日收盘生成信号，`t+1` 执行”的日频契约。

#### Scenario: Pullback Alpha 默认关闭
- **WHEN** 运行配置未显式启用 pullback alpha
- **THEN** provider 仅产出原有 breakout 候选
- **THEN** baseline 的交易、排序和执行语义保持不变

#### Scenario: Pullback Alpha 与 Breakout 并行产出
- **WHEN** 运行配置显式启用 pullback alpha
- **THEN** provider SHALL 在同一日的 tradable universe 上同时计算 breakout 与 pullback 候选
- **THEN** 每个候选信号 MUST 标记 `alpha_source`

### Requirement: Pullback 候选必须限制为趋势内再启动
系统 SHALL 仅在中期趋势仍然向上的前提下产出 pullback 候选，不得把反转抄底信号混入 breakout 主策略。

#### Scenario: 趋势内回踩再启动
- **WHEN** 股票满足 `close > MA60` 且 `MA20 > MA60`
- **THEN** provider 才允许继续评估 pullback 变体
- **THEN** 任一 pullback 变体的最终触发 MUST 依赖当日收盘重新走强，而不是只依赖盘中低点

#### Scenario: 趋势破坏时不产出 Pullback
- **WHEN** 股票不满足趋势内约束
- **THEN** pullback 候选 MUST 为 False

### Requirement: 统一排序层必须支持 residual / sector / volume_price / final 分数
系统 SHALL 为 breakout 与 pullback 候选计算统一的排序分数字段，并允许组合层按这些分数进行排序，而不是先把大部分候选做成硬过滤。

#### Scenario: Residual Ranking 仅改变排序
- **WHEN** `enable_residual_rank=true`
- **THEN** 组合层 SHALL 保留 breakout 与 pullback 候选，只按 `residual_strength_score` 重新排序
- **THEN** 不得额外删除候选，除非仍触发既有资金、手数或持仓约束

#### Scenario: 综合排序按 final_score 生效
- **WHEN** `enable_sector_quality_rank=true`
- **THEN** 组合层 SHALL 使用 `final_score` 对候选排序
- **THEN** `final_score` MUST 由 `residual_strength_score`、`sector_strength_score`、`volume_price_quality_score` 的固定权重线性组合生成

### Requirement: 所有排序字段必须基于同日可见样本计算
系统 SHALL 仅基于同一交易日可见且可交易的候选集合进行横截面分数比较，不得把未来样本、未来行业归属或停牌不可交易样本带入同日排名。

#### Scenario: 同日候选排序
- **WHEN** 组合层在交易日 `t` 对候选排序
- **THEN** 排序所用的 cross-sectional universe MUST 仅包含交易日 `t` 的候选且满足当日 `tradable` 约束的标的

#### Scenario: 分数计算不读取未来数据
- **WHEN** 计算 `stock_ret_60`、`benchmark_ret_60`、`sector_ret_60`、`ATR20` 或成交量均值
- **THEN** rolling 窗口 MUST 仅使用截至 `t` 日的数据
- **THEN** 不得使用 `shift(-1)`、未来收益或未来行业排名
