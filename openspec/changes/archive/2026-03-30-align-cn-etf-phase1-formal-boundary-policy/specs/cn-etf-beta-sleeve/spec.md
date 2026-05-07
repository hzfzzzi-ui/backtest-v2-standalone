## ADDED Requirements

### Requirement: formal ETF Phase 1 必须以 Governor 预算与三桶配置语义决定本地 boundary
当 `cn_etf_beta` 以 formal `phase1_allocation_engine` 运行时，系统 MUST 先消费 Governor 下发的 sleeve budget、execution flags 与 Phase 1 三桶配置语义，再决定本地 deployability。系统 SHALL NOT 仅依据硬编码状态槽位表，将 `TRANS_DOWN` 或 `RISK_OFF` 静默翻译为 `NO_TRADE`。

#### Scenario: RISK_OFF 且 Governor 仍给出正预算
- **WHEN** formal ETF Phase 1 处于 `RISK_OFF`，且 Governor 仍下发正的 `requested_budget`，并且不存在显式禁止新风险或强制去风险的执行 flags
- **THEN** 系统 MUST 允许 Phase 1 生成缩减后的 `targets`
- **THEN** 这些 `targets` MUST 体现权益低配、limited defense candidate 和现金缓冲的三桶语义，而不是直接归零为 `NO_TRADE`

#### Scenario: Governor 明确触发硬性执行阻断
- **WHEN** formal ETF Phase 1 所消费的 Governor 预算明确包含 `allow_new_risk=false`、`force_deleveraging=true` 或等价的显式执行阻断信号
- **THEN** 系统 MUST 优先表现为减仓优先、零新买入或等价的硬性收缩行为
- **THEN** 该行为 MUST 在产物中归因到 Governor 边界，而不是被描述为 ETF 自行选择 `NO_TRADE`

### Requirement: formal ETF Phase 1 不得在 boundary 对齐 change 中静默引入 controlled accumulation
formal ETF Phase 1 的 boundary 对齐 MUST 保持当前 formal alignment 范围，不得在同一 change 中静默引入 `LIGHT` 或 `TRANS_DOWN` 的 `controlled_accumulation` 语义。任何受控承接或加仓带宽研究 SHALL 通过新的非 formal 研究 profile 或独立 change 引入。

#### Scenario: formal Phase 1 profile 继续保持对齐语义
- **WHEN** 系统运行 formal `cn_etf_first_wave_core` 或等价 formal Phase 1 profile
- **THEN** 产物中的 `controlled_accumulation_mode` MUST 仍为 `none`
- **THEN** 系统 MUST 不把本次 boundary 对齐解释为新的 `TRANS_DOWN` 承接策略

#### Scenario: 受控承接研究不得伪装成 formal 对齐
- **WHEN** 研究配置尝试为 formal Phase 1 profile 注入 `light_only`、`light_and_controlled_trans_down` 或等价的承接模式
- **THEN** 系统 MUST 将其标记为超出当前 formal Phase 1 边界
- **THEN** 相关研究结果 SHALL NOT 被标记为 formal mainline 对齐结论
