# architecture-closure-gates Specification

## Purpose

Synced from delta spec during archive. The capability contract is now part of the main spec set.

## Requirements

### Requirement: 架构收口必须按 P0 和 P1 两个正式波次推进
本轮架构收口 MUST 被拆为 `P0` 和 `P1` 两个正式波次。`P0` MUST 先于 `P1` 完成，且每个波次 MUST 具有显式进入条件、通过条件和阻断条件。

#### Scenario: P0 验收通过
- **WHEN** `P0` 完成实现并执行验收
- **THEN** 默认 `pytest` 命令 MUST 能完成 collect
- **THEN** 脚本面治理测试与前端 owner 边界测试 MUST 通过
- **THEN** `baseline_V10.1` 主线回归结果 MUST 不发生口径漂移

#### Scenario: P0 未完成时尝试启动 P1
- **WHEN** `P0` 的通过条件尚未满足
- **THEN** 本 change SHALL NOT 继续进入 `P1` 实现批次
- **THEN** 未通过的 `P0` 阻断项 MUST 先被修复或回退

### Requirement: 架构收口必须保护 baseline_V10.1 主线
本轮架构收口 MUST 以 `baseline_V10.1` 为唯一正式回归锚点。任何任务 SHALL NOT 改变其信号时点、执行时点、成交规则、资产池定义和正式产物口径。

#### Scenario: 收口任务导致主线结果漂移
- **WHEN** 任一 `P0/P1` 任务导致 `baseline_V10.1` 的核心结果、计数器或产物协议发生非预期漂移
- **THEN** 该任务 MUST 被阻断或回退
- **THEN** 系统 SHALL NOT 以“结构清理”为理由接受该漂移

#### Scenario: 收口任务只调整入口与边界
- **WHEN** 某个任务仅处理测试、入口、文档、边界或模块职责收口
- **THEN** 系统 MAY 接受代码位置或宿主模块变化
- **THEN** 相关运行口径 MUST 保持不变
