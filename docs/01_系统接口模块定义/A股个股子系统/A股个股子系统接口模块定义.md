# A股个股子系统接口模块定义

## 0. 定位

本文定义 A 股个股子系统的正式接口边界，只描述当前主线如何接收共享层输入、生成正式动作意图并交给共享执行层。

本文不负责：
- 独立组合真相
- 独立执行核
- 研究历史叙事
- 非主实现说明

## 1. 子系统职责

A 股个股子系统负责：
- 生成个股层正式信号
- 在共享预算内形成可执行动作
- 输出 `action_intent_v1`

## 2. 输入合同

个股子系统只消费共享层给出的正式输入：
- `state_payload`
- `subsystem_budget_v1`
- `shared_data_bundle`
- `shared_feature_bundle`
- `execution_profile`

它不应自建第二套正式输入合同。

## 3. 输出合同

个股子系统跨共享执行边界的正式输出为 `action_intent_v1`。

最小字段包括：
- `contract_version`
- `as_of_date`
- `owner_system`
- `actions[]`

`actions[]` 中每条动作至少包含：
- `symbol`
- `side`
- `priority`
- `action_index`
- `reason_codes`
- `suggested_size_value`
- `suggested_size_unit`
- `suggested_size_basis`