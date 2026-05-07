## ADDED Requirements

### Requirement: Formal ETF stabilizer 必须支持 `TRANS_UP` 状态切换的 strategic floor redeploy
当 formal ETF stabilizer 运行在 `phase1_bucket_allocation` / `strategic_beta_stabilizer` 语义下时，系统 MUST 在有效状态从 `{LIGHT, TRANS_DOWN, RISK_OFF}` 切换到 `TRANS_UP` 且 Governor 未硬阻断时，允许一次不等待月末的 `strategic floor` redeploy。该 redeploy MUST 继续遵守 next-open execution、cash/lot 约束和现有 Governor budget contract。

#### Scenario: 从防守段进入 TRANS_UP
- **WHEN** ETF stabilizer 的有效状态从 `LIGHT`、`TRANS_DOWN` 或 `RISK_OFF` 切换到 `TRANS_UP`
- **THEN** 系统 MUST 允许为 `strategic floor` 生成一次 redeploy 机会
- **THEN** 系统 SHALL NOT 因“不是月末 rebalance 日”而直接放弃这次 floor 承接

#### Scenario: Governor 硬阻断存在
- **WHEN** 当前 `TRANS_UP` 切换日存在 Governor hard block
- **THEN** 系统 SHALL NOT 触发 redeploy
- **THEN** 产物 MUST 记录未触发的阻断原因

### Requirement: TRANS_UP redeploy 必须限定为 core-only floor 补齐
`TRANS_UP` 状态切换 redeploy MUST 只用于补齐 `core_accumulator` 对应的 strategic floor，SHALL NOT 在非月末日触发 `tactical_satellite` 轮换或完整月度 rebalance 语义。

#### Scenario: 非月末 TRANS_UP redeploy
- **WHEN** redeploy 发生在非月末日
- **THEN** 生成的买单 MUST 仅指向 `core_accumulator_symbols`
- **THEN** 系统 SHALL NOT 因这次 redeploy 改写当期 satellite selection 结果

#### Scenario: 当前 core floor 已满足
- **WHEN** 当前 `actual_core_exposure` 已达到或超过 `strategic_floor_target`
- **THEN** 系统 SHALL NOT 再次触发 redeploy
- **THEN** 产物 MUST 记录“floor 已满足”的未触发原因

### Requirement: TRANS_UP redeploy 必须输出可审计的最小证据
当 formal ETF stabilizer 发生或拒绝 `TRANS_UP` state-change redeploy 时，系统 MUST 在日级或订单级产物中暴露最小可审计证据，至少包括：

- 是否触发 `TRANS_UP` redeploy
- 触发或拒绝原因
- 是否属于 `monthly rebalance` 还是 `state-change redeploy`
- 当前 strategic floor gap 摘要

#### Scenario: redeploy 成功触发
- **WHEN** 系统在 `TRANS_UP` 状态切换日触发一次 core-only redeploy
- **THEN** `orders.csv` 或等价订单产物 MUST 含有专属 reason_code 或元数据，明确这是 `TRANS_UP` redeploy
- **THEN** `portfolio_daily.csv` 或等价日级产物 MUST 能回答当天为何在非月末日买入

#### Scenario: redeploy 未触发
- **WHEN** 系统在 `TRANS_UP` 状态切换日未触发 redeploy
- **THEN** 产物 MUST 能区分至少 `hard_block`、`floor_already_satisfied` 和 `not_state_change_edge`
- **THEN** 产物 SHALL NOT 只给出笼统的 `HOLD_UNTIL_REBALANCE`
