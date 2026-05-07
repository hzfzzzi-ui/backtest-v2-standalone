## 概述

这条 change 只做一个最小行为试验：在账户层为 `TRANS_UP / TRANS_DOWN` 引入 `3` 天最短停留期。目标是减少过渡态抖动，而不修改趋势判断公式本身。

## 设计原则

1. 只在账户层做抗抖，不回到 ETF 局部实现
2. 保留原始证据状态用于诊断，不丢失 `5-state` 细粒度信息
3. 预算与执行只消费抗抖后的有效账户状态
4. 单改动可归因：只改最短停留，不同时引入确认条数、双阈值、组件共识等机制

## 实现方案

### 1. 账户层状态解析增加 min dwell

在 `resolve_account_state_from_evidence(...)` 中增加可选输入：

- `previous_account_state_run_days`
- `transient_min_dwell_days`

逻辑：

- 先按现有规则得到 `raw_state_5`
- 当 `previous_account_state_5` 属于 `TRANS_UP / TRANS_DOWN`
- 且 `previous_account_state_run_days < transient_min_dwell_days`
- 且 `raw_state_5 != previous_account_state_5`

则：

- `effective_state_5 = previous_account_state_5`
- `dwell_hold_applied = true`
- `suppressed_state_5 = raw_state_5`

否则：

- `effective_state_5 = raw_state_5`
- `dwell_hold_applied = false`

### 2. 主 runtime 维护 run length

在 `_build_account_budget_daily_frame(...)` 中维护：

- `previous_account_state`
- `previous_account_state_run_days`

当 `effective_state_5` 与前一日相同：
- `run_days += 1`

否则：
- `run_days = 1`

### 3. explain 输出

主 runtime 输出：

- `raw_state_5`
- `effective_state_5`
- `previous_account_state_run_days`
- `transient_min_dwell_days`
- `dwell_hold_applied`
- `suppressed_state_5`

## 验收方法

### 行为验收

比较改动前后：

- 账户层切换次数
- `1-2` 天短段数
- `<=5` 天短段数
- `A -> B -> A` bounce 次数

### 指标验收

比较主回放：

- `total_return`
- `cagr`
- `max_drawdown`
- `sharpe`
- `calmar`

### 成功标准

- 账户层短段和 bounce 明显下降
- 主指标不发生明显恶化

## 非目标

- 不修改趋势公式
- 不修改 ETF 局部状态机
- 不新增 `RISK_OFF` 专属 patch
- 不处理 `defensive -> recovery` 的额外确认条数
