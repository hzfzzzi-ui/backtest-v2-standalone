## ADDED Requirements

### Requirement: 系统必须以最新持仓快照为输入重算正式策略
系统 MUST 提供持仓感知的 reconcile run。该 run SHALL 使用正式策略配置、最新可用市场数据和最新成功的模拟盘持仓快照作为输入，而 SHALL NOT 继续以实验 `portfolio_trades.csv` 重建的持仓作为运行输入。reconcile run 结果 MUST 记录 `account_id`、`snapshot_id`、`reconcile_id`、`strategy_source`、`config_hash` 和 `as_of_date`。

#### Scenario: 基于最新持仓快照成功生成 reconcile run
- **WHEN** 某账户已有最新成功持仓快照，且系统具备对应 `as_of_date` 的市场数据
- **THEN** 系统 SHALL 生成新的 `reconcile_id`
- **THEN** reconcile run SHALL 记录其绑定的 `snapshot_id`、`strategy_source` 和 `config_hash`

#### Scenario: 缺少持仓快照或市场数据时不生成伪动作单
- **WHEN** 最新持仓快照缺失，或市场数据不满足本次日度规划要求
- **THEN** 系统 MUST 返回 `unavailable`、`missing_holdings_snapshot`、`stale_market_data` 或等价显式状态
- **THEN** 系统 SHALL NOT 伪造买卖动作单

### Requirement: reconcile run 必须输出持仓感知的 action sheet
系统 MUST 为每次 reconcile run 生成 action sheet。action sheet 中的每一条动作 MUST 至少包含 `symbol`、`action_type`、`current_qty`、`target_weight`、`suggested_qty`、`delta_qty`、`reference_price`、`reference_price_basis` 和 `reason_tags`。A 股股数建议 MUST 按 lot size 和现金约束处理。

#### Scenario: 当前未持有但策略建议建仓
- **WHEN** 最新持仓快照中某 symbol 未持有，而本次策略重算将其纳入目标组合
- **THEN** action sheet SHALL 生成 `buy` 动作
- **THEN** 该动作 SHALL 返回 `reference_price`、`suggested_qty`、`target_weight` 和 `delta_qty`

#### Scenario: 当前已持有但策略建议退出或减仓
- **WHEN** 最新持仓快照中某 symbol 已持有，而本次策略重算要求卖出或部分减仓
- **THEN** action sheet SHALL 生成 `sell` 动作
- **THEN** 该动作 SHALL 返回 `current_qty`、`suggested_qty`、`delta_qty` 和卖出原因

#### Scenario: 当前已持有且仍在目标组合中
- **WHEN** 最新持仓快照中的某 symbol 在本次目标组合中仍应保留
- **THEN** action sheet SHALL 生成 `hold` 或等价保留动作
- **THEN** 该动作 SHALL 仍返回 `current_qty`、`target_weight` 和偏差说明，供手机端展示

### Requirement: reconcile run 必须显式暴露 freshness 和失效条件
系统 MUST 为每次 reconcile run 返回 freshness、阻断和失效条件。该结果 SHALL 至少绑定 `snapshot_id`、`as_of_date`、`reference_price_basis` 和 `risk_flags`。当更新了更晚的持仓快照或更晚的市场数据后，旧 reconcile run MUST 被标记为 `stale`、`drifted` 或等价显式状态。

#### Scenario: 新持仓快照到来使旧 plan 失效
- **WHEN** 某个 reconcile run 生成后，系统又收到同账户更新的持仓快照
- **THEN** 旧 reconcile run SHALL 被标记为 `stale` 或 `drifted`
- **THEN** 后续确认流程 SHALL 要求用户先刷新到新的 plan

#### Scenario: 参考价只是规划基准而不是成交事实
- **WHEN** 手机端读取 action sheet 中的 `reference_price`
- **THEN** 结果 MUST 同时返回 `reference_price_basis`
- **THEN** 客户端 SHALL 能区分“规划参考价”和“实际成交价/回写价”
