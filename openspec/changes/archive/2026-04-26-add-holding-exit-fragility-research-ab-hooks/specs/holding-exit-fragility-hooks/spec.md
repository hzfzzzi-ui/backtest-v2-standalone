## ADDED Requirements

### Requirement: research-only hook 只作用于已持仓股票
系统 SHALL 为 stock-only research runtime 提供 holding/exit fragility hook，并且该 hook 只能对当前已持仓股票生效，不得对当天新候选生效。

#### Scenario: 候选层不允许消费 lifecycle fragility
- **WHEN** research 配置尝试把 lifecycle fragility 因子接入 candidate veto、candidate tiebreak 或主排序
- **THEN** 系统 MUST 拒绝该接法或将其标记为无效研究配置

#### Scenario: 持仓层允许消费 lifecycle fragility
- **WHEN** research runtime 在某日存在已持仓股票且 fragility factor 对应日可用
- **THEN** 系统 SHALL 仅对这些已持仓股票构建 holding/exit fragility hook 输入
