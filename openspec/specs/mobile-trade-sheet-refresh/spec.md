# mobile-trade-sheet-refresh Specification

## Purpose
浠?2026-03-22 褰掓。鍙樻洿鎭㈠鐨勪富瑙勬牸銆?
## Requirements

### Requirement: 手机端必须展示真实持仓同步状态和 reconcile 动作单
手机端 MUST 同时展示 `holding_sync`、`positions` 和 `reconcile` 三类信息。`positions` SHALL 来自最新成功的模拟盘持仓快照；`reconcile` SHALL 来自绑定该快照的最新有效 reconcile run。手机端 SHALL NOT 继续把实验成交推导持仓当成“当前持仓”。

#### Scenario: 持仓已同步且存在有效 reconcile run
- **WHEN** 账户已有最新持仓快照，且系统已基于该快照生成有效 reconcile run
- **THEN** 手机端 SHALL 展示当前持仓、最新同步时间和待确认买卖动作
- **THEN** 每张动作卡 SHALL 显示其绑定的 `snapshot_id` / `reconcile_id` 或等价版本标识

#### Scenario: 持仓未同步或 reconcile 不可用
- **WHEN** 持仓尚未同步，或最新 reconcile run 为 `unavailable` / `stale`
- **THEN** 手机端 MUST 显式展示阻断原因
- **THEN** 手机端 SHALL NOT 把旧动作单渲染成当前仍可确认的动作

### Requirement: 手机端动作卡必须展示股票、价位、股数和确认状态
手机端的买卖动作卡 MUST 展示 `symbol`、`name`、`action_type`、`reference_price`、`reference_price_basis`、`suggested_qty`、`current_qty`、`target_weight` 和当前 `user_decision`。当用户手工改单后，手机端 SHALL 同时保留系统原始建议值和人工调整值。

#### Scenario: 用户查看一张买入动作卡
- **WHEN** 手机端展示某条 `buy` 动作
- **THEN** 动作卡 SHALL 至少显示股票、参考价、建议股数、当前持仓和目标权重
- **THEN** 若用户已确认或改单，动作卡 SHALL 同时显示系统值和用户值

#### Scenario: 用户查看一张卖出动作卡
- **WHEN** 手机端展示某条 `sell` 动作
- **THEN** 动作卡 SHALL 至少显示当前持股数量、建议卖出数量和参考价
- **THEN** 若该动作被阻断或已失效，动作卡 SHALL 显式显示原因

### Requirement: 手机端确认后不得直接刷新当前持仓
用户在手机端确认或驳回动作后，系统 MUST 只更新 `approval ticket` / `user_decision` 状态，而 SHALL NOT 直接修改当前持仓。当前持仓只有在新的持仓快照同步成功或执行回写完成后才可刷新。

#### Scenario: 用户确认一条动作单
- **WHEN** 用户在手机端完成二次确认并生成 `approval ticket`
- **THEN** 手机端 SHALL 把该动作标记为 `approved_pending`
- **THEN** `positions` SHALL 保持为最近一次成功持仓快照的内容，不得直接变为“预期持仓”

#### Scenario: 用户执行完成后再次同步持仓
- **WHEN** 用户在模拟盘手工执行后重新同步持仓，且最新快照反映了新的真实仓位
- **THEN** 手机端当前持仓 SHALL 更新为该快照内容
- **THEN** 旧动作单 SHALL 被标记为已失效、已完成或需要重算，而不是继续沿用旧版本
