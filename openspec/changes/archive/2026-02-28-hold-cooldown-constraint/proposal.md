## Why

EMA/SMA 均线交叉策略在震荡行情中频繁产生金叉/死叉信号，导致引擎对同一标的反复开平仓。每次交易都消耗佣金 + 印花税 + 滑点，积累起来严重侵蚀收益。当前引擎只有 T+1 延迟（信号次日成交），没有"最短持有"和"卖出后冷却"机制来抑制短周期噪声交易。

## What Changes

- **引擎新增 min_hold_days**：持仓不满 N 天时，仅 `SMA_CROSS_DOWN` 卖出信号被阻断；风控退出（ATR_STOP_LOSS、ATR_TRAIL_EXIT、RISK_OFF_EXIT、TREND_BREAK_EXIT）不受约束
- **引擎新增 cooldown_days**：个股仓位清零后 M 天内禁止买回同一标的；部分减仓不触发冷却
- **引擎新增状态追踪**：`entry_day: dict[str, date]`（BUY 成交日）、`last_sell_day: dict[str, date]`（清仓成交日）
- **诊断计数器**：`BLOCK_MIN_HOLD`、`BLOCK_COOLDOWN` reason_code 与对应 metrics
- **前端 UI**：退出规则面板新增"持仓约束"分组，含 min_hold_days、cooldown_days 输入、min_hold 例外原因多选
- **参数映射**：`backtest_v2.py _build_runtime_cfg_from_workbench()` 新增 hold_constraint 字段映射到 strategy.params

## Capabilities

### New Capabilities

- `hold-cooldown-constraint`: 最短持有天数 + 个股卖出冷却期，含引擎逻辑、策略参数、前端 UI、参数映射、诊断输出

### Modified Capabilities

（无）

## Impact

| 文件 | 变更 |
|------|------|
| `backend/core/strategies/ema_cross.py` | 新增 min_hold_days / cooldown_days / min_hold_exempt_reasons 字段 |
| `backend/core/strategies/sma_cross.py` | 同上（SMA 策略同样支持） |
| `backend/core/strategies/registry.py` | 从 params 读取并传入策略构造 |
| `backend/core/engine_vector/portfolio_simulator_strict.py` | 新增 entry_day / last_sell_day 状态，SELL/BUY 过滤逻辑，计数器 |
| `backend/api/endpoints/backtest_v2.py` | hold_constraint 参数映射 |
| `frontend/index.html` | 退出规则面板新增持仓约束 UI |
| `frontend/assets/js/backtest_v2.js` | buildConfigDraft / 事件绑定 / hydration / 诊断展示 |
