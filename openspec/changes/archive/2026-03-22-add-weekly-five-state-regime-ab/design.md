## Overview

这版候选替换方案的目标不是重做整套 regime framework，而是给 `ma200_legacy` 提供一个：

- 更贴近主线节奏
- 更容易人工检查
- 更低自由度

的周度五态状态机。

核心设计原则：

1. 只使用上证指数
2. 只使用 5 个明确指标
3. 只在周度观察点更新状态
4. 升级慢、降级快
5. 只改变市场过滤和风险预算，不改变个股信号逻辑

## Input Features

基准指数固定为上证指数 `000001.SH`。

日频输入：

- `close`
- `high`
- `low`

派生特征：

- `ma120`
- `ma120_slope_up = ma120[t] > ma120[t-20]`
- `ret60 = close / close[t-60] - 1`
- `ret120 = close / close[t-120] - 1`
- `adx20`

不允许引入：

- 成交量之外的宏观变量
- 额外广度变量
- 额外风格变量
- 未来信息

## Weekly Observation Model

状态只在周度观察点更新，默认取每周最后一个交易日。

周度原始分数：

- `close > ma120`：`+1`
- `ma120_slope_up`：`+1`
- `ret60 > 0`：`+1`
- `ret120 > 0`：`+1`
- `adx20 >= 25`：`+1`
- `20 <= adx20 < 25`：`0`
- `adx20 < 20`：`-1`

总分映射：

- `5` -> `BULL_MAIN`
- `4` -> `TURN_STRONG`
- `3` -> `LIGHT_TREND`
- `1~2` -> `TURN_WEAK`
- `<=0` -> `DEFENSIVE`

## Debounce Rules

为了和主线风控一致，状态机采用周度防抖：

- 升级：
  - 候选高一级或多级状态，必须连续 2 个周度观察点都成立
- 降级：
  - 只要 1 个周度观察点成立，立即生效

周度平滑后的状态再向前填充到下一周观察点之前的全部交易日。

## State to Trading Mapping

这次候选替换方案不复用旧的 `TREND_LIGHT -> EMA5/20` 分支。

原因：

- 用户要求不改个股信号逻辑
- 当前要做的是市场状态机 A/B，而不是主线壳重构

因此映射规则是：

- `BULL_MAIN` -> 允许开新仓，风险预算 `1.00`
- `TURN_STRONG` -> 允许开新仓，风险预算 `0.70`
- `LIGHT_TREND` -> 允许开新仓，风险预算 `0.40`
- `TURN_WEAK` -> 允许开新仓，风险预算 `0.15`（默认，可配置为 `0.10~0.20`）
- `DEFENSIVE` -> 禁止新开仓，风险预算 `0.00`

也就是说：

- 只有 `DEFENSIVE` 会强制 `NO_TRADE`
- 其他四档仍然走主线 `40日突破 + 40日个股残差动量排序`
- 差异只体现为风险预算缩放

## Router Contract

新增 `regime_engine.engine = weekly_five_state`。

当 engine = `weekly_five_state` 时：

- `market_state` 输出五档状态
- `trade_mode` 仅输出：
  - `TREND_MAIN`
  - `NO_TRADE`
- `risk_budget_multiplier` 由五态映射给出
- 个股层仍使用主线 breakout + residual 排序

当 engine = `ma200_legacy` 时：

- 保持现有行为不变

## Audit Outputs

为了支持 A/B 和前端检查，运行产物至少应输出：

- `market_state_5`
- `market_state_score`
- `market_state_raw`
- `market_state_smoothed`
- `risk_budget_multiplier`
- `weekly_observation_flag`
- `market_state_transition_reason`

## AB Experiment Design

最小 A/B 必须满足：

- 同一窗口
- 同一股票池
- 同一数据角色
- 同一个股信号逻辑
- 同一仓位与退出框架

唯一 intended diff：

- `regime_engine = ma200_legacy`
- vs `regime_engine = weekly_five_state`

推荐先用：

- `baseline_V10.2`
- `v2_canonical`
- `PIT_DYNAMIC`

## Risks

1. 周度观察可能让状态反应偏慢  
2. `TURN_WEAK` 仍允许开仓，可能带来拖尾亏损  
3. 只使用上证指数，可能对 CSI800 宽度代表性不足  
4. 新风险预算链如果实现不干净，会混淆为“状态改善”还是“预算变化”  

## Rollback

回退方式必须简单：

- 配置层把 `regime_engine.engine` 切回 `ma200_legacy`
- 不删除 legacy 状态机
- 前端保留旧实验加载兼容
