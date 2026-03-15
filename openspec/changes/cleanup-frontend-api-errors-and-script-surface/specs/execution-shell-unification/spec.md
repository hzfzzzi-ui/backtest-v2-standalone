## ADDED Requirements

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
