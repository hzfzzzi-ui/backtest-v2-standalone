## MODIFIED Requirements

### Requirement: `SOURCE_ONLY` MUST 继续作为正式持仓归属规则
系统 MUST 继续采用 `SOURCE_ONLY` 作为正式持仓归属规则。普通 `SELL` 只能卖自己来源的仓位；只有 Governor 的风险覆盖才可以跨来源强平。

#### Scenario: 普通卖出尝试卖出他人来源仓位
- **WHEN** 某个子系统发出普通 `SELL intent`，目标仓位不属于该来源
- **THEN** 系统 MUST 拒绝该动作并写入 `execution_audit`
- **THEN** 该动作 SHALL NOT 被默默改写为跨来源卖出
