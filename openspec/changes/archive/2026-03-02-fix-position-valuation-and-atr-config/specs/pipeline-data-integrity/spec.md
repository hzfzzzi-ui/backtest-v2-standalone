## MODIFIED Requirements

### Requirement: exit_rules 参数完整映射（修改）

原要求：`_build_runtime_cfg_from_workbench()` 映射 exit_rules 子项到 strategy.params。
新增：`atr_stop_k` 必须（SHALL）同时写入 `ExitConfig` 且不被 loader 丢弃。

#### Scenario: atr_stop_k 通过 ExitConfig 传递
- **WHEN** 用户配置 `exit.atr_stop_k = 1.5`
- **THEN** `loader.py` 不过滤该字段
- **AND** `ExitConfig.atr_stop_k` 等于 1.5

#### Scenario: atr_stop_k 向后兼容
- **WHEN** 旧配置 JSON 中 exit 区无 atr_stop_k 字段，但 risk_budget.atr_stop_k=2.5
- **THEN** 引擎使用 risk_budget.atr_stop_k=2.5 作为回退值

#### Scenario: ExitConfig 新增 atr_stop_k 字段
- **WHEN** `ExitConfig` dataclass 定义
- **THEN** 必须包含 `atr_stop_k: float = 2.0` 字段

---

## ADDED Requirements

### Requirement: atr_stop_k 优先级规则

引擎读取 atr_stop_k 时，必须（SHALL）优先使用 `ExitConfig.atr_stop_k`，仅当其为默认值（2.0）时回退到 `RiskBudgetConfig.atr_stop_k`。

#### Scenario: 用户修改 exit.atr_stop_k
- **WHEN** ExitConfig.atr_stop_k=1.5，RiskBudgetConfig.atr_stop_k=2.0
- **THEN** 引擎使用 1.5

#### Scenario: 用户未修改 exit.atr_stop_k
- **WHEN** ExitConfig.atr_stop_k=2.0（默认），RiskBudgetConfig.atr_stop_k=3.0
- **THEN** 引擎使用 3.0（回退到 risk_budget）

#### Scenario: 三条引擎路径一致
- **WHEN** atr_stop_k 优先级规则应用
- **THEN** SMA 路径、Generic 路径、RegimeRouter 路径均使用相同的优先级逻辑
