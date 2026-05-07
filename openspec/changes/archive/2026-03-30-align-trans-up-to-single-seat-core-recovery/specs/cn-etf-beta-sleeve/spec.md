## ADDED Requirements

### Requirement: formal ETF stabilizer 的 TRANS_UP 必须是单 seat core recovery
当 `cn-etf-beta-sleeve` 以 formal `strategic_beta_stabilizer` 运行且当前有效状态为 `TRANS_UP` 时，系统 MUST 将该状态解释为 `single-seat core recovery`。该 live 合同 MUST 只允许 `core_accumulator` 作为可部署风险载体；系统 SHALL NOT 在 `TRANS_UP` 下保留需要第二个 seat 的独立 `tactical_satellite` live 目标。

#### Scenario: TRANS_UP 下 live target 只指向 core
- **WHEN** formal ETF stabilizer 在某个交易日进入 `TRANS_UP`
- **THEN** 系统 MUST 将 `TRANS_UP` 的 live deployable target 收敛到 `core_accumulator`
- **THEN** 系统 SHALL NOT 为 `tactical_satellite` 生成独立于 core 之外、需要第二个 seat 的 live target

#### Scenario: TRANS_UP 下单 seat 合同优先于纸面模板
- **WHEN** `TRANS_UP` 的模板预算、旧字段或历史语义仍存在 satellite overlay 痕迹
- **THEN** 系统 MUST 以单 seat core recovery 合同作为正式执行真相
- **THEN** 系统 MUST 不得把这些历史痕迹继续当作可执行 overlay 预算

### Requirement: TRANS_UP 的 monthly 与 redeploy 路径必须共享同一单 seat 语义
formal ETF stabilizer 在 `TRANS_UP` 下的 monthly rebalance 路径与状态切换 redeploy 路径 MUST 共享同一份单 seat core recovery 语义。无论是月末调仓还是 `TRANS_UP` 状态切换触发的非月末补仓，系统都 SHALL NOT 借由路径差异恢复第二个 seat 的 satellite overlay。

#### Scenario: TRANS_UP 的 monthly rebalance 不得选出第二个风险 seat
- **WHEN** formal ETF stabilizer 在 `TRANS_UP` 的月末 rebalance 日生成 ETF 目标或 BUY 信号
- **THEN** 系统 MUST 将其限制在单 seat core recovery 范围内
- **THEN** 系统 SHALL NOT 因为是月末路径就额外放出 `tactical_satellite` 风险 seat

#### Scenario: TRANS_UP 的 state-change redeploy 仍然是 core-only
- **WHEN** formal ETF stabilizer 触发 `TRANS_UP` 状态切换 redeploy
- **THEN** redeploy MUST 继续只补 `core_accumulator` 的 floor gap
- **THEN** redeploy SHALL NOT 被解释为 overlay 提前部署或 second-seat 恢复
