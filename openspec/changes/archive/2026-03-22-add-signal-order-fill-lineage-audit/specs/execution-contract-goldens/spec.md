## ADDED Requirements

### Requirement: execution contract goldens 必须覆盖 lineage id 与生命周期终态
系统 MUST 在执行链 golden 覆盖集中加入 lineage 相关断言，至少校验代表性样本的 `signal_id`、`order_id`、`fill_id` 传播关系和生命周期终态。

#### Scenario: golden 校验稳定 lineage id
- **WHEN** 代表性路由执行 golden 测试
- **THEN** golden 结果 SHALL 能校验 `signal_id -> order_id -> fill_id` 的父子关系
- **THEN** 相同输入下 lineage id SHALL 保持稳定

#### Scenario: golden 校验生命周期终态
- **WHEN** golden 样本包含成交、取消、拒绝或失效等路径
- **THEN** golden 结果 SHALL 能校验对应终态与原因字段
- **THEN** 任一非预期状态漂移 SHALL 被判定为 contract 失败
