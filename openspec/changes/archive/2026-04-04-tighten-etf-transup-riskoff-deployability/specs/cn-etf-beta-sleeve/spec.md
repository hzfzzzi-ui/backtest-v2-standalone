# cn-etf-beta-sleeve Specification Delta

## MODIFIED Requirements

### Requirement: research standalone ETF mainline 在正风险目标下必须给出可部署的 RISK_OFF contract

当 `cn_etf_beta` 以 `governed_broad_based_standalone_mainline` 且 `exposure_policy_family=broad_based_standalone_mainline_v1` 运行时，如果 `RISK_OFF` 下仍存在正的 `target_exposure` 且 Governor 未发出 hard block，系统 MUST 给出非零 `deployment_pace`，并 SHALL NOT 把该日静默解释为 `RISK_OFF_ZERO`。

#### Scenario: RISK_OFF 正目标暴露不再被静默压成零
- **WHEN** standalone ETF mainline 处于 `RISK_OFF`
- **AND** `target_exposure > 0`
- **AND** 不存在 `allow_new_risk=false` 或等价 hard block
- **THEN** `deployment_pace` MUST 大于 `0`
- **THEN** diagnostics MUST 明确说明这是 `RISK_OFF` 下的 core-only 风险承接，而不是 `NO_TRADE`

### Requirement: research standalone ETF mainline 在 TRANS_UP 必须支持持续 recovery fill

当 `cn_etf_beta` 以 standalone mainline 运行且处于 `TRANS_UP` 时，系统 MUST 支持在非 rebalance 日持续补齐强状态风险缺口，而不是只在状态切换当天提供一次性的恢复机会。

#### Scenario: TRANS_UP 非 rebalance 日持续追平缺口
- **WHEN** standalone ETF mainline 处于 `TRANS_UP`
- **AND** `actual_exposure` 明显低于当日 target
- **AND** 不存在 Governor hard block
- **THEN** provider MUST 允许发出 `gap-fill` BUY 信号
- **THEN** 该执行路径 SHALL NOT 退化成统一的 `hold_until_rebalance`

### Requirement: research standalone ETF mainline 在 BULL 与 TRANS_UP 必须显式追平强状态 target gap

当 standalone ETF mainline 在 `BULL` 或 `TRANS_UP` 下存在显著的 target-actual gap 时，系统 MUST 允许使用明确的 `execution_path` 与 `reason_code` 去追平该缺口，直到 gap 收敛或被 hard block/selection failure 明确阻断。

#### Scenario: BULL 强状态允许 gap-fill
- **WHEN** standalone ETF mainline 处于 `BULL`
- **AND** 当日 `actual_exposure` 明显低于 target
- **THEN** 系统 MUST 支持非 rebalance 日的补仓路径
- **THEN** 产物 MUST 能区分该路径与常规 rebalance BUY

#### Scenario: TRANS_UP 强状态允许 gap-fill
- **WHEN** standalone ETF mainline 处于 `TRANS_UP`
- **AND** 当日 `actual_exposure` 明显低于 target
- **THEN** 系统 MUST 支持非 rebalance 日的补仓路径
- **THEN** 产物 MUST 输出 gap-fill 原因与未触发阻断原因

### Requirement: standalone ETF mainline 的 deployability 证据必须能直接验证 target-actual 偏差

对于 standalone ETF mainline，`run_meta`、`audit` 或等价研究产物 MUST 能直接展示 `BULL/TRANS_UP` 下的 `avg_target_exposure`、`avg_actual_exposure`、`avg_pace_policy_gap` 与 `execution_path_day_counts`，以支持验证目标暴露与实际暴露的偏差是否收敛。

#### Scenario: BULL/TRANS_UP 偏差可直接核对
- **WHEN** standalone ETF mainline 完成一次研究回测
- **THEN** 研究产物 MUST 同时暴露 `BULL` 与 `TRANS_UP` 的 target/actual/policy-gap 摘要
- **THEN** 用户 SHALL NOT 需要前端重算才能判断 gap 是否进入 `10%` 以内
