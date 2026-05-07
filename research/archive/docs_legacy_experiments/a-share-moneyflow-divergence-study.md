# a-share-moneyflow-divergence-study Specification

## Purpose
定义 A 股主力分歧率月频研究的正式口径、覆盖率门控、执行时点合同与可审计产物要求，确保该研究能力可复现、可解释、可回滚。
## Requirements

### Requirement: 研究运行必须支持可审计的组合权重模式

系统 MUST 允许该月频研究在不改变选股排序口径的前提下，使用显式声明的组合权重模式构建目标持仓。默认模式为等权；可选模式为按 rank 线性递减权重。

线性递减权重模式定义为：

- 对前 `N` 只入选股票，原始权重分数为 `N + 1 - rank`
- 归一化后目标权重为 `raw_weight / sum(raw_weight)`
- `rank = 1` 的股票必须获得最高权重
- 权重必须严格随 rank 非增

#### Scenario: 等权模式保持现有行为

- **WHEN** 研究运行未显式指定权重模式，或指定为 `equal_weight`
- **THEN** 系统必须按当前等权逻辑构建目标组合，不改变已存在的 TopN 等权研究结果

#### Scenario: 递减权重模式按 rank 分配更高权重给前排股票

- **WHEN** 研究运行指定 `weight_mode = rank_decay_linear`
- **THEN** 系统必须按 `N + 1 - rank` 的线性递减分数为入选股票分配目标权重，并将归一化权重用于调仓目标仓位计算

#### Scenario: 权重模式不改变选股集合

- **WHEN** 两次研究运行具有相同的候选池、排序口径、TopN 和执行时点，只是 `weight_mode` 不同
- **THEN** 系统必须保证最终入选股票集合完全一致，仅目标持仓权重不同

### Requirement: 主力分歧率月频研究口径必须固定

系统 MUST 提供一个独立的 A 股月频研究能力，用于研究“主力分歧率最小前十”策略。该能力 MUST 把单日因子定义为 `abs(net_mf_amount) / avg20(circ_mv)`，并把月度因子定义为当月全部有效交易日单日因子的算术均值。月末观察日 SHALL 对月度因子做升序排序，取最小 10 只股票作为下一调仓期目标组合。

#### Scenario: 按确认口径生成月度因子
- **WHEN** 某股票在某月拥有满足有效性要求的单日 `abs(net_mf_amount) / avg20(circ_mv)` 序列
- **THEN** 系统必须用这些有效单日值的算术均值生成该股票该月的月度因子值

#### Scenario: 月末按最小值排序选股
- **WHEN** 某月月末观察日的候选池已经生成全部有效月度因子
- **THEN** 系统必须按月度因子升序排序并选出最小的 10 只股票作为下一次调仓目标组合

### Requirement: 缺失值不得进入最小值排序

系统 MUST 把 `net_mf_amount` 缺失、`circ_mv` 缺失、或无法形成完整过去 20 个交易日 `avg20(circ_mv)` 的股票日样本判定为无效。系统 SHALL NOT 把这些缺失或无效值补为 `0`、空字符串或其他可参与排序的默认值。

某股票某月只有在同时满足以下条件时，才允许生成月度因子：

- 月末观察日该股票属于可交易候选池。
- 月末观察日本身存在有效单日因子。
- 当月有效单日因子数量不低于 `max(15, ceil(月内交易日数 * 0.8))`。

#### Scenario: 单日缺失不会被补零
- **WHEN** 某股票某日 `net_mf_amount` 为空或 `avg20(circ_mv)` 无法计算
- **THEN** 系统必须把该股票该日样本标记为无效，且不得生成可参与排序的单日因子值

#### Scenario: 月内有效日不足时不得参与排序
- **WHEN** 某股票在某月的有效单日因子数量低于 `max(15, ceil(月内交易日数 * 0.8))`
- **THEN** 系统必须把该股票该月标记为月度因子无效，并从当月排序候选池中排除

### Requirement: 月度候选池必须同时满足异常过滤与交易过滤

系统 MUST 在每个月月末观察日构建候选池，并至少排除以下样本：

- ST 或 `*ST` 股票。
- 观察日停牌股票。
- 观察日无正常交易主表记录的股票。
- 现有系统已定义为异常、不可交易或不应进入 A 股研究池的股票。

在次月首个交易日开盘执行时，系统 MUST 再次应用执行日可交易检查，防止观察日可交易但执行日不可成交的样本被下单。

#### Scenario: 观察日异常股票被排除
- **WHEN** 某股票在月末观察日属于 ST、停牌或异常不可交易状态
- **THEN** 系统必须在当月排序前将其从候选池中排除

#### Scenario: 执行日不可交易不会被强行买入
- **WHEN** 某股票在月末观察日通过排序但在次月首个交易日开盘不可成交
- **THEN** 系统必须阻止该股票买入，并在产物中记录对应的执行过滤原因

### Requirement: 十年研究必须执行日期级覆盖率门控

系统 MUST 对每个调仓月份的月末观察日执行 `moneyflow` 可用性门控。默认优先使用 `pit_stock_moneyflow_v2_whitelist_daily`；若该白名单在运行时不可用，则系统 MUST 使用等价的覆盖率审计输入重建同口径判断。

只有当月末观察日同时满足以下条件时，该月份才允许进入调仓排序：

- `moneyflow` 行覆盖率大于等于 `0.95`
- `net_mf_amount` 覆盖率大于等于 `0.90`

若不满足，系统 MUST 把该月份标记为 `skipped_low_coverage`，跳过该月份调仓排序，并把原因写入月份级 ledger。

#### Scenario: 低覆盖月份被显式跳过
- **WHEN** 某月月末观察日 `moneyflow` 行覆盖率低于 `0.95` 或 `net_mf_amount` 覆盖率低于 `0.90`
- **THEN** 系统必须跳过该月调仓排序，并在月份级诊断中记录 `skipped_low_coverage`

#### Scenario: 白名单不可用时不能静默放行
- **WHEN** 运行时无法读取 `pit_stock_moneyflow_v2_whitelist_daily` 且也没有等价覆盖率审计输入
- **THEN** 系统必须拒绝启动该研究运行，而不是在没有日期门控的情况下继续执行

### Requirement: 执行时点必须遵守 next_open 合同

系统 MUST 把该研究的观察时点和成交时点固定为“月末最后一个交易日收盘后观察，次月首个交易日开盘成交”。系统 SHALL NOT 把月末观察日收盘价假设为同日可成交价格。

月度持仓 MUST 在下一次调仓时按新目标组合执行再平衡，卖出不再入选的股票，保留仍在目标组合中的股票。

#### Scenario: 月末观察不会同日成交
- **WHEN** 系统在某月最后一个交易日生成当月排序结果
- **THEN** 系统必须把成交时点放在次月首个交易日开盘，而不是使用当日收盘成交

#### Scenario: 下一调仓时按目标组合再平衡
- **WHEN** 新月份的目标前十组合与当前持仓存在差异
- **THEN** 系统必须在调仓日按目标组合执行卖出与买入，并保留仍在目标组合中的股票

### Requirement: 2016-2026 运行必须输出月份级可用性诊断

系统 MUST 允许以 `2016-2026` 作为该研究的主开发窗口启动研究运行，但 MUST 输出完整的月份级可用性诊断，至少包括：

- `monthly_coverage_ledger.csv`
- `monthly_factor_panel.csv`
- `monthly_selection.csv`
- `monthly_universe_stats.csv`

运行摘要还 MUST 显式输出：

- `planned_rebalance_months`
- `tradable_months`
- `skipped_months`
- `partial_coverage`

#### Scenario: 十年研究输出月份分类账
- **WHEN** 用户启动 `2016-2026` 窗口的主力分歧率研究
- **THEN** 系统必须输出每个月是否可交易、覆盖率如何、是否跳过以及跳过原因的月份级分类账

#### Scenario: 研究摘要显式标记部分覆盖
- **WHEN** 十年研究中存在任意跳过月份
- **THEN** 系统必须把运行摘要中的 `partial_coverage` 标记为真，并给出计划月份与实际可交易月份计数

### Requirement: 数据不足的十年运行不得伪装成正式结论

系统 MUST 允许 `2016-2026` 研究完成并产出结果，但若实际可交易月份占计划调仓月份比例低于 `0.85`，系统 MUST 将该运行标记为 `data_unreliable`。被标记为 `data_unreliable` 的运行 SHALL NOT 默认追加到 baseline 报告，也不得在无额外说明的情况下视为正式研究结论。

#### Scenario: 可交易月份过少时标记不可靠
- **WHEN** 十年研究的 `tradable_months / planned_rebalance_months` 低于 `0.85`
- **THEN** 系统必须将该运行标记为 `data_unreliable`

#### Scenario: 不可靠运行不会默认追加到 baseline
- **WHEN** 某次十年研究运行被标记为 `data_unreliable`
- **THEN** 系统不得默认将该运行追加到 baseline 报告产物

### Requirement: 现有运行时不支持月频能力时必须阻塞启动

系统 MUST 在启动研究前校验以下能力是否已接线：

- `moneyflow` side table 的运行时读取能力
- 月频横截面因子面板生成能力
- 月度调仓执行能力

若任一能力缺失，系统 MUST 返回明确的阻塞原因，而不是退回到现有日频 breakout 或 multifactor 运行逻辑。

#### Scenario: 月频研究能力未实现时明确报阻塞
- **WHEN** 用户请求启动该研究，但运行时尚未实现月频横截面执行链路
- **THEN** 系统必须返回明确的 blocking reason，说明缺少的能力模块
