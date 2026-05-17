## ADDED Requirements

### Requirement: baseline 重锚必须记录被接受的口径变更
当正式 baseline 因研究口径、数据口径或会计口径变更而重锚时，系统 MUST 在 baseline 注册记录或伴随迁移记录中说明被接受的口径变更、候选实验、旧锚点状态和验证命令。

#### Scenario: 接受 ETF 分红现金流新口径
- **WHEN** 操作方接受包含 ETF 显式分红现金事件的新候选实验作为正式 baseline
- **THEN** 新 active baseline MUST 指向新候选实验的 `linked_exp_id`
- **THEN** 旧 active baseline MUST 被标记为 `superseded`、`replay_anchor` 或等价的非 active 状态
- **THEN** baseline 迁移记录 MUST 说明这是 ETF 分红现金流口径变更，而不是策略参数优化

### Requirement: 新 baseline 激活后必须对自身通过回归门禁
baseline 重锚完成后，系统 MUST 使用新的 active baseline truth 重新执行 baseline regression；只有新候选实验对新的 compare truth 通过时，重锚才视为完成。

#### Scenario: 重锚后回归通过
- **WHEN** 新 baseline 已经注册为 active baseline
- **AND** baseline regression 在容器内重新执行
- **THEN** regression 结果 MUST 返回 `PASS`
- **THEN** 结果记录 MUST 指向新的 active baseline `linked_exp_id`

#### Scenario: 重锚后回归失败
- **WHEN** 新 baseline 注册后 baseline regression 仍返回 `FAIL`
- **THEN** 本次重锚 SHALL NOT 视为完成
- **THEN** 操作方 MUST 保留失败日志并回滚或继续排查 compare truth 不一致原因
