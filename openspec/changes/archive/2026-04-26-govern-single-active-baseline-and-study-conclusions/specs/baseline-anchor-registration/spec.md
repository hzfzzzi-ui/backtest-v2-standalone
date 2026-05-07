## ADDED Requirements

### Requirement: baseline 正式真相必须锚定 linked_exp
系统 MUST 将 `baseline.json.linked_exp_id` 对应实验定义为 baseline 的唯一正式真相来源。`index.json`、`latest_champion.json`、human digest 或其他展示层文件 SHALL NOT 反向充当 baseline 法源。

#### Scenario: linked_exp 可用时必须以其指标为准
- **WHEN** 某个 baseline 的 `baseline.json.linked_exp_id` 可解析到本地实验目录，且实验包含 `perf.json`
- **THEN** 系统 MUST 将该实验的 `perf.json` / `manifest.json.metrics` 作为 baseline 正式指标真相
- **THEN** `index.json` 或 `latest_champion.json` 若与之冲突，系统 MUST 将其视为展示层冲突，而不是 baseline 真相

#### Scenario: linked_exp 缺失时 baseline 不得继续作为正式对照
- **WHEN** 某个 baseline 的 `linked_exp_id` 缺失，或对应实验目录无法解析
- **THEN** 系统 SHALL NOT 将该 baseline 视为正式可复核对照
- **THEN** 系统 MUST 将其状态标记为非 active，并要求补齐法源后才能恢复正式使用

### Requirement: 同一生效时期只能存在一个 active baseline
系统 MUST 要求同一 `effective_period` 最多只存在一个 `active` baseline。其他 baseline MUST 明确降级为 `archived`、`superseded`、`invalid` 或 `replay_anchor`。

#### Scenario: 尝试在同一时期注册第二个 active baseline
- **WHEN** 某个生效时期已经存在一个 active baseline，系统又尝试注册第二个 active baseline
- **THEN** 系统 MUST 拒绝该注册
- **THEN** 系统 MUST 要求先降级旧 baseline，或明确结束旧 baseline 的生效时期

#### Scenario: 历史 baseline 保留追溯但不参与正式对照
- **WHEN** 某个 baseline 已被新的 active baseline 替代
- **THEN** 系统 MAY 保留其历史目录与报告
- **THEN** 该 baseline MUST 被标记为 `superseded` 或 `archived`
- **THEN** compare / 汇总 / 正式回归 SHALL NOT 默认再把它当 active baseline 使用

### Requirement: baseline 切换前必须人工确认
系统 MUST 在任何 active baseline 切换或 baseline apply 前，向用户明确报告候选 baseline、其个股腿绩效与 ETF/组合腿绩效，并取得人工确认。

#### Scenario: 未经确认不得 apply 新 active baseline
- **WHEN** 系统已经识别出一个候选 baseline，但尚未向用户确认
- **THEN** 系统 SHALL NOT 执行 active baseline 切换
- **THEN** 系统 MUST 先报告候选 baseline 的 `linked_exp_id`、法源指标、个股腿绩效与 ETF/组合腿绩效

#### Scenario: 用户确认后方可执行收敛
- **WHEN** 用户明确确认最终保留的 baseline
- **THEN** 系统 MAY 执行 active baseline 注册与其余 baseline 降级
- **THEN** 系统 MUST 保留被降级 baseline 的历史追溯信息
