## 概述

这条 change 做一件事：把 `LIGHT` 从正式运行状态中移除，并把系统正式收成 4-state runtime。目标不是改策略收益，而是清掉死状态和解释噪音，提升状态机可信度。

## 设计原则

1. 兼容优先：保留 `LIGHT` 作为历史输入别名，但不再作为正式输出状态
2. 主真相统一：账户层、状态机、ETF 正式映射统一收成 4-state
3. 最小行为漂移：`LIGHT` 一律映射到 `TRANS_UP`，避免引入新的防守语义
4. 解释收口：前端、审计、query 不再把 `LIGHT` 当成正式状态展示

## 实现方案

### 1. 账户层与主状态机

- `LIGHT` 历史别名统一映射到 `TRANS_UP`
- `TREND_LIGHT` 统一映射到 `TRANS_UP`
- 账户层 budget map 删除 `LIGHT`
- 状态解析优先级和 fallback 删除 `LIGHT`

### 2. ETF 正式映射

- ETF canonical state 别名把 `LIGHT` 映射到 `TRANS_UP`
- 依赖正式状态集合的模板、bucket split、equity weights 删除 `LIGHT`
- 原先 `LIGHT` 行为一律并入 `TRANS_UP`

### 3. 输出与解释

- runtime 输出不再把 `LIGHT` 当成正式有效状态
- query/front-end/audit 只承认 4-state
- 历史产物中的 `LIGHT` 作为兼容输入读取，不作为新产物正式输出

## 验收方法

1. 主回放能正常运行
2. 新产物 `run_meta / portfolio_daily / surface` 不再出现正式 `LIGHT`
3. 指标不发生无意义漂移
4. 最小正式回归通过

## 非目标

- 不重写状态机公式
- 不同时做新的抗抖逻辑
- 不修改 ETF/个股腿研究逻辑
- 不处理历史 outputs 回填
