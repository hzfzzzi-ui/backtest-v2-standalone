## MODIFIED Requirements

### Requirement: 账户层状态切换合同
账户层状态切换合同 MUST 支持对过渡态应用统一的最短停留策略，而不是直接按 raw state 切换。

#### Scenario: 过渡态抗抖优先于即时反向切换
- **GIVEN** 账户层 transition policy 已启用
- **AND** 当前有效状态属于 `TRANS_UP` 或 `TRANS_DOWN`
- **AND** 当前停留天数小于最短停留期
- **WHEN** raw state 解析结果与当前有效状态不同
- **THEN** transition policy MUST 维持当前有效状态
- **AND** 后续预算与 transition runtime MUST 消费维持后的有效状态
