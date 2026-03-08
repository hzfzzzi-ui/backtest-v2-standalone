## ADDED Requirements

### Requirement: 公开单次回测编排只暴露 foundation shell
公开单次回测入口 SHALL 只把编排真相暴露到 foundation shell；legacy stage adapter 仍可作为 internal implementation detail 存在，但 MUST 不再被公开 API 直接建模或绕过。

#### Scenario: 公开运行返回 experiment-first surface
- **WHEN** 客户端调用公开 run 或 run_async 成功
- **THEN** 返回面以 `experiment_id/exp_id + manifest/report endpoint` 为中心，而不是暴露 legacy execution internals

#### Scenario: foundation shell 仍是唯一公开编排边界
- **WHEN** 公开单次回测主链执行一次实验
- **THEN** orchestrator 通过 foundation shell 进入 stage pipeline / legacy adapter，而不会新增第二条公开执行路径
