# execution-shell-unification Specification

## Purpose

定义当前正式执行总线的单一入口与运行边界，确保执行链只通过统一执行壳进入共享执行路径。

## Requirements

### Requirement: stage pipeline MUST be the formal execution route

系统 MUST 将 `stage_pipeline.shell` 定义为正式执行总线。

#### Scenario: 正式实验进入执行总线
- **WHEN** runtime service 触发一次正式实验运行
- **THEN** 系统通过统一执行入口进入 `stage_pipeline.shell`
- **THEN** 不暴露并行的第二套正式执行入口

### Requirement: foundation shell MUST be the application-facing execution entry

系统 MUST 将 `foundation_shell` 作为应用层进入执行总线的统一入口。

#### Scenario: 应用层发起执行
- **WHEN** API 或 runtime service 需要运行实验
- **THEN** 它们调用 `foundation_shell`
- **THEN** 具体执行细节在统一执行总线内部完成
