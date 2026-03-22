## Why

当前主线 `baseline_V10.2` 仍然依赖 `ma200_legacy` 作为市场过滤主入口。这个过滤器简单、可解释，但它本质上只是 `close vs MA200 + slope` 的简化价格过滤器，和主线的 `40日突破 + 40日个股残差动量排序` 在节奏上并不完全匹配。

当前问题不是要引入复杂宏观模型，而是要提供一版：

- 简单
- 可解释
- 低自由度
- 只使用上证指数价格与 ADX
- 能直接映射到主线风险预算

的新状态机，作为 `ma200_legacy` 的候选替换方案，并在不改个股信号逻辑的前提下做最小 A/B。

## What Changes

- 新增一个候选 regime engine：`weekly_five_state`
- 只使用以下输入：
  - `close > MA120`
  - `MA120_today > MA120_20d_ago`
  - `60d return > 0`
  - `120d return > 0`
  - `ADX(20)` 作为环境修正
- 采用固定打分：
  - `close > MA120`：`+1`
  - `MA120 slope > 0`：`+1`
  - `60d return > 0`：`+1`
  - `120d return > 0`：`+1`
  - `ADX >= 25`：`+1`
  - `20 <= ADX < 25`：`0`
  - `ADX < 20`：`-1`
- 采用五档状态：
  - `BULL_MAIN`
  - `TURN_STRONG`
  - `LIGHT_TREND`
  - `TURN_WEAK`
  - `DEFENSIVE`
- 采用周度观察与防抖：
  - 升级需要连续 2 个周度观察点确认
  - 降级只需 1 个周度观察点
- 只把状态机用于：
  - 市场状态输出
  - 风险预算输出
  - 是否允许开新仓
- 不改 `V10.2` 的个股信号逻辑：
  - 仍是 `40日突破 + 40日个股残差动量排序`
- 新状态机默认保持 `shadow / opt-in`
- 必须提供与 `ma200_legacy` 的最小 A/B 实验

## Capabilities

### New Capabilities

- `weekly-five-state-regime-engine`

### Modified Capabilities

- `ma200-market-state`
- `regime-router`
- `risk-budget-sizing`
- `market-state-chart-overlay`
- `regime-signal-ui`

## Impact

- 后端：
  - `backend/core/engine_vector/regime_router_precompute.py`
  - `backend/core/engine_vector/regime_router_signal_provider.py`
  - `backend/core/config/*`
  - 相关运行时配置编译链
- 前端：
  - 结果图阶段蒙版
  - regime 配置面板
  - A/B 实验加载与标签
- 研究与审计：
  - 新增 weekly five-state 对照实验
  - 输出状态、分数、风险预算和切换原因

## Non-Goals

- 不引入宏观变量
- 不引入机器学习 / HMM / 聚类
- 不改个股选股逻辑
- 不把新状态机直接切成默认主线
