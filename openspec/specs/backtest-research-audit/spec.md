# backtest-research-audit Specification

## Purpose

定义正式 research-audit 层，包括统一审计状态、gate 汇总、target-contract drift 证据，以及 baseline 法源声明。

## Requirements

### Requirement: every experiment MUST emit a unified research audit

每次实验 SHALL 将 `research_audit` 写入 `audit.json`。系统 SHALL NOT 为同一次运行再额外产出独立的 `research_audit.json`。

#### Scenario: emit research audit

- **WHEN** 实验完成 artifact stabilization
- **THEN** `audit.json` MUST 包含 `research_audit.contract_version`
- **THEN** `audit.json` MUST 包含 `research_audit.overall_status`
- **THEN** `audit.json` MUST 包含 `research_audit.gates`

### Requirement: overall research audit status MUST be derived from gates

审计层 SHALL 使用稳定优先级从 gate 状态推导唯一的 `overall_status`。

#### Scenario: failure dominates

- **WHEN** 任一 gate 为 `FAIL`
- **THEN** `research_audit.overall_status` MUST 为 `FAIL`

#### Scenario: warning dominates non-fail states

- **WHEN** 没有 `FAIL` 且至少一个 gate 为 `WARN`
- **THEN** `research_audit.overall_status` MUST 为 `WARN`

#### Scenario: unknown dominates pass-only states

- **WHEN** 没有 `FAIL` 或 `WARN` 且至少一个 gate 为 `UNKNOWN`
- **THEN** `research_audit.overall_status` MUST 为 `UNKNOWN`

#### Scenario: full pass

- **WHEN** 所有 gate 都为 `PASS`
- **THEN** `research_audit.overall_status` MUST 为 `PASS`

### Requirement: audit MUST classify target-contract drift with explicit evidence

当 ETF standalone 或其他正式路径在订单、日频产物或 summary 之间暴露出不一致的 final target semantics 时，审计层 MUST 将其标记为 target-contract drift，并保留冲突证据。审计 MUST 区分 final target semantics 和 deploy-gap semantics。

#### Scenario: conflicting final target semantics

- **WHEN** 同一决策日的 formal artifacts 出现冲突的 `final_target_weight` 或等价字段
- **THEN** `research_audit` MUST 标记 target-contract drift failure
- **THEN** 审计 MUST 包含冲突 artifact、字段和值

#### Scenario: deploy-gap is not misclassified as drift

- **WHEN** standalone deploy 的 `target_weight` 只是 incremental deploy gap，而 `final_target_weight` 仍然一致
- **THEN** 审计 SHALL NOT 将其误判为 drift

### Requirement: research audit MUST declare baseline source of truth explicitly

任何 baseline compare 或 research audit MUST 显式声明 baseline 的 source-of-truth。若 baseline 存在 `baseline.json.linked_exp_id`，则 research compare 与 audit MUST 以该 linked experiment 作为唯一正式 baseline 法源。

#### Scenario: display-layer metrics conflict with linked experiment

- **WHEN** `index.json`、`latest_champion.json` 或其他展示层指标与 `baseline.json.linked_exp_id` 对应实验不一致
- **THEN** compare 或 audit MUST 标记 baseline source-of-truth conflict
- **THEN** 输出 MUST 明确指出 canonical source 是 linked experiment，而不是展示层数值

#### Scenario: linked experiment is missing

- **WHEN** baseline 的 `linked_exp_id` 缺失，或对应实验目录不可解析
- **THEN** compare 或 audit MUST 将该 baseline 标记为不可 fully reproduce
- **THEN** 相关研究结论 SHALL NOT 被解释为对 formal baseline 的可靠比较
