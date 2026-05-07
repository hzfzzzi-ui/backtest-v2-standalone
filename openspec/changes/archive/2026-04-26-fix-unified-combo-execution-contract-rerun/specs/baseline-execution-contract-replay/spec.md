## ADDED Requirements

### Requirement: Baseline replay MUST resolve the bound execution contract
正式 baseline 复跑 SHALL 通过 `baseline.json.execution_contract_ref` 定位并读取正式 `execution_contract.json`，而不是通过 `baseline_config_snapshot.json` 重新推导执行真相。

#### Scenario: replaying a baseline with execution_contract_ref
- **WHEN** 系统复跑 `outputs/baselines/<baseline_id>/baseline.json` 中带有 `execution_contract_ref` 的 baseline
- **THEN** 系统 MUST 从该引用指向的 artifact 读取 execution contract
- **THEN** 系统 MUST 使用该 execution contract 进入 runtime
- **THEN** `baseline_config_snapshot.json` SHALL 只作为编辑恢复或兼容输入，不得覆盖 execution contract

### Requirement: Baseline replay MUST fail visibly when the bound contract is missing
如果 baseline 声明了 `execution_contract_ref` 但 artifact 无法定位或 hash 校验失败，系统 SHALL 显式失败，不得静默回退到 snapshot 重编译。

#### Scenario: missing bound execution contract
- **WHEN** baseline 的 `execution_contract_ref.artifact` 不存在或无法读取
- **THEN** 系统 MUST 返回明确错误
- **THEN** 系统 SHALL NOT 用 `baseline_config_snapshot.json` 重新编译并伪装成正式复跑

### Requirement: Baseline replay MUST preserve component execution semantics
通过 baseline 合同复跑 unified combo 时，子腿执行语义 SHALL 与合同内组件参数一致，包括 `runtime_config` 与 `execution_overrides`。

#### Scenario: replaying A_STOCK_ETF_V1
- **WHEN** 系统按 `A_STOCK_ETF_V1` 的正式 execution contract 复跑
- **THEN** stock component MUST 保留 final_score/MF 排名相关 execution overrides
- **THEN** ETF component MUST 保留合同声明的 ETF source entry、资产池、复权口径和 fallback 规则
