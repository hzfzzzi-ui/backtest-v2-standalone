## ADDED Requirements

### Requirement: research audit 必须能审计模板 A 的评分、过滤与 fallback 生效情况
当实验属于“宽基轮动模板 A”时，`research_audit` MUST 能回答以下问题：

- 本轮使用的是 A0 还是 A1
- 当前角色映射是什么
- 哪些角色使用了代理资产
- 相对强弱评分是否真实参与选择
- 绝对过滤是否真实阻止了不合格 ETF
- fallback 是否被触发、触发了多少次

#### Scenario: 模板 A 审计能回答为什么是这些 ETF
- **WHEN** 用户查看模板 A 的 `audit.json`
- **THEN** 审计结果 MUST 能指出当前选中的 ETF、对应角色以及主要选择原因

#### Scenario: 模板 A 审计能回答为什么没上某个 ETF
- **WHEN** 某个模板 A 候选 ETF 未被选中
- **THEN** 审计结果 MUST 能指出它是被评分淘汰、绝对过滤淘汰还是角色位未开放

### Requirement: research audit 必须能区分模板 A 的 proxy 结果与正式结果
当模板 A 使用代理资产时，`research_audit` MUST 显式标记该实验属于 proxy 版本结果，并且 SHALL NOT 把它表达为正式完整池结果。

#### Scenario: A0 结果显式标记 proxy
- **WHEN** 模板 A 运行在 A0 版本
- **THEN** `research_audit` MUST 显示当前结果含 proxy 角色
- **THEN** 审计摘要 MUST 能提示该结果不能直接等同于 A1 正式池结论
