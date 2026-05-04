# A股ETF子系统接口模块定义

## 0. 定位

本文定义 A 股 ETF 子系统的正式接口边界，只描述当前主线如何接收共享层输入、生成正式动作意图并交给共享执行层。

本文不负责：
- 独立组合真相
- 独立执行核
- 非主实现说明
- 重构过程叙事

## 1. 子系统标识

- 正式名称：A 股 ETF 子系统
- 代码主标识：`cn_etf_beta`
- 当前正式角色：`strategic_beta_stabilizer`
- 当前正式频率：`monthly`

## 2. 输入合同

ETF 子系统只消费共享层给出的正式输入：
- `state_payload`
- `subsystem_budget_v1`
- `shared_data_bundle`
- `shared_feature_bundle`
- `execution_profile`

当 ETF 组件出现在统一组合装配链中时，assembly metadata 可以保留
`component_source_contract.components[*].compile_input` 作为来源说明。
但在真正进入 ETF runtime 之前，系统必须先把该来源说明解析为纯参数 `execution_contract`。
ETF runtime 不应直接依赖 `component_source_contract`、`baseline_id`、`study_id` 或其它来源字段。

## 3. 输出合同

ETF 子系统跨共享执行边界的正式输出为 `action_intent_v1`。

最小动作字段包括：
- `symbol`
- `side`
- `priority`
- `action_index`
- `reason_codes`
- `suggested_size_value`
- `suggested_size_unit`
- `suggested_size_basis`

## 4. 约束

- `BUY` 只允许 `weight + subsystem_budget_relative`
- `SELL` 只允许 `ratio + sellable_qty_relative`
- ETF 子系统不直接输出订单或成交结果
