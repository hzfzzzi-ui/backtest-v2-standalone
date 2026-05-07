## ADDED Requirements

### Requirement: Research runtime 必须消费已冻结 snapshot
系统 SHALL 允许 research runtime 直接消费已生成的 factor snapshot 与 state score snapshot，而不是在消费侧默认重算研究逻辑。

#### Scenario: factor snapshot 作为研究输入
- **WHEN** 研究者为 study runner 提供 factor snapshot 输入
- **THEN** research runtime SHALL 使用该 snapshot 作为研究输入真相

#### Scenario: state score snapshot 作为研究输入
- **WHEN** 研究者为 study runner 提供 state score snapshot 输入
- **THEN** research runtime SHALL 使用该 snapshot 作为状态研究输入真相
