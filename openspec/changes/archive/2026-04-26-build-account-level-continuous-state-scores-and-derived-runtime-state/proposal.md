## Why

当前平台的市场状态仍以离散状态机和局部规则为主，研究逻辑、解释逻辑和运行逻辑耦合过紧，导致状态研究难以原生化、结果难以按分数层归因。现在需要先把账户层状态从“硬切状态”重构为“连续分数为主、离散状态为解释产物”的研究面，为后续 runtime 因子化接线建立稳定合同。

## What Changes

- 建立账户层连续状态分数目录，首版明确 `risk_on_score`、`recovery_score`、`defense_score` 的定义、字段、as-of 约束和解释边界。
- 建立账户层日频状态分数快照产物，支持原始值、标准化值、可用性和分数来源链路落盘。
- 建立由连续状态分数映射离散解释状态的研究合同，首版解释状态固定为 `BULL / TRANS_UP / TRANS_DOWN / RISK_OFF`。
- 提供账户层状态分数的单分数研究与多分数组合研究入口，不要求先跑完整策略。
- 明确这条 change 仅建立研究层真相与产物，不默认改写正式 runtime 预算、执行或主线状态消费逻辑。

## Capabilities

### New Capabilities
- `account-level-continuous-state-scores`: 定义账户层连续状态分数目录、字段合同和解释边界。
- `account-state-score-snapshots`: 定义账户层日频状态分数快照与离散解释状态快照产物。
- `account-state-score-study-surface`: 定义账户层状态分数的单分数与组合分数研究入口。

### Modified Capabilities
- 无

## Impact

- 受影响代码主要位于 `backend/research`、`research/studies`、`tests` 和后续会消费这些产物的 `backend/core`。
- 不新增外部依赖；首版优先复用现有研究 runner、产物目录和审计约束。
- 不改变当前正式主线回测口径，不直接修改账户预算与执行行为。
