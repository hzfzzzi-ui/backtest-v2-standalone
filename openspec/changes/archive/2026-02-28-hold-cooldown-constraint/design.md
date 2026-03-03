## Context

VECTOR 引擎（SMA 路径，`portfolio_simulator_strict.py` line 297–950）当前用 4 个 dict 追踪持仓状态：`positions`、`position_avg_cost`、`peak_close_state`、`break_streak_state`。没有记录入场日期或上次卖出日期，因此无法实现最短持有或冷却期。

T+1 模型：信号日 Day N → `pending[Day N+1]` → Day N+1 开盘成交。entry_day 和 last_sell_day 均应记录**成交日**。

## Goals / Non-Goals

**Goals:**
- 引擎支持 min_hold_days（SELL 侧约束）和 cooldown_days（BUY 侧个股冷却）
- 风控退出（ATR_STOP / ATR_TRAIL / RISK_OFF / TREND_BREAK）豁免 min_hold 检查
- 诊断计数器 + 前端 UI 完整贯通
- SMA 和 EMA 策略共用同一机制

**Non-Goals:**
- 不实现全局级冷却（卖出任意标的后暂停所有买入）
- 不修改 generic_signals 路径（line 953+），仅 SMA 路径
- 不实现 min_hold_exempt_reasons 的前端多选 UI（本期硬编码默认 4 种豁免，后续可扩展）

## Decisions

### D1: 新增两个状态 dict

```python
entry_day: dict[str, date] = {}       # sym → BUY 成交日
last_sell_day: dict[str, date] = {}   # sym → 清仓成交日
```

- `entry_day[sym]` 在 BUY 成交时写入（pending 填充阶段，line 393 附近）
- `entry_day[sym]` 在 SELL 清仓成交时 pop（line 358-363 附近，与其他状态同步清理）
- `last_sell_day[sym]` 仅在 SELL 后 `positions[sym] <= 0` 时写入

### D2: min_hold 检查位置 — SELL 信号生成循环

在 held-only SELL 循环（line 490 `for c in held_cols`）中，计算 `held_days = (day - entry_day.get(sym, day)).days`。当 `held_days < min_hold_days` 时：
- 若 `reason in exempt_set` → 正常生成 sell_sig
- 否则 → skip，计数器 +1

这比在 pending 填充阶段检查更好：**在信号决策阶段就阻断**，不生成无效订单。

### D3: cooldown 检查位置 — BUY 候选循环

在 `for c in day_cands` 循环（line 596）中，已有 `if sym in positions` 持仓检查。在其后追加冷却检查：
```python
if cooldown_days > 0 and sym in last_sell_day:
    if (day - last_sell_day[sym]).days < cooldown_days:
        cooldown_block_count += 1
        continue
```

### D4: 豁免原因默认硬编码

```python
DEFAULT_MIN_HOLD_EXEMPT = {"RISK_OFF_EXIT", "TREND_BREAK_EXIT", "ATR_STOP_LOSS", "ATR_TRAIL_EXIT"}
```

策略字段 `min_hold_exempt_reasons: list[str]` 存在但前端本期不暴露多选 UI，使用默认值。后续可扩展。

### D5: 前端放置位置

退出规则面板 → 退出优先级之前（line 392 `<hr>` 之前），新增 `<div>` 分组"持仓约束"。包含：
- `wbMinHoldDays`: number input, min=0, max=15, default=0
- `wbCooldownDays`: number input, min=0, max=30, default=0

## Risks / Trade-offs

- **风险**：`entry_day` 用自然日（`date` 对象的 `.days` 差），不是交易日。若中间有长假（国庆 7 天），实际只过了 2 个交易日但 held_days 算 7。→ **缓解**：可接受——min_hold 本意是"时间冷静期"而非"交易日数"，且 A 股长假不频繁。后续可改用交易日索引差。
- **风险**：SMA 路径和 generic_signals 路径需要分别实现。本期只做 SMA 路径。→ **缓解**：当前前端只走 SMA 路径（EMA_CROSS 也走 SMA 路径的 `build_signal_matrices`），generic_signals 路径是多因子策略专用，暂不触及。
