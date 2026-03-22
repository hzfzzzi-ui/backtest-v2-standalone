## MODIFIED Requirements

### Requirement: MA200 状态机作为 legacy compatibility engine 保留
系统 SHALL 将现有 `ma200-market-state` 明确定义为 `ma200_legacy` compatibility engine。

该 engine：

- 继续保持当前行为
- 继续可被正式主线调用
- 不得被本 change 直接删除或无提示替换

#### Scenario: 选择 ma200_legacy
- **WHEN** `regime_engine.engine = ma200_legacy`
- **THEN** 系统 SHALL 保持当前 `close vs MA200 + slope + legacy router` 行为不变

#### Scenario: weekly five-state 不覆盖 legacy
- **WHEN** 本 change 落地
- **THEN** `ma200_legacy` SHALL 仍然可以被配置显式选中，用于 A/B 对照与回退
