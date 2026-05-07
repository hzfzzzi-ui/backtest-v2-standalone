## ADDED Requirements

### Requirement: stock-only 最小 A/B 只允许单因子单动作
系统 SHALL 为当前认可的 stock-only 基线提供 holding/exit fragility 最小 A/B 入口，并且第一轮实验只能比较“基线”与“单个 lifecycle 因子 + 单个 research 动作映射”之间的差异。

#### Scenario: 最小 A/B 锁定单因子单动作
- **WHEN** 用户发起 holding/exit fragility 最小 A/B
- **THEN** 研究运行面 MUST 只允许一个 lifecycle fragility 因子和一个动作映射进入实验配置

#### Scenario: A/B 结果显式记录锚点与因子来源
- **WHEN** 系统完成 holding/exit fragility 最小 A/B
- **THEN** 结果产物 MUST 显式记录 baseline 锚点、factor source、动作映射和实验变更范围
