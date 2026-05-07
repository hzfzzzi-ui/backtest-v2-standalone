## MODIFIED Requirements

### Requirement: research standalone ETF mainline 在 `TRANS_UP` 下 MUST 支持 live deployable target

当 ETF 单腿以 `governed_broad_based_standalone_mainline` 运行，且当前 `effective_state_5=TRANS_UP` 时，系统 MUST 不再把 `TRANS_UP` 默认压缩成 floor-only 的纸面部署节奏。系统 MUST 允许将已批准的 `TRANS_UP target_exposure` 转成 live deployable target，并允许 provider 在非调仓日对当前选中的 live seat 执行补仓。

#### Scenario: standalone mainline 在 `TRANS_UP` 下进行非调仓日补仓
- **WHEN** ETF research standalone mainline 当前处于 `TRANS_UP`，非调仓日，且不存在 Governor hard block
- **THEN** 系统 MUST 生成正的 `deployment_pace`
- **THEN** provider MUST 允许对当前 live seat 生成 `inter_rebalance_deploy` BUY path，而不是统一停留在 `hold_until_rebalance`

#### Scenario: `TRANS_UP` 审计证据可区分 deploy path
- **WHEN** standalone mainline 在 `TRANS_UP` 下触发或拒绝非调仓日补仓
- **THEN** `run_meta.json` 与 `audit.json` MUST 能区分 `inter_rebalance_deploy` 与常规 rebalance path
- **THEN** 产物 MUST 记录对应的 reason code、execution path 和 gap attribution

### Requirement: research standalone ETF mainline 在 `RISK_OFF` 下 MUST 支持 core-only 小幅累积

当 ETF 单腿以 `governed_broad_based_standalone_mainline` 运行，且当前 `effective_state_5=RISK_OFF` 时，只要不存在显式 hard block，系统 MUST 允许保留正的 `deployment_pace`。该部署语义 MUST 仅用于 `core_accumulator` 的小幅受控累积，SHALL NOT 在 `RISK_OFF` 下恢复 growth seat 或多 risk seat 扩张。

#### Scenario: `RISK_OFF` 下允许 core-only 小幅 live accumulation
- **WHEN** ETF research standalone mainline 当前处于 `RISK_OFF`，非调仓日，且 `min_deployable_exposure > 0`
- **THEN** 系统 MUST 允许 `deployment_pace > 0`
- **THEN** provider MUST 只对 `core_accumulator` 生成小幅累积 BUY path

#### Scenario: `RISK_OFF` 不得恢复 growth seat
- **WHEN** ETF research standalone mainline 当前处于 `RISK_OFF`
- **THEN** 系统 SHALL NOT 在非调仓日把 `growth seat` 作为 live deploy 目标
- **THEN** 系统 SHALL NOT 把 `RISK_OFF` 解释成多席位恢复状态

### Requirement: standalone ETF 的 held symbol top-up MUST 仅在部署路径下放开

当 research standalone mainline 处于 `RISK_OFF / TRANS_UP` 的新部署路径时，provider MUST 允许对已持有 symbol 再次生成 BUY 信号，用于把仓位补到合同批准的绝对目标。除此之外，既有 non-phase1 BUY 规则 SHALL 保持不变。

#### Scenario: 部署路径允许 held symbol top-up
- **WHEN** standalone mainline 在 `TRANS_UP` 或 `RISK_OFF` 下触发 `inter_rebalance_deploy`
- **THEN** provider MUST 允许对已持有 symbol 生成补仓 BUY
- **THEN** BUY 信号 meta MUST 继续携带绝对目标仓位，而不是改成增量语义

#### Scenario: 普通 research path 仍保持原有限制
- **WHEN** standalone research path 不属于本轮新增部署路径
- **THEN** non-phase1 默认 BUY 规则 MUST 保持现状
- **THEN** 系统 SHALL NOT 把所有 research-only BUY 都放开成可重复补仓
