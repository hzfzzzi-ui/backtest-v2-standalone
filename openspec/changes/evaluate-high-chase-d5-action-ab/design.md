## Context

V3 已有 D5 三日 MFE/MAE runtime AB，但全量 D5 immediate 半卖在全周期收益上明显拖累。最新 High Chase shadow audit 进一步说明：追高本身不是稳定亏损主因，盈利 TOP30 也大量来自追高；更有解释力的是“高追后 day3 确认失败”。

本次设计只研究这个组合条件的处理动作，不修改股票池、ETF 腿、排序、入场主逻辑或成交时点。

## Goals / Non-Goals

**Goals:**

- 在真实 runtime 中验证 High Chase + D5 failure 是否比全量 D5 更有用。
- 将三类动作拆开：立刻半卖、watch 后 day10 半卖、延迟到 day5 再确认半卖。
- 保持所有新增参数默认关闭。
- 用同一份 V3 stock runtime config 做 same-window 对照。
- 保留机器可读的 reason/meta，方便后续按触发次数、交易、收益和回撤归因。

**Non-Goals:**

- 不把 high_chase 作为硬禁买规则。
- 不做买入延迟状态机；本轮“延迟确认”指卖出确认从 day3 延迟到 day5。
- 不使用行业、主题、大盘指数或未来样本动态调参。
- 不推广 baseline。

## Decisions

### 1. High Chase 标签在 runtime 内即时计算

使用 entry 之前的可观测价格和 breakout meta 矩阵计算 high chase，不读取 shadow CSV，也不读取输出产物。

计算口径：

- `short_heat`: 5/10/20 日入场前涨幅超过配置阈值之一。
- `extension_heat`: close 相对 MA20/MA60 或 ATR extension 超过配置阈值之一。
- `breakout_stretch`: breakout margin 或 open gap 超过配置阈值之一。
- `high_chase`: 上述三类至少命中 `mfe_mae_high_chase_min_core_flags` 类。
- `weak_breakout_quality`: 只作为 meta/audit，不作为 high_chase 必要条件。

阈值通过 runtime 参数注入，研究配置固定，不在同一轮根据结果二次调参。

### 2. D5 增加 scope 和 action，而不是新增独立 exit 引擎

复用现有 `evaluate_mfe_mae_confirmation_exits`，新增：

- `mfe_mae_confirmation_scope`: `all | high_chase`
- `mfe_mae_confirmation_action`: `exit | watch_day10`
- watch review 参数：review bars、修复 MFE、当前收益、MAE 条件。

这样可以保持 exit 优先级、order planning、fill accounting、cash、positions、NAV 都继续走同一条 runtime ledger。

### 3. 三个 AB 变体只改变 High Chase + D5 参数

- `HC_D5_IMMEDIATE_HALF_EXIT`: scope=high_chase，day3 失败直接半卖。
- `HC_D5_WATCH_DAY10_HALF_EXIT`: scope=high_chase，day3 失败进入 watch；day10 仍未修复再半卖。若 day3 MAE 深于 `-8%`，可按配置直接半卖，避免放任严重失败。
- `HC_D5_DELAYED_5D_HALF_EXIT`: scope=high_chase，lookahead=5，仍按同一 MFE/MAE 失败条件半卖。

保留 `B0_V3_STOCK_REPLAY` 和 `D5_ALL_3D_IMMEDIATE_HALF_EXIT` 做定位对照。

## Risks / Trade-offs

- [Risk] High Chase 阈值来自 shadow audit 方向，存在过拟合风险。  
  Mitigation: 标记为 research-only；结论不得直接推广；后续若有效必须做 rolling/live-safe threshold 版本。

- [Risk] partial sell 可能降低回撤但损害趋势票收益。  
  Mitigation: 必须同时比较总收益、CAGR、Sharpe、MaxDD、交易数、触发交易归因和 TOP30 损伤。

- [Risk] watch 状态如果不清理可能重复卖出。  
  Mitigation: watch state 在 full exit、review exit、修复取消时清理；partial watch exit 也主动清理。

- [Risk] 延迟确认和 watch 都可能错过早期减损。  
  Mitigation: 与 immediate 变体同窗比较，而不是只看 B0。
