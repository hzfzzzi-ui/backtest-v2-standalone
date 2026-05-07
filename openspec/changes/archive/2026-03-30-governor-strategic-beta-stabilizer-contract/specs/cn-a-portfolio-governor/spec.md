## ADDED Requirements

### Requirement: Governor 必须向正式 sleeve 发布分层预算合同
`cn-a-portfolio-governor` MUST 将正式 sleeve 的预算真相拆分为可审计的分层合同，而不是只发布单一 `target_exposure`。对每个正式 sleeve，Governor SHALL 至少输出：

- `strategic_floor_cap`
- `tactical_overlay_cap`
- `deployment_pace`
- `hard_block_flags`
- `defense_bias`

现有 `target_exposure` 若继续保留，MUST 仅作为聚合视图存在，且 SHALL NOT 取代上述分层预算字段作为正式真相来源。

#### Scenario: Governor 在正常风险环境下发布分层预算
- **WHEN** Governor 评估某个正式 sleeve 处于可承担正常风险的状态
- **THEN** Governor MUST 输出正的 `strategic_floor_cap`
- **THEN** Governor MAY 输出正的 `tactical_overlay_cap`
- **THEN** Governor MUST 输出明确的 `deployment_pace`

#### Scenario: Governor 在弱市但未硬阻断时压缩 overlay
- **WHEN** Governor 判断市场转弱但未触发 `allow_new_risk=false`、`force_deleveraging=true` 或等价硬阻断
- **THEN** Governor MUST 允许 `strategic_floor_cap` 与 `tactical_overlay_cap` 分别变化
- **THEN** Governor SHALL NOT 仅因状态转弱就把全部 budget 静默折叠成单一零目标

#### Scenario: Governor 在硬阻断时显式发布停止新增风险信号
- **WHEN** Governor 触发 `allow_new_risk=false`、`force_deleveraging=true` 或等价硬阻断条件
- **THEN** Governor MUST 在 `hard_block_flags` 中显式输出阻断原因
- **THEN** Governor MUST 允许下游 sleeve 区分“底仓仍允许持有”和“禁止新增风险”两类语义

### Requirement: 正式 Governor 合同不得从固定 research combo 权重派生生产预算
`cn-a-portfolio-governor` SHALL NOT 将固定 stock/ETF 权重假设，例如 `50/50`，解释为正式生产级 sleeve budget 真相。任何固定组合权重只能作为 `research_combo_only` 假设存在，并 MUST 与正式 Governor 合同明确区分。

#### Scenario: 研究组合使用固定 50/50 权重
- **WHEN** 系统运行 `CN_STOCK_ETF_50_50` 或等价 research combo
- **THEN** 该实验 MUST 在 `run_meta`、`audit` 或等价正式产物中显式标记为 `research_combo_only`
- **THEN** 系统 SHALL NOT 将该组合权重写回正式 Governor 预算真相

#### Scenario: 正式多 sleeve 运行发布预算
- **WHEN** 系统进入正式 Governor 驱动的多 sleeve 运行
- **THEN** sleeve budget MUST 来源于 Governor 分层合同
- **THEN** sleeve budget SHALL NOT 默认回退到固定 `0.5 / 0.5` 权重
