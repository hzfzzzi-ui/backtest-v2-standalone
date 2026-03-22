## ADDED Requirements

### Requirement: Overlay 默认关闭且不得改变 baseline 默认行为
系统 MUST 仅在 `asset_context.moneyflow_overlay.enabled=true` 时启用 `moneyflow overlay`。当该配置缺失、为 `false` 或路径校验失败时，运行时 SHALL 回退为 `baseline_V10.1` 的原始行为，不得改变默认排序、仓位和执行时点。

#### Scenario: Overlay 未开启
- **WHEN** 运行配置中没有 `asset_context.moneyflow_overlay.enabled=true`
- **THEN** 系统必须按当前 baseline 逻辑运行，且不加载任何 overlay 因子文件

#### Scenario: Overlay 路径无效
- **WHEN** overlay 已开启但 `factor_panel_path` 或 `coverage_ledger_path` 缺失或不可读
- **THEN** 系统必须显式报错并终止该实验运行，不得静默降级为脏结果

### Requirement: Overlay 必须按月末观察、次交易日生效、月内冻结
系统 MUST 从 `monthly_factor_panel.csv` 中读取 `observation_date` 和月度因子值，并将该月度分数从 `observation_date` 对应的 decision date 开始冻结，直至下一次 `observation_date` 前一日。

#### Scenario: 新月份开始生效
- **WHEN** 某条月度记录的 `observation_date` 为 `2023-07-31`
- **THEN** 该记录的 overlay 分数必须从 `2023-07-31` 决策日开始用于 `2023-08-01` 开盘成交，并在下一观察日到来前保持不变

#### Scenario: 月内非观察日沿用冻结分数
- **WHEN** 决策日位于两次相邻 `observation_date` 之间
- **THEN** 系统必须沿用最近一次观察日生成的同一组 overlay 分数

### Requirement: Overlay 只能在覆盖率达标月份启用
系统 MUST 读取 `monthly_coverage_ledger.csv` 的覆盖率结论。只有当对应观察日 `allow_in_research=true` 时，当月 overlay 才能启用；否则当月 MUST 回退为 baseline 行为，不得把缺失当低分或默认分。

#### Scenario: 覆盖率达标月份启用
- **WHEN** 某观察日在 coverage ledger 中 `allow_in_research=true`
- **THEN** 系统必须允许该观察日对应的 overlay 分数进入实验模式

#### Scenario: 覆盖率不达标月份禁用
- **WHEN** 某观察日在 coverage ledger 中 `allow_in_research=false`
- **THEN** 系统必须在该观察日到下一观察日前的整段区间内关闭 overlay，并保持 baseline 行为

### Requirement: 系统必须支持 shadow、tiebreak、soft_weight 三种模式
系统 MUST 支持以下 overlay 模式：

- `shadow`：仅装载与记录 overlay，不改变排序和仓位
- `tiebreak`：保持 baseline 主排序为第一排序键，仅用 overlay 作为次级排序键
- `soft_weight`：保持 baseline 排序不变，仅用 overlay 驱动 `score_weighted` 仓位缩放

#### Scenario: Shadow 不改交易行为
- **WHEN** overlay 模式为 `shadow`
- **THEN** 系统必须记录 overlay 可用性与分数状态，但最终买卖决策必须与未开启 overlay 时一致

#### Scenario: Tiebreak 保持主排序为第一键
- **WHEN** overlay 模式为 `tiebreak`
- **THEN** 系统必须先按 baseline 当前主排序分数排序，再按 overlay 分数做次级排序

#### Scenario: Soft Weight 只改仓位不改选股顺序
- **WHEN** overlay 模式为 `soft_weight`
- **THEN** 系统必须保持 baseline 当前候选排序顺序，只允许 overlay 分数影响 `score_weighted` 仓位缩放
