# execution-shell-unification Specification

## Purpose
Synced from delta spec during archive. The capability contract is now part of the main spec set.

## Requirements

### Requirement: stage pipeline 必须成为唯一正式执行总线
系统 MUST 将 `stage_pipeline.shell` 定义为唯一正式日循环执行总线。所有正式实验运行 SHALL 通过 `foundation_shell` 进入执行总线，SHALL NOT 直接调用 strict 或 legacy 主循环。

#### Scenario: 正式实验运行进入执行总线
- **WHEN** runtime service 触发一次正式实验运行
- **THEN** 系统 MUST 调用 `foundation_shell`
- **THEN** `foundation_shell` MUST 将执行请求转交给 `stage_pipeline.shell`

#### Scenario: 旧壳不再作为正式入口
- **WHEN** 新执行总线已承担正式运行职责
- **THEN** strict 和 legacy 壳 SHALL NOT 继续作为新功能的正式入口
- **THEN** 旧壳仅可承担过渡 shim 职责

### Requirement: foundation shell 必须是主系统唯一兼容门
系统 MUST 将 `foundation_shell.py` 作为主系统到执行总线的唯一兼容门。runtime service SHALL NOT 直接依赖 `portfolio_simulator_strict.py` 或 `portfolio_builder.py`。

#### Scenario: runtime service 发起执行
- **WHEN** 应用层需要运行实验
- **THEN** 应用层 MUST 只调用 `foundation_shell`
- **THEN** 调用链 SHALL 保持与 strict/legacy 具体实现解耦

#### Scenario: 执行入口收敛
- **WHEN** 新总线完全承担正式执行
- **THEN** 系统 MUST 能在不影响调用方的前提下移除 strict/legacy 直接依赖
- **THEN** 兼容成本 MUST 被集中在 `foundation_shell`

### Requirement: legacy 必须进入删除路径
系统 MUST 将 strict shim、`legacy_adapter.py` 和 `legacy_loop.py` 视为待删除过渡层，而不是长期兼容层。新逻辑 SHALL NOT 再进入这些文件。

#### Scenario: 新逻辑扩展执行链
- **WHEN** 需要接入新的执行相关逻辑
- **THEN** 系统 MUST 拒绝将该逻辑直接写入 strict/legacy 主流程
- **THEN** 该逻辑 MUST 进入 provider 或 pipeline built-in module 路径

#### Scenario: golden 稳定后清理 legacy
- **WHEN** 最小覆盖集 golden 稳定通过
- **THEN** 系统 MUST 进入 legacy 删除阶段
- **THEN** 删除顺序 MUST 先处理 strict 主流程分支，再处理 legacy adapter/loop

### Requirement: 默认 route 拆分后仍必须保持统一执行入口
系统 MUST 允许默认 route 的具体实现拆成多个阶段模块，但 `strict_runtime_default.py` 仍 SHALL 只作为默认 route 的 facade 入口存在。该拆分 SHALL NOT 引入新的并行执行入口，也 SHALL NOT 绕过既有统一执行入口链路。

#### Scenario: 默认 route 完成阶段拆分
- **WHEN** 系统将默认 route 拆为 `input`、`benchmark`、`signal`、`daily-loop` 和 `result` 模块
- **THEN** 调用方 MUST 仍通过既有默认 route facade 进入执行
- **THEN** 系统 SHALL NOT 因模块化重新暴露额外的正式执行入口

#### Scenario: 默认 route facade 收口
- **WHEN** 后续需要扩展默认 route 内部逻辑
- **THEN** 系统 MUST 在阶段模块内扩展
- **THEN** facade 文件 SHALL NOT 重新长回重型实现文件


