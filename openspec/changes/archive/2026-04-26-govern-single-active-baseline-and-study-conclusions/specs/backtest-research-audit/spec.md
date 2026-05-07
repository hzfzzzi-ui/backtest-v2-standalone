## ADDED Requirements

### Requirement: research audit 必须显式声明 baseline 真相来源
系统 MUST 在研究审计中显式声明 compare 所使用的 baseline 真相来源。若 baseline 存在 `baseline.json.linked_exp_id`，research audit MUST 以该 linked experiment 作为唯一正式 baseline source-of-truth。

#### Scenario: baseline 展示层与法源层冲突
- **WHEN** `index.json`、`latest_champion.json` 或其他展示层指标与 `baseline.json.linked_exp_id` 对应实验指标不一致
- **THEN** `research_audit` MUST 标记 baseline source-of-truth conflict
- **THEN** 审计 MUST 明确指出法源 baseline 是 linked experiment，而不是展示层数值

#### Scenario: baseline 法源缺失
- **WHEN** baseline 的 `linked_exp_id` 缺失，或对应实验目录不可解析
- **THEN** `research_audit` MUST 将该 baseline 标记为不可复核
- **THEN** 与其相关的研究结论 SHALL NOT 被解释为对正式 baseline 的可靠比较结论
