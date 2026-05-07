## ADDED Requirements

### Requirement: ETF 正式输出必须收敛为正式视图
当 `cn-etf-beta-sleeve` 运行在 Governed A 股正式主线时，系统 MUST 为 ETF 子系统提供一份正式输出视图。该正式视图 SHALL 只包含进入共享执行链和正式审计所必需的 ETF 真相，而 SHALL NOT 继续暴露研究诊断专用的中间预算、节奏、缺口与恢复解释字段。

#### Scenario: ETF 正式输出进入共享执行链
- **WHEN** ETF 子系统向共享执行链提交正式输出
- **THEN** 输出 MUST 只包含最终目标持仓、正式原因摘要和正式状态摘要
- **THEN** 输出 SHALL NOT 要求执行内核理解 `requested_budget`、`applied_budget`、`deployment_pace`、`strategic_floor_cap`、`tactical_overlay_cap` 或任意 gap 字段

#### Scenario: ETF 正式输出进入正式审计
- **WHEN** ETF 子系统的正式输出被正式审计层消费
- **THEN** 正式审计 MUST 只记录正式 ETF 摘要与正式原因字段
- **THEN** 正式审计 SHALL NOT 把 ETF 研究解释字段写回正式真相产物

### Requirement: ETF 研究诊断必须收敛为研究视图
当 ETF 子系统需要输出预算解释、节奏解释、恢复解释或缺口拆分时，系统 MUST 将这些信息收敛为 ETF 研究视图。该研究视图 SHALL 仅供研究诊断层消费，而 SHALL NOT 作为共享执行链或正式审计的正式输入。

#### Scenario: ETF 需要输出节奏与缺口解释
- **WHEN** ETF 子系统生成 `deployment_pace`、各类 gap、恢复路径或预算解释
- **THEN** 系统 MUST 将其归入 ETF 研究视图
- **THEN** 这些字段 SHALL NOT 被标记为 ETF 正式合同的一部分

#### Scenario: ETF 研究视图供 research audit 使用
- **WHEN** `research_audit` 需要解释 ETF 为什么没有完全部署或为什么出现恢复不足
- **THEN** `research_audit` MUST 从 ETF 研究视图消费证据
- **THEN** `research_audit` SHALL NOT 反向要求正式执行合同保留这些研究字段
