## ADDED Requirements

### Requirement: research audit 必须将 TRANS_UP 解释为单 seat core recovery
当实验属于 Governed A 股主线，且 formal ETF stabilizer 当前有效状态为 `TRANS_UP` 时，`research_audit` MUST 将该状态解释为 `single-seat core recovery`。审计 MUST 能明确区分“合同上不存在独立 overlay”与“合同存在 overlay 但执行漏损”，并 SHALL NOT 继续把 `TRANS_UP` 的第二个风险 seat 缺失表述为部署失败。

#### Scenario: TRANS_UP 审计解释为单 seat 恢复
- **WHEN** formal ETF stabilizer 在 `TRANS_UP` 下生成日级或实验级审计输出
- **THEN** 审计 MUST 明确表明当前 live 合同是单 seat core recovery
- **THEN** 审计 SHALL NOT 把缺失的 `tactical_satellite` second seat 解释成执行漏损

#### Scenario: TRANS_UP 的纸面 overlay 痕迹不得被审计成批准预算
- **WHEN** 历史字段、模板预算或兼容性元数据中仍出现 `tactical_overlay` 痕迹
- **THEN** 审计 MUST 将其解释为历史/兼容性证据，而不是当前 live 合同中的独立风险预算
- **THEN** 审计 MUST 以正式单 seat 合同作为 `TRANS_UP` 的解释真相
