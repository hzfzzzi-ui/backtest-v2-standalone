# cn-etf-beta-sleeve Specification

## Purpose

Define the formal ETF beta sleeve boundary for the A-share governed mainline, including Phase 1 scope, executable BUY deployment, and standalone target semantics.
## Requirements
### Requirement: the ETF beta sleeve MUST remain a governed standalone sleeve

The system SHALL expose `cn-etf-beta-sleeve` as a governed sleeve under the A-share mainline. It is a low-frequency, explainable beta sleeve rather than a second stock-style alpha engine.

#### Scenario: ETF sleeve runs under governor budget
- **WHEN** the ETF beta sleeve is enabled
- **THEN** it is treated as a sleeve independent from stock alpha logic
- **THEN** it runs within governor-issued budget and execution constraints

### Requirement: Phase 1 ETF scope MUST stay bounded

Phase 1 SHALL treat only the formal core beta ETF set as in-scope, with limited defense candidates explicitly bounded by contract.

#### Scenario: only formal Phase 1 symbols are treated as formal core beta
- **WHEN** the system builds the formal Phase 1 ETF candidate set
- **THEN** only formal in-scope symbols are treated as core beta truth
- **THEN** out-of-scope ETF symbols are not silently upgraded into the formal sleeve

### Requirement: ETF BUY orders MUST be executable under fill-equivalent affordability

ETF standalone deploy BUY orders SHALL satisfy the same affordability semantics used by the fill stage. Orders that exceed affordable cash MUST be clipped or rejected during planning rather than allowed to fail one day later for the same reason.

#### Scenario: planning-stage BUY affordability matches fill semantics
- **WHEN** the ETF sleeve generates standalone deploy BUY orders
- **THEN** planning uses fill-equivalent cost semantics and lot constraints
- **THEN** the scheduled order set contains only affordable BUY orders

### Requirement: ETF standalone deploy MUST expose final and delta target semantics separately

The standalone inter-rebalance deploy path SHALL preserve both `final_target_weight` and `target_weight`. `final_target_weight` is the final portfolio target, while `target_weight` is the deploy-gap increment for the current order path.

#### Scenario: existing holdings require only incremental deploy gap
- **WHEN** a selected ETF already has existing exposure
- **THEN** emitted BUY orders may have `target_weight` smaller than `final_target_weight`
- **THEN** both values remain available for downstream audit and artifact alignment

### Requirement: partial fallback fill MUST preserve zero-original fallback target semantics

When original target symbols still exist, fallback symbols with zero original target SHALL keep both `target_weight` and `final_target_weight` at `0.0`. Postprocess and fallback sizing SHALL NOT silently assign them positive target semantics.

#### Scenario: partial fallback does not create false positive target weight
- **WHEN** original target symbols still remain in the selected set
- **THEN** zero-original fallback symbols keep `target_weight = 0.0`
- **THEN** zero-original fallback symbols keep `final_target_weight = 0.0`

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

### Requirement: ETF beta sleeve 弱势状态必须允许非再平衡日防守补位
当 ETF beta sleeve 处于 `TRANS_DOWN` 或 `RISK_OFF`，且正式 weak-state defense policy 已激活时，如果当前 live seats 未满足正式 defense posture，系统 MUST 允许通过 inter-rebalance defense redeploy 进入防守部署。该路径 SHALL NOT 改变 `BULL / TRANS_UP` 的固定再平衡节奏。

#### Scenario: 弱势状态绕过固定 biweekly 等待进入防守部署
- **WHEN** ETF beta sleeve 运行于非再平衡日
- **AND** `effective_state_5` 属于 `TRANS_DOWN` 或 `RISK_OFF`
- **AND** 当前 live seats 未满足正式 defense posture
- **THEN** 系统 MUST 允许 inter-rebalance defense redeploy
- **THEN** 系统 SHALL NOT 仅因 `AWAIT_BIWEEKLY_REBALANCE` 而放弃该弱势防守部署

### Requirement: ETF beta sleeve 弱势 inter-rebalance 路径必须保持正式边界
ETF beta sleeve 的 weak-state inter-rebalance defense redeploy MUST 只使用正式弱势防守合同生成的目标集合。系统 SHALL NOT 在该路径中回退到普通进攻 ranking，也 SHALL NOT 借机修改 stock sleeve、regime 或 combo 主结构。

#### Scenario: 非再平衡日 weak-state redeploy 只使用 formal defense targets
- **WHEN** weak-state inter-rebalance defense redeploy 被激活
- **THEN** 选中结果 MUST 来自 formal weak-state defense targets
- **THEN** 运行 explain surface MUST 能区分该路径与常规再平衡路径

### Requirement: ETF beta sleeve 弱势目标必须采用债为主、核心宽基为辅的正式映射

在当前主线中，ETF beta sleeve 的弱势目标映射 MUST 采用“债为主、核心宽基为辅”的正式结构，而不是纯防守空仓化语义。

#### Scenario: `RISK_OFF` 使用低风险累积结构

- **WHEN** `effective_state_5 = RISK_OFF`
- **THEN** 正式 active target 以 `511010.SH` 为主
- **THEN** 系统允许少量 `510300.SH` 作为核心宽基累积

#### Scenario: `TRANS_DOWN` 使用债为主的过渡结构

- **WHEN** `effective_state_5 = TRANS_DOWN`
- **THEN** 正式 active target 仍以债为主
- **THEN** 系统允许有限核心宽基暴露作为过渡累积

### Requirement: ETF beta sleeve 必须支持 `RISK_OFF` cash-drip top-up

当 `RISK_OFF` 已激活正式弱势目标且存在目标缺口时，系统 MUST 允许 ETF beta sleeve 在非再平衡日进入小额、可解释的 `cash-drip top-up` 路径。该路径以债优先、核心宽基次之，不要求一次补满完整 deploy gap。

#### Scenario: 现金足够一手时执行 drip top-up

- **WHEN** `effective_state_5 = RISK_OFF`
- **AND** 当前存在目标缺口
- **AND** 现金足够买入最小可执行单位
- **THEN** 系统允许执行一次 `cash-drip top-up`
- **THEN** 顺序优先补债，其次才补核心宽基

#### Scenario: 现金不足最小单位时保留明确拒绝原因

- **WHEN** `effective_state_5 = RISK_OFF`
- **AND** 当前存在目标缺口
- **AND** 现金不足最小可执行单位
- **THEN** 运行产物 MUST 给出 `cash too small` 类拒绝原因
- **THEN** 系统 SHALL NOT 退回到笼统的 `execution constraint` 解释

### Requirement: ETF beta sleeve 在账户层主真相下只能作为 transition execution adapter

当 `runtime_truth_source = account_allocator` 时，ETF beta sleeve MUST 作为共享账户执行 runtime 的资产执行 adapter。旧 weak-state 路径可以继续产出研究与排障信息，但 SHALL NOT 再作为账户层 transition execution 的主 owner。

#### Scenario: 账户层 owner 存在时旧 weak-state 路径降级
- **WHEN** 账户层共享执行 runtime 已输出 transition execution owner
- **THEN** `state_edge_cash_release`、`riskoff_cash_drip_topup`、`riskoff_account_budget_materialization`、`weak_state_inter_rebalance_defense_redeploy` 只允许写入 diagnostics/reference
- **THEN** ETF beta sleeve SHALL NOT 再用这些旧路径输出主执行结论或主 reject reason
