# 共享层接口模块定义

## 0. 定位

本文定义 A 股主线共享层的正式接口合同。
共享层负责把执行合同、组合预算、风险覆盖与执行记账接成一条稳定链路。

## 1. 当前正式对象

共享层正式承载的对象有：
- `execution_contract`
- `subsystem_budget_v1`
- `action_intent_v1`
- `risk_override_v1`
- `target_book_v1`
- `execution_audit`

## 2. 合同分层

### 2.1 唯一执行合同

`execution_contract` 是回测实验与 unified combo 的唯一正式执行合同。
它只负责描述会改变回测行为的纯参数，例如：
- 资产范围
- 时间区间
- benchmark / regime
- 信号生成
- 排序
- 仓位与预算规则
- 执行与成本
- 退出规则
- 组合策略参数

### 2.2 非执行合同对象

以下对象不属于正式执行合同：
- `component_source_contract`
- `component_experiments`
- `baseline_id`
- `study_id`
- `window_key`
- `variant_name`
- `linked_exp_id`
- `comboTruth`

它们只可用于：
- 组装配置
- 来源追溯
- 审计说明
- 前端展示

它们不得直接驱动执行。

## 3. 正式调用链

`execution_contract -> subsystem_budget_v1 -> action_intent_v1 -> risk_override_v1 -> execution_kernel -> target_book_v1 + execution_audit`

其中：
- 上游编译结果必须先收口为 `execution_contract`
- 子系统正式意图由 `action_intent_v1` 提供
- Governor 的正式覆盖由 `risk_override_v1` 提供
- `execution_kernel` 只消费正式执行合同，不消费 provenance / reference 字段

## 4. 对外边界

共享层对外只输出正式合同与正式执行结果，不输出研究旁路字段作为执行真相：
- 不输出子系统私有模板作为正式执行输入
- 不输出历史兼容字段作为正式运行边界
- 不输出 provenance / reference 字段作为执行分支条件

## 5. 保留原则

共享层保留的只有当前正式执行语义。
来源叙事、回放锚点和历史兼容字段可以保留在 provenance 区，但不得继续扩张到执行合同中。
