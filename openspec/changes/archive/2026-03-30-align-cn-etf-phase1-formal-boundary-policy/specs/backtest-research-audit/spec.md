## ADDED Requirements

### Requirement: research audit 必须区分 formal ETF Phase 1 的 Governor 边界与本地 boundary 决策
当实验属于 Governed A 股主线，且 ETF sleeve 以 formal `phase1_allocation_engine` 运行时，`research_audit` MUST 分别引用 Governor 下发边界证据与 ETF 本地 boundary 决策证据。审计 SHALL NOT 仅凭零部署或低部署结果，就把 ETF 本地 boundary 选择误记为 Governor 零预算真相。

#### Scenario: Governor 明确导致零部署
- **WHEN** formal ETF Phase 1 的零部署直接由 Governor 显式预算阻断或执行阻断导致
- **THEN** `research_audit` MUST 将主原因归类为 Governor 边界
- **THEN** `research_audit` MUST 同时引用对应的 Governor 预算 reason codes 或等价证据

#### Scenario: Governor 仍给正预算但 ETF 本地 boundary 压缩部署
- **WHEN** Governor 仍下发正预算，但 formal ETF Phase 1 的本地 boundary 或 contract 结果导致目标为零或显著低于预算
- **THEN** `research_audit` MUST 将主原因归类为 ETF 本地 boundary 决策
- **THEN** `research_audit` MUST 引用本地 boundary reason codes、配置 contract 或等价 sleeve 证据，而不是把该结果描述成 Governor 零预算

### Requirement: research audit 必须能回答 formal ETF Phase 1 为什么进入 reduced allocation 或 no-trade
当实验属于 Governed A 股 formal ETF Phase 1 时，`research_audit` MUST 能明确回答 ETF sleeve 当天处于 reduced allocation、deleveraging 还是 `NO_TRADE` 的具体原因，并区分这是文档允许的三桶过渡，还是显式风险阻断。

#### Scenario: RISK_OFF 下的缩减配置可解释
- **WHEN** formal ETF Phase 1 在 `RISK_OFF` 下仍生成缩减后的配置目标
- **THEN** `research_audit` MUST 能说明该行为符合 formal 文档中的权益降配、防守倾向与现金缓冲语义
- **THEN** 审计输出 MUST 不把该行为标记为越过 Governor 的独立风险判断

#### Scenario: NO_TRADE 来自显式风险阻断
- **WHEN** formal ETF Phase 1 表现为 `NO_TRADE` 或零新买入
- **THEN** `research_audit` MUST 能明确说明这是由显式风险阻断、去风险要求或等价执行边界导致
- **THEN** 审计输出 MUST 不使用模糊表述掩盖边界来源
