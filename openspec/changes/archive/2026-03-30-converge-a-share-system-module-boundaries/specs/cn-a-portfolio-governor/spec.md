## ADDED Requirements

### Requirement: 组合总控只定义组合级正式边界
`cn-a-portfolio-governor` MUST 只输出组合级风险环境、总预算边界、子系统预算上限、硬阻断与防守倾向。Governor SHALL NOT 将个股子系统或 ETF 子系统的内部模板、建仓节奏、恢复模式或研究诊断字段提升为正式组合级真相。

#### Scenario: Governor 向个股与 ETF 发布预算
- **WHEN** Governor 为 A 股个股子系统和 ETF 子系统生成正式预算快照
- **THEN** 输出 MUST 只包含组合级状态、预算边界、硬阻断与防守倾向
- **THEN** 输出 SHALL NOT 直接包含子系统内部模板权重或研究诊断缺口字段

#### Scenario: 子系统存在内部模板或恢复模式
- **WHEN** ETF 子系统或个股子系统在内部使用模板、恢复语义或其他局部控制逻辑
- **THEN** Governor SHALL NOT 将这些内部语义回写成组合级正式合同
- **THEN** 正式预算真相 MUST 仍然保持在组合级边界层
