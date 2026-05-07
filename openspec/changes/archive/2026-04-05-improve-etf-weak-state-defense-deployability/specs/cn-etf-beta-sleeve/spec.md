## ADDED Requirements

### Requirement: ETF beta sleeve 弱势状态必须遵守正式防守承接合同
当 ETF beta sleeve 的 `effective_state_5` 为 `TRANS_DOWN` 或 `RISK_OFF` 时，系统 MUST 使用正式的 `etf-weak-state-defense-policy` 生成候选资产、部署槽位与目标暴露。`BULL` 与 `TRANS_UP` 的进攻段逻辑 SHALL 保持不变。

#### Scenario: 弱势状态切换到正式防守承接路径
- **WHEN** ETF beta sleeve 运行于 `TRANS_DOWN` 或 `RISK_OFF`
- **THEN** 系统 MUST 按 `etf-weak-state-defense-policy` 生成选中结果与部署约束
- **THEN** 系统 SHALL NOT 继续沿用进攻段 ranking 作为弱势默认部署真相

### Requirement: ETF beta sleeve 弱势状态必须可审计地区分未部署原因
ETF beta sleeve 在弱势状态下 MUST 输出可审计的部署解释，至少区分“存在可交易防守资产但被部署约束压零”和“正式防守资产池无可交易资产”两类情形。

#### Scenario: 弱势状态保留部署失败归因
- **WHEN** ETF beta sleeve 在 `TRANS_DOWN` 或 `RISK_OFF` 下未形成最终持仓
- **THEN** 运行产物 MUST 记录 deployability 保底是否触发
- **THEN** 运行产物 MUST 记录未部署的主原因码与资产池可交易性结论
