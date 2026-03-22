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

### Requirement: 正式执行总线中的 diagnostics adapter 必须成为唯一归一化层
系统 MUST 将正式执行总线中的 diagnostics adapter 视为最终 diagnostics 归一化的唯一 owner。`daily_accounting.py` 等执行 facade 可以产出原始 diagnostics input，但 SHALL NOT 重新承担最终 stage count 语义。

#### Scenario: stage pipeline 写入 daily row
- **WHEN** stage pipeline 在日循环结束后写入 daily row 或 accounting snapshot
- **THEN** 执行 facade MUST 仅写入原始执行事实和 diagnostics input
- **THEN** 最终 diagnostics 归一化 MUST 延后到 diagnostics adapter 或 builder

#### Scenario: provider 或 runtime 路由扩展
- **WHEN** 后续 provider 或 runtime route 扩展新的诊断字段
- **THEN** 系统 MUST 通过 diagnostics adapter 接线
- **THEN** 执行 facade SHALL NOT 因扩展诊断字段重新长回重型 diagnostics owner

### Requirement: 执行 compat shim 必须持续收缩且禁止吸收新逻辑
系统 MUST 持续收缩 `foundation_shell`、strict shim、`portfolio_builder.py` 和 `legacy_loop.py` 的职责边界。新执行逻辑、策略分支或记账规则 SHALL NOT 再进入这些文件。

#### Scenario: 需要接入新的执行逻辑
- **WHEN** 需要新增执行相关逻辑
- **THEN** 该逻辑 MUST 进入正式执行总线、provider 或 pipeline built-in module 路径
- **THEN** compat shim SHALL NOT 成为该逻辑的落点

#### Scenario: compat 文件仍然存在
- **WHEN** compat 文件短期内仍需保留
- **THEN** 它们 MUST 仅承担过渡分发或兼容包装职责
- **THEN** 文件头或文档 MUST 明确标注删除路径

### Requirement: 执行 compat 清理必须通过固定回归锚点验证
系统 MUST 使用固定回归锚点验证执行 compat 清理不会导致价格型信号口径漂移。对于本仓库当前主线，清理过程中 MUST 至少复核 `baseline_V10_1` 对应的固定回归快照。

#### Scenario: 清理执行 compat 文件
- **WHEN** 任何一次清理触及 `foundation_shell`、strict shim、`portfolio_builder.py` 或 `legacy_loop.py`
- **THEN** 系统 MUST 在清理前后复核固定回归锚点的关键 perf / trade 指标
- **THEN** 若结果漂移，则清理 SHALL NOT 继续推进

#### Scenario: 价格型信号路径
- **WHEN** 清理涉及使用 `close/high/low/volume/amount` 的价格型信号执行路径
- **THEN** 系统 MUST 重点复核信号时点和 `t+1` 执行口径
- **THEN** 清理 SHALL NOT 改变该执行语义

