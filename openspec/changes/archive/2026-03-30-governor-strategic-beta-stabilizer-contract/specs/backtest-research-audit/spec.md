## ADDED Requirements

### Requirement: research audit 必须分层归因 ETF stabilizer 的目标与实际暴露
当实验启用 `strategic_beta_stabilizer` 语义时，`backtest-research-audit` MUST 能分别审计以下层次，而不是只输出单层 `target_exposure / actual_exposure`：

- `strategic_floor_target`
- `tactical_overlay_target`
- `deployment_pace`
- `actual_core_exposure`
- `actual_satellite_exposure`
- `actual_defense_exposure`
- `hard_block_flags`

#### Scenario: 正式 ETF stabilizer 实验生成分层审计
- **WHEN** 实验启用了正式 ETF stabilizer 语义
- **THEN** `audit.json` MUST 暴露 floor、overlay、deployment pace 与 hard block 的正式审计字段
- **THEN** 审计结果 MUST 能解释实际暴露分别来自底仓、卫星和防守层

#### Scenario: 弱市下的低仓位可被解释
- **WHEN** 实验在弱市下出现低暴露或低成交
- **THEN** 审计 MUST 能区分这是因为 floor 保留但 overlay 收缩
- **THEN** 审计 MUST 能区分这是因为 Governor 硬阻断，还是 ETF stabilizer 本地选择降低部署节奏

### Requirement: research audit 必须区分正式 Governor 真相与 research combo 假设
`backtest-research-audit` MUST 将固定 `50/50` stock/ETF 组合、等权拼接或等价实验模式标记为 `research_combo_only`，并 SHALL NOT 将其解读为正式 Governor 预算真相。

#### Scenario: 研究组合运行使用固定 50/50
- **WHEN** 实验运行采用 `CN_STOCK_ETF_50_50` 或等价 research combo 模式
- **THEN** 审计 MUST 显式标记该实验依赖 `research_combo_only` 假设
- **THEN** 审计 SHALL NOT 将固定 50/50 权重描述为正式 Governor 输出

#### Scenario: 正式 Governor 驱动运行
- **WHEN** 实验使用正式 Governor 合同驱动 sleeve 预算
- **THEN** 审计 MUST 以 Governor 合同字段解释 ETF 目标与实际暴露
- **THEN** 审计 SHALL NOT 回退到 `research_combo_only` 叙述
