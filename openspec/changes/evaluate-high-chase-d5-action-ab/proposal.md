## Why

High Chase shadow audit 显示，追高本身不能区分盈利 TOP30 和亏损 TOP30；但“高追 + 买入后三日 D5 确认失败”明显更集中在亏损侧。需要把这个组合条件放进真实 runtime AB，而不是继续用事后 shadow 判断。

## What Changes

- 新增一个研究-only runtime AB：`cn_stock_etf_high_chase_d5_action_ab_v1`。
- 在现有 D5 MFE/MAE 确认失败逻辑上增加可选 scope：
  - `all`：保持现有 D5 行为。
  - `high_chase`：只有入场属于 high chase 时，D5 失败处理才生效。
- 新增三类可归因变体：
  - `HC_D5_IMMEDIATE_HALF_EXIT`：高追且 day3 D5 失败时立刻半卖。
  - `HC_D5_WATCH_DAY10_HALF_EXIT`：高追且 day3 D5 失败时进入 watch；day10 仍未修复再半卖。
  - `HC_D5_DELAYED_5D_HALF_EXIT`：高追后不在 day3 处理，延迟到 day5 再确认失败并半卖。
- 保留 B0 V3 replay 和既有 D5 all-scope immediate 作为对照。
- 所有新增参数默认关闭，不改变正式 V3 baseline。

## Capabilities

### New Capabilities
- `high-chase-d5-action-ab`: 研究-only 的 High Chase + D5 失败 runtime AB 合同，覆盖高追识别、D5 scope、降仓/watch/延迟确认三类动作和 same-window 审计要求。

### Modified Capabilities
- `cn-stock-trend-alpha-core`: 增加默认关闭的高追 D5 scope/action runtime 参数；默认行为必须保持不变。
- `study-definition-runner`: 增加新的 declarative study 定义，要求同一 runtime source 下只 patch High Chase + D5 参数。

## Impact

- 影响源码：
  - `backend/core/strategies/breakout_trend.py`
  - `backend/core/strategies/registry.py`
  - `backend/core/engine_vector/breakout_provider_models.py`
  - `backend/core/engine_vector/breakout_signal_provider.py`
  - `backend/core/engine_vector/breakout_provider_day_signals.py`
  - `backend/core/engine_vector/multi_alpha_signal_provider.py`
  - `research/studies/cn_stock_etf/*.study.yaml`
  - `tests/unit/*`
- 影响产物：
  - 新实验输出写入 `outputs/experiments`
  - 新 study/journal 输出写入 `outputs/studies` 和 `research/study_journal`
- 不改变：
  - stock universe / PIT membership
  - ETF leg
  - 排序主因子
  - 入场规则
  - 成交时点
  - 成本模型
  - baseline 默认配置
