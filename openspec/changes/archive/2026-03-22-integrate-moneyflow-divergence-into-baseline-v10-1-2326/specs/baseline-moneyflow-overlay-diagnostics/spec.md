## ADDED Requirements

### Requirement: Overlay 运行元信息必须进入实验产物
当 overlay 开启时，系统 MUST 在实验产物中记录 overlay 的配置与输入来源，至少包括模式、factor panel 路径、coverage ledger 路径、score 字段和是否启用。

#### Scenario: Run Meta 记录 overlay 配置
- **WHEN** overlay 实验运行完成
- **THEN** `run_meta` 或等价运行元信息中必须包含 overlay 的核心配置与输入路径

### Requirement: 每个决策日必须记录 overlay 启停与冻结来源
当 overlay 开启时，系统 MUST 在日频诊断中记录每个决策日的 overlay 状态，至少包括：

- `overlay_enabled`
- `overlay_mode`
- `overlay_gate_on`
- `overlay_observation_date`
- `overlay_score_source`

#### Scenario: 覆盖率关闭的月份写入禁用状态
- **WHEN** 某决策日所在冻结区间的 coverage gate 为关闭
- **THEN** 该日诊断中必须记录 `overlay_gate_on=false` 和对应的观察日或禁用原因

#### Scenario: 覆盖率达标的月份写入冻结来源
- **WHEN** 某决策日使用了最近一次观察日的 overlay 分数
- **THEN** 该日诊断中必须记录当前冻结所来自的 `overlay_observation_date`

### Requirement: 候选级诊断必须能看见 overlay 分数
当 overlay 开启时，系统 MUST 在候选级诊断中写出每个候选标的的 overlay 分数，并在需要时写出 baseline 主排序分数，确保后续可以复盘“排序没变但仓位变了”或“排序为什么被次级键改变”。

#### Scenario: Tiebreak 记录双排序信息
- **WHEN** overlay 模式为 `tiebreak`
- **THEN** 候选级诊断必须能同时看到 baseline 主排序分数与 overlay 分数

#### Scenario: Soft Weight 记录权重缩放依据
- **WHEN** overlay 模式为 `soft_weight`
- **THEN** 候选级诊断必须记录 overlay 分数以及最终使用的仓位缩放信息
