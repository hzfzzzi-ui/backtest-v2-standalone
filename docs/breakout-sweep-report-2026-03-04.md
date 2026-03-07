# Breakout Trend 参数扫描优化报告 (2026-03-04)

## 实验背景

### 生存偏差修复

原 AKShare 数据仅包含**当前**中证 800 成分股，`end_date` 永远为 NULL，导致回测引入未来函数（生存偏差）。

**修复方案**：使用 BaoStock 逐月拉取 HS300 + ZZ500 历史成分快照（2007-01 至 2026-03），重建 `in_date / out_date` 变动表。

| 数据项 | 修复前 (AKShare) | 修复后 (BaoStock) |
|--------|-----------------|------------------|
| 数据来源 | `akshare_index_stock_cons` | `baostock_pit_snapshot` |
| 总记录数 | 700 | 2,814 |
| 不重复股票 | ~700 | 1,996 |
| 当前成分 | 700 (end_date=NULL) | 800 |
| 历史移出记录 | 0 | 2,014 |
| 2016-03-01 PIT | ~700 (有偏) | 800 (真实) |

### 偏差量化

| 策略 | 有偏 CAGR | 真 PIT CAGR | 偏差膨胀 |
|------|----------|-------------|---------|
| Breakout 20d baseline | +7.51% | +2.41% | **+5.10%** |
| EMA Cross G5 champion | +0.06% | -1.16% | +1.22% |

**结论**：Breakout 策略的生存偏差影响远大于 EMA Cross，因为 breakout 更依赖股票池中的强势股，而被移出指数的弱势股在有偏数据中被隐藏。

---

## 实验目标

在真 PIT CSI800 上优化 Breakout Trend 策略，目标：**CAGR > 5% 且 MDD < 40%**。

主排名指标：**Calmar ratio**（CAGR / MDD）

判断框架：
- CAGR > 5% + MDD < 30% + Sharpe > 0.5 → 值得深入
- CAGR > 3% + MDD < 40% → 可接受的分散策略
- CAGR < 2% → breakout 在 CSI800 不适用

---

## 公共配置（三阶段共用）

```json
{
  "universe_mode": "HS300_ZZ500",
  "start_date": "2016-03-01",
  "end_date": "2026-03-01",
  "benchmark": "000300.SH",
  "initial_capital": 1000000,
  "max_positions": 10,
  "price_adj": "hfq",
  "strategy": "breakout_trend",
  "min_hold_days": 5,
  "cooldown_days": 5,
  "min_price": 5.0,
  "market_filter": false,
  "benchmark_regime": false,
  "breadth": false,
  "sizing": {"weight_mode": "equal", "min_positions": 10, "lot_size": 100}
}
```

---

## Phase 1：退出系统优化

**固定参数**：breakout_window=20, v2_trend=on, regime_ma=120, atr_stop_k=2.0, min5/cool5

### 配置矩阵

| ID | 止盈 | ATR trail k | LOW10 | 核心假设 |
|----|------|-------------|-------|----------|
| P1-A | 无 | 3 | on | 当前 baseline |
| P1-B | 20% | 3 | on | 中等止盈 |
| P1-C | 30% | 3 | on | Champion 级止盈 |
| P1-D | 无 | 5 | on | 宽松追踪，让利润跑 |
| P1-E | 30% | 5 | on | 止盈 + 宽追踪 |
| P1-F | 30% | 6 | off | Champion 风格：TP30 + 极宽追踪 + 无 LOW10 |

### 完整配置详情

**P1-A** (baseline)
```
enable_take_profit: false
atr_trail_k: 3.0, enable_low10_exit: true
atr_stop_k: 2.0, enable_atr_stop: true, enable_atr_trail: true
enable_fixed_stop_loss: false, enable_ma20_exit: false
```

**P1-B** (TP=20%, trail=3)
```
enable_take_profit: true, take_profit_mode: pct, take_profit_pct: 0.20
atr_trail_k: 3.0, enable_low10_exit: true
其余同 P1-A
```

**P1-C** (TP=30%, trail=3)
```
enable_take_profit: true, take_profit_mode: pct, take_profit_pct: 0.30
atr_trail_k: 3.0, enable_low10_exit: true
其余同 P1-A
```

**P1-D** (无 TP, trail=5)
```
enable_take_profit: false
atr_trail_k: 5.0, enable_low10_exit: true
其余同 P1-A
```

**P1-E** (TP=30%, trail=5)
```
enable_take_profit: true, take_profit_mode: pct, take_profit_pct: 0.30
atr_trail_k: 5.0, enable_low10_exit: true
其余同 P1-A
```

**P1-F** (TP=30%, trail=6, 无 LOW10)
```
enable_take_profit: true, take_profit_mode: pct, take_profit_pct: 0.30
atr_trail_k: 6.0, enable_low10_exit: false
其余同 P1-A
```

### 结果排名（按 Calmar）

| 排名 | 配置 | CAGR | MDD | Sharpe | Calmar | 交易数 |
|------|------|------|-----|--------|--------|--------|
| 1 | **P1-B**: TP=20%, trail=3, LOW10 | **+2.41%** | **-36.47%** | 0.22 | **0.07** | 278 |
| 2 | P1-F: TP=30%, trail=6, 无 LOW10 | +1.71% | -39.26% | 0.19 | 0.04 | 190 |
| 3 | P1-A: baseline (无 TP, trail=3) | +2.41% | -63.12% | 0.22 | 0.04 | 82 |
| 4 | P1-E: TP=30%, trail=5, LOW10 | +0.88% | -43.40% | 0.15 | 0.02 | 200 |
| 5 | P1-C: TP=30%, trail=3, LOW10 | +0.17% | -38.17% | 0.12 | 0.00 | 236 |
| 6 | P1-D: 无 TP, trail=5, LOW10 | -0.61% | -52.80% | 0.10 | -0.01 | 57 |

### 退出类型分布

| 配置 | TAKE_PROFIT | ATR_STOP | ATR_TRAIL | 总退出 |
|------|-------------|----------|-----------|--------|
| P1-A | 0 | 11 | 26 | 37 |
| P1-B | 74 | 43 | 17 | 134 |
| P1-C | 44 | 45 | 24 | 113 |
| P1-D | 0 | 20 | 5 | 25 |
| P1-E | 45 | 47 | 3 | 95 |
| P1-F | 44 | 45 | 1 | 90 |

### Phase 1 分析

1. **TP=20% 是甜蜜点**：P1-B 与 baseline 同样 CAGR (+2.41%)，但 MDD 从 63% 降至 36%，交易数从 82 暴增到 278。TP 加速了资金轮转。
2. **TP=30% 过高**：P1-C CAGR 仅 +0.17%，说明 30% 止盈在 breakout 上等太久，错过最佳卖出时机。与 EMA Cross 不同（TP=30% 最优），breakout 的利润分布更薄。
3. **宽追踪无意义**：trail k=5/6 让追踪止损几乎不触发（P1-F 仅 1 次），ATR_STOP 反而成了主要退出。
4. **无 TP + 宽追踪最差**：P1-D 仅 57 笔交易，CAGR 为负。资金被锁在持仓中太久。

**Winner: P1-B** → 进入 Phase 2

---

## Phase 2：入场放松

**固定退出参数（来自 P1-B）**：TP=20%, trail_k=3, LOW10=on, atr_stop_k=2.0

### 配置矩阵

| ID | breakout_window | V2 趋势过滤 | regime_ma | 核心假设 |
|----|----------------|------------|-----------|----------|
| P2-A | 20 | on | 120 | Phase 1 winner（baseline） |
| P2-B | 15 | on | 120 | 更短窗口 → 更多信号 |
| P2-C | 10 | on | 120 | 激进短窗口 |
| P2-D | 20 | off | 120 | 去掉个股趋势过滤 |
| P2-E | 15 | off | 120 | 短窗口 + 无趋势过滤 |
| P2-F | 15 | off | 60 | 全面放松 |

### 完整配置详情

**P2-A** (Phase 1 winner baseline)
```
breakout_window: 20
enable_v2_trend_filter: true, v2_trend_short_ma: 20, v2_trend_long_ma: 60
regime_ma: 120
退出参数: TP=20%, trail_k=3, LOW10, stop_k=2.0
```

**P2-B** (短窗口)
```
breakout_window: 15
enable_v2_trend_filter: true, v2_trend_short_ma: 20, v2_trend_long_ma: 60
regime_ma: 120
退出参数同 P2-A
```

**P2-C** (激进短窗口)
```
breakout_window: 10
enable_v2_trend_filter: true, v2_trend_short_ma: 20, v2_trend_long_ma: 60
regime_ma: 120
退出参数同 P2-A
```

**P2-D** (无趋势过滤)
```
breakout_window: 20
enable_v2_trend_filter: false
regime_ma: 120
退出参数同 P2-A
```

**P2-E** (短窗口 + 无趋势)
```
breakout_window: 15
enable_v2_trend_filter: false
regime_ma: 120
退出参数同 P2-A
```

**P2-F** (全面放松)
```
breakout_window: 15
enable_v2_trend_filter: false
regime_ma: 60
退出参数同 P2-A
```

### 结果排名（按 Calmar）

| 排名 | 配置 | CAGR | MDD | Sharpe | Calmar | 交易数 |
|------|------|------|-----|--------|--------|--------|
| 1 | **P2-D**: bw=20, v2=off, rma=120 | **+4.77%** | **-23.97%** | 0.34 | **0.20** | 306 |
| 2 | P2-C: bw=10, v2=on, rma=120 | +3.60% | -27.96% | 0.28 | 0.13 | 308 |
| 3 | P2-E: bw=15, v2=off, rma=120 | +2.73% | -23.10% | 0.23 | 0.12 | 356 |
| 4 | P2-A: bw=20, v2=on, rma=120 | +2.41% | -36.47% | 0.22 | 0.07 | 278 |
| 5 | P2-B: bw=15, v2=on, rma=120 | +1.52% | -35.46% | 0.18 | 0.04 | 258 |
| 6 | P2-F: bw=15, v2=off, rma=60 | -1.77% | -38.36% | 0.02 | -0.05 | 290 |

### Phase 2 分析

1. **去掉 v2_trend_filter 是最大的 alpha 提升**：P2-D vs P2-A，同样 bw=20、rma=120，CAGR 从 +2.41% 升至 +4.77%（+2.36%），MDD 从 36% 降至 24%。v2 趋势过滤（SMA20>SMA60 AND close>SMA60）对 breakout 信号过于严苛，过滤掉了很多有效突破。
2. **短窗口 bw=10 有效但弱于去 v2**：P2-C (+3.60%) 不如 P2-D (+4.77%)。缩短窗口增加信号量，但质量下降。
3. **regime_ma=60 灾难性**：P2-F 的 CAGR 为 -1.77%。更短的体制过滤 MA 让太多假突破通过。regime_ma=120 是必要的保护屏障。
4. **bw=15 不如 bw=20**：无论有无 v2 过滤，15 日窗口都弱于 20 日。20 日突破的信号质量更高。

**Winner: P2-D** → 进入 Phase 3

---

## Phase 3：风控优化

**固定入场参数（来自 P2-D）**：bw=20, v2_trend=off, regime_ma=120
**固定退出参数（来自 P1-B）**：TP=20%, trail_k=3, LOW10=on

### 配置矩阵

| ID | atr_stop_k | DD 熔断 | dd_reduce_pct / scale | 核心假设 |
|----|-----------|---------|----------------------|----------|
| P3-A | 2.0 | off | — | Phase 2 winner |
| P3-B | 1.5 | off | — | 更紧初始止损 |
| P3-C | 2.0 | on | 10% / 0.5 | DD 降仓 |
| P3-D | 1.5 | on | 10% / 0.5 | 紧止损 + DD 降仓 |
| P3-E | 2.0 | on | 15% / 0.3 | 激进 DD 降仓 |
| P3-F | 1.5 | on | 15% / 0.3 | 紧止损 + 激进 DD |

### 完整配置详情

**P3-A** (Phase 2 winner)
```
atr_stop_k: 2.0
risk_budget: {enabled: false}
入场: bw=20, v2=off, rma=120
退出: TP=20%, trail_k=3, LOW10
```

**P3-B** (更紧止损)
```
atr_stop_k: 1.5
risk_budget: {enabled: false}
其余同 P3-A
```

**P3-C** (标准止损 + DD 熔断)
```
atr_stop_k: 2.0
risk_budget: {enabled: true, dd_reduce_pct: 0.10, dd_reduce_scale: 0.5, atr_stop_k: 2.0}
其余同 P3-A
```

**P3-D** (紧止损 + DD 熔断)
```
atr_stop_k: 1.5
risk_budget: {enabled: true, dd_reduce_pct: 0.10, dd_reduce_scale: 0.5, atr_stop_k: 1.5}
其余同 P3-A
```

**P3-E** (标准止损 + 激进 DD)
```
atr_stop_k: 2.0
risk_budget: {enabled: true, dd_reduce_pct: 0.15, dd_reduce_scale: 0.3, atr_stop_k: 2.0}
其余同 P3-A
```

**P3-F** (紧止损 + 激进 DD)
```
atr_stop_k: 1.5
risk_budget: {enabled: true, dd_reduce_pct: 0.15, dd_reduce_scale: 0.3, atr_stop_k: 1.5}
其余同 P3-A
```

### 结果排名（按 Calmar）

| 排名 | 配置 | CAGR | MDD | Sharpe | Calmar | 交易数 |
|------|------|------|-----|--------|--------|--------|
| 1 | **P3-D**: stop=1.5, DD 10%/0.5 | **+5.46%** | **-24.32%** | **0.36** | **0.22** | 324 |
| 2 | P3-A: stop=2.0, 无 DD | +4.77% | -23.97% | 0.34 | 0.20 | 306 |
| 3 | P3-E: stop=2.0, DD 15%/0.3 | +4.14% | -24.11% | 0.31 | 0.17 | 248 |
| 4 | P3-B: stop=1.5, 无 DD | +2.84% | -20.68% | 0.24 | 0.14 | 350 |
| 5 | P3-C: stop=2.0, DD 10%/0.5 | +2.84% | -21.61% | 0.24 | 0.13 | 278 |
| 6 | P3-F: stop=1.5, DD 15%/0.3 | +2.38% | -25.67% | 0.22 | 0.09 | 286 |

### 退出类型分布

| 配置 | TAKE_PROFIT | ATR_STOP | ATR_TRAIL | 总退出 |
|------|-------------|----------|-----------|--------|
| P3-A | 84 | 47 | 17 | 148 |
| P3-B | 83 | 75 | 12 | 170 |
| P3-C | 71 | 46 | 17 | 134 |
| P3-D | 82 | 58 | 17 | 157 |
| P3-E | 67 | 37 | 15 | 119 |
| P3-F | 67 | 63 | 8 | 138 |

### Phase 3 分析

1. **紧止损 + DD 熔断的组合最优**：P3-D 同时使用 stop_k=1.5 和 DD 10%/0.5，CAGR 比 P3-A 高 +0.69%，MDD 基本持平。两层保护产生了协同效应。
2. **单独紧止损反而伤 CAGR**：P3-B (stop=1.5, 无 DD) CAGR 仅 +2.84%，比 P3-A 低 1.93%。止损太紧导致频繁被震出（ATR_STOP 从 47 次升至 75 次），但 MDD 确实降到最低 20.68%。
3. **单独 DD 熔断效果有限**：P3-C (stop=2.0, DD 10%/0.5) CAGR 也仅 +2.84%。DD 熔断减少了持仓数（avg 7.8 vs 8.8），但标准止损不够灵活。
4. **激进 DD (15%/0.3) 过度**：P3-E 和 P3-F 的 CAGR 都较低。DD 触发太晚（15%）、降仓太猛（30%），错过恢复行情。
5. **P3-D 的协同机制**：紧止损（1.5ATR）快速止损单笔亏损 → DD 熔断（10%/0.5）在组合层面缩仓 → 两者叠加在控制回撤的同时保留了足够的上行空间。

**Winner: P3-D** → 最终冠军

---

## 最终冠军配置

### 参数总览

```
策略类型:           breakout_trend
突破窗口:           20 日
个股趋势过滤:       关闭
体制 MA:            120 日
最低价格:           5.0 元

止盈:               20%（百分比止盈）
ATR 追踪止损:       k=3
ATR 初始止损:       k=1.5
LOW10 退出:         开启
固定止损:           关闭
MA20 退出:          关闭

最小持仓天数:       5 天
冷却期:             5 天
最大持仓数:         10
选股池:             HS300_ZZ500（中证 800 成分股 PIT）
起始资金:           100 万
复权模式:           后复权 (hfq)

DD 熔断:            开启
DD 触发阈值:        10%
DD 降仓系数:        0.5
市场过滤器:         关闭
风格排名:           关闭
```

### API 提交格式

```json
{
  "universe_mode": "HS300_ZZ500",
  "start_date": "2016-03-01",
  "end_date": "2026-03-01",
  "benchmark": "000300.SH",
  "initial_capital": 1000000,
  "max_positions": 10,
  "fast_mode": true,
  "price_adj": "hfq",
  "strategy": {
    "name": "breakout_trend",
    "order_size": 1000,
    "params": {
      "breakout_window": 20,
      "min_price": 5.0,
      "regime_ma": 120,
      "enable_v2_trend_filter": false,
      "enable_atr_stop": true,
      "atr_stop_k": 1.5,
      "enable_atr_trail": true,
      "atr_trail_k": 3.0,
      "enable_take_profit": true,
      "take_profit_mode": "pct",
      "take_profit_pct": 0.20,
      "enable_fixed_stop_loss": false,
      "enable_ma20_exit": false,
      "enable_low10_exit": true,
      "max_hold_days": 0,
      "min_hold_days": 5,
      "cooldown_days": 5,
      "momentum_top_pct": 0.0,
      "enable_sector_gate": false
    }
  },
  "exit": {
    "enable_atr_stop": true,
    "atr_stop_k": 1.5,
    "enable_atr_trail": true,
    "atr_trail_k": 3.0,
    "enable_take_profit": true,
    "take_profit_mode": "pct",
    "take_profit_pct": 0.20,
    "enable_fixed_stop_loss": false,
    "enable_low10_exit": true
  },
  "sizing": {
    "order_value": 0,
    "lot_size": 100,
    "weight_mode": "equal",
    "min_positions": 10
  },
  "risk_budget": {
    "enabled": true,
    "dd_reduce_pct": 0.10,
    "dd_reduce_scale": 0.5,
    "atr_stop_k": 1.5
  },
  "market_filter": {"enabled": false},
  "benchmark_regime": {"enabled": false},
  "breadth": {"enabled": false}
}
```

### 绩效指标

| 指标 | 数值 |
|------|------|
| **年化收益率 (CAGR)** | **+5.46%** |
| 累计收益 | +66.79% |
| 最大回撤 | -24.32% |
| 夏普比率 | 0.36 |
| 卡尔玛比率 | 0.22 |
| 总交易次数 | 324 |
| 平均持仓数 | 7.8 |

---

## 进化路径

| 阶段 | 配置 | CAGR | MDD | Calmar | 关键改动 |
|------|------|------|-----|--------|----------|
| 起点 | baseline (无 TP, trail=3, stop=2) | +2.41% | -63.12% | 0.04 | — |
| Phase 1 | +TP=20% | +2.41% | -36.47% | 0.07 | MDD 减半，交易增 3 倍 |
| Phase 2 | -v2_trend_filter | +4.77% | -23.97% | 0.20 | CAGR 翻倍，最大提升 |
| Phase 3 | stop=1.5 + DD 10%/0.5 | **+5.46%** | **-24.32%** | **0.22** | 风控组合锦上添花 |

### 累计提升

- CAGR：+2.41% → +5.46%（**+3.05%**，提升 127%）
- MDD：-63.12% → -24.32%（**改善 38.80%**）
- Calmar：0.04 → 0.22（**提升 5.5 倍**）

---

## 关键发现与策略洞察

### 1. Breakout vs EMA Cross：退出参数不可互换

EMA Cross 的最优 TP=30%，但 Breakout 的最优 TP=20%。原因：EMA Cross 依靠均线交叉信号退出（信号反转），TP 是兜底保护；Breakout 无内生退出信号，TP 是主要退出通道。因此 Breakout 需要更低的 TP 来加速资金轮转。

### 2. v2_trend_filter 对 Breakout 有害

v2 趋势过滤（SMA20 > SMA60 AND close > SMA60）设计初衷是只在上升趋势中买入，但 Breakout 本身就是趋势确认信号（创 20 日新高 = 强趋势）。双重趋势确认导致信号严重滞后，错过最佳入场时机。去掉后 CAGR 提升 +2.36%。

### 3. DD 熔断与 ATR 止损的协同

单独使用 stop_k=1.5（紧止损）→ MDD 降低但 CAGR 大幅下降（被震出）。
单独使用 DD 10%/0.5（熔断）→ MDD 降低但 CAGR 也下降（减仓太被动）。
组合使用 → CAGR 最高且 MDD 可控。

机制：紧止损在个股层面快速止损，DD 熔断在组合层面缩仓。紧止损减少了进入 DD 熔断的概率，DD 熔断在极端行情中进一步保护。

### 4. regime_ma=120 是必需保护

将 regime_ma 从 120 降至 60，CAGR 从 +2.73% 骤降至 -1.77%。MA120 作为大盘体制过滤器，防止在下行趋势中开新仓。MA60 太短，无法有效识别熊市。

---

## 待验证事项

1. **Walk-forward 稳定性**：冠军配置的 10 年回测是否在各年度均稳定？
2. **成本敏感性**：交易成本从 5bp 升至 30bp 后 CAGR 衰减多少？
3. **与 EMA Cross 的互补性**：两个策略相关性如何？是否适合组合配置？
4. **样本外验证**：在 CSI1000 或行业子集上表现如何？

---

## 技术备注

- 扫描脚本：`backend/scripts/run_breakout_sweep.py`
- PIT 数据脚本：`backend/scripts/fetch_csi800_pit.py` + `import_csi800_pit.py`
- `atr_trail_k` 必须同时写入 `strategy.params` 和 `exit` block（引擎从两处分别读取）
- Breakout 的 `enable_risk_off_exit=False`：RISK_OFF 只阻止新开仓，不强制平仓
