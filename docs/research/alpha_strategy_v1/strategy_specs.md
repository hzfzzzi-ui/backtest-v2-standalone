# Alpha Strategy Research v1 — Strategy Specifications

## Context & Baseline

**Market:** A-share, 2015-01-01 ~ 2025-01-01, ALL_A 800 stocks
**Benchmark:** CSI800 (000906.SH), annualized ~-1.5% over this period
**Current baseline:** EMA(8,25) + ATR trail k=6 + TP 30% + ATR stop k=2 + min_hold=5 + cooldown=5
**Baseline result (30bp):** CAGR = -4.74%, Sharpe = -0.11, MaxDD ~38%

**Hard targets:**
- 10yr: CAGR >= 10%, MaxDD <= 30%, Sharpe >= 0.6
- 30bp cost: CAGR >= 8%
- WF: 7/10 positive years, median CAGR >= 6%
- Holding ratio >= 40%

**Gap analysis:** Baseline is ~15pp below target. The gap comes from:
1. Too many false MA cross signals in choppy A-share markets
2. No stock selection quality — random stocks that cross MA
3. High transaction cost drag (est. 10-15% annualized with ~200+ trades/yr at 70bp round-trip)

---

## Strategy 1: Momentum Selection (S1_MOMO)

### Core Thesis
Transform per-stock trend following into approximate cross-sectional momentum:
- Use MA cross as a **filter** (candidate must be in uptrend) — NOT the primary signal
- Use strength ranking as the **selector** (pick highest-momentum stocks)
- Use time exit to **force rotation** into new momentum winners
- Use wide trailing stops to **ride existing momentum**

### Signal Logic
```
ENTRY:
  EMA(10, 30) fast > slow            # stock in uptrend (filter, not signal)
  AND not ST/suspended/limit-up
  RANK by: close / MA(120) - 1       # momentum strength
  SELECT: top candidates to fill open slots (max 10)

EXIT (priority order):
  1. ATR stop:     close <= avg_cost - 2.5 * ATR(14)     ~5-7% loss
  2. Fixed stop:   close <= avg_cost * 0.92               8% hard floor
  3. ATR trailing: close <= peak - 5.0 * ATR(14)          protect profits
  4. Take profit:  close >= avg_cost * 1.25               lock 25% gain
  5. Time exit:    held_days >= 45                         FORCE ROTATION
  6. EMA cross:    fast < slow                             trend reversal

CONSTRAINTS:
  min_hold = 10 days, cooldown = 15 days

RISK:
  Market filter: slope_ma_period=50, light_multiplier=0.6
  (reduces new buys in bear market, does NOT force sell)
```

### Why It Could Work
1. **Momentum factor** is the strongest OHLCV-only alpha source in A-shares (academic: ~10-15% raw)
2. **Time exit at 45 days** transforms the strategy from "hold until exit" into "regular rotation"
   - Without it: hold losers too long, miss rotation into new winners
   - With it: natural ~monthly rebalance cycle, approximating cross-sectional momentum
3. **Strength ranking** selects the BEST momentum stocks, not random crossover stocks
4. **Wide trailing (k=5)** survives intraday noise but catches real trend reversals
5. **Market filter** reduces bear exposure without zeroing out (maintains >40% holding)

### Failure Modes
| Mode | Symptom | Monitor |
|------|---------|---------|
| Momentum crash | Sudden reversal of winners | Monthly return distribution, max single-day loss |
| Crowding | Alpha decay if too many follow momentum | Year-over-year alpha trend |
| High turnover | Cost drag exceeds alpha | Turnover rate, avg holding period |
| Bear exposure | Market filter too late/early | Holding ratio by market regime |

### Parameter Grid (5 combos)
| ID | fast | slow | trail_k | time_exit | Rationale |
|----|------|------|---------|-----------|-----------|
| S1_CENTER | 10 | 30 | 5.0 | 45 | Center point |
| S1_FAST | 8 | 25 | 5.0 | 45 | Faster entry (more signals) |
| S1_SLOW | 12 | 40 | 5.0 | 45 | Slower entry (fewer signals) |
| S1_TIGHT | 10 | 30 | 4.0 | 45 | Tighter trailing |
| S1_LONG | 10 | 30 | 5.0 | 60 | Longer hold period |

Other parameters held constant: ATR stop k=2.5, fixed stop 8%, TP 25%, min_hold=10, cooldown=15, max_pos=10.

---

## Strategy 2: Regime Adaptive Dual Engine (S2_REGIME)

### Core Thesis
Use regime detection to switch between two complementary engines:
- **TREND mode** (bull): aggressive momentum selection with wide trailing
- **CAUTIOUS mode** (bear/sideways): conservative RSI mean-reversion with tight stops
This provides "something to do" in all market conditions while controlling risk.

### Signal Logic
```
REGIME DETECTION:
  benchmark_close > EMA(benchmark, 50) → TREND
  benchmark_close <= EMA(benchmark, 50) → CAUTIOUS

TREND MODE:
  Entry: EMA(8, 25) fast > slow, ranked by strength
  Exit: ATR trail k=6, TP 30%, ATR stop k=2.0
  Max positions: 10

CAUTIOUS MODE:
  Entry: RSI(6) < 25 (oversold bounce)
  Exit: RSI(6) > 75 OR max_hold=5d OR stop_loss=5%
  Max positions: 5
  (Reduced exposure, quick trades, tight risk)

SHARED:
  min_hold = 5, cooldown = 10
  Market filter: OFF (regime detection handles it)

TRANSITION:
  When switching TREND→CAUTIOUS:
    - Stop generating new trend buys
    - Existing trend positions continue with trend exit rules
    - Start generating MR signals
  When switching CAUTIOUS→TREND:
    - Stop generating new MR buys
    - Existing MR positions exit by their own rules (max_hold=5)
    - Start generating trend signals
```

### Why It Could Work
1. **Dual engine** covers both trending and ranging markets
2. **RSI mean-reversion** in A-shares has short-term alpha (academic evidence for 3-5 day reversals)
3. **Position limit halved** in cautious mode → automatically reduces exposure
4. **Regime detection at EMA(50)** is faster than MA(200) but slower than day-to-day noise

### Failure Modes
| Mode | Symptom | Monitor |
|------|---------|---------|
| Regime whipsaw | Frequent switching | Regime switch count per year |
| MR losses | RSI bounces fail in crash | MR-mode P&L attribution |
| Lag at transition | Miss rally start/crash end | Days from regime start to first signal |
| MR too few trades | Not enough alpha to cover costs | MR trades/year, MR win rate |

### Parameter Grid (5 combos)
| ID | regime_ma | trail_k | rsi_buy | mr_hold | Rationale |
|----|-----------|---------|---------|---------|-----------|
| S2_CENTER | 50 | 6.0 | 25 | 5 | Center point |
| S2_FAST_REG | 40 | 6.0 | 25 | 5 | Faster regime detection |
| S2_SLOW_REG | 60 | 6.0 | 25 | 5 | Slower regime detection |
| S2_DEEP_RSI | 50 | 6.0 | 20 | 5 | Deeper oversold (fewer MR entries) |
| S2_LONG_MR | 50 | 6.0 | 25 | 8 | Longer MR hold |

---

## Strategy 3: Low Turnover Momentum (S3_LOWTURN)

### Core Thesis
Minimize transaction cost drag by trading as little as possible:
- Ultra-slow EMA (15, 40) generates ~60% fewer signals than EMA(8, 25)
- NO take profit — let winners run to full potential
- Long min_hold (15d) and cooldown (20d) prevent whipsaws
- Concentrated portfolio (8 positions) in strongest momentum stocks

### Signal Logic
```
ENTRY:
  EMA(15, 40) fast > slow
  RANK by: strength (close/MA120 - 1)
  SELECT: top 8

EXIT (priority order):
  1. Fixed stop:   close <= avg_cost * 0.90     10% hard floor
  2. ATR trailing: close <= peak - 6.0 * ATR(14) very wide trailing
  3. Time exit:    held_days >= 60               force rotation every 2 months
  4. EMA cross:    fast < slow                   trend reversal

  NO take profit (let winners run)

CONSTRAINTS:
  min_hold = 15, cooldown = 20

RISK:
  Market filter: OFF (maximize holding ratio)
  Max positions: 8

MULTIFACTOR RANKING: enabled
  (volume_z20 + ROC20 + RS60 + Bollinger position, equal weight)
```

### Why It Could Work
1. **Low turnover** → minimal cost drag (~4-6% annual vs ~12-15% for baseline)
2. **No take profit** → the few big winners compound fully (positive skew)
3. **Wide trailing (k=6)** → only exits on genuine trend reversal, not noise
4. **Concentrated (8 pos)** → each pick is highest-conviction momentum
5. **Multifactor ranking** → diversifies selection beyond pure momentum

### Failure Modes
| Mode | Symptom | Monitor |
|------|---------|---------|
| Concentration risk | Single stock blowup | Max single-stock P&L contribution |
| Slow adaptation | Miss regime changes | Avg days in losing position |
| Whipsaw on slow EMA | Still generates false signals | Annual trade count, win rate |
| Low holding ratio | Market filter OFF but still low | Daily position count distribution |

### Parameter Grid (4 combos)
| ID | fast | slow | trail_k | time_exit | max_pos | Rationale |
|----|------|------|---------|-----------|---------|-----------|
| S3_CENTER | 15 | 40 | 6.0 | 60 | 8 | Center point |
| S3_FASTER | 12 | 30 | 6.0 | 60 | 8 | Faster signals |
| S3_WIDER | 15 | 40 | 7.0 | 60 | 8 | Wider trailing |
| S3_MORE | 15 | 40 | 6.0 | 60 | 10 | More positions |

---

## Required Code Changes

Before running experiments, one API gap must be fixed:

**`enable_strength_rank` / `enable_multifactor_rank` are NOT in the HTTP API request model.**

These parameters currently only exist in `run_experiment()` overrides but the API endpoint doesn't pass them through. All prior experiments ran WITHOUT momentum ranking.

**Fix:** Add to `BacktestV2ExperimentRequest` and the overrides builder in `_experiment_runner_api.py`:
```
enable_strength_rank: bool | None = None
strength_ma: int | None = None
enable_multifactor_rank: bool | None = None
```

This is a ~10 line change.

---

## Priority Ranking

1. **S1_MOMO** (Momentum Selection) — highest conviction, clearest alpha source
2. **S3_LOWTURN** (Low Turnover) — lowest cost drag, simplest structure
3. **S2_REGIME** (Regime Adaptive) — most complex, highest implementation risk

## Honest Risk Assessment

Achieving CAGR >= 10% with OHLCV-only data in a market that returned ~-1.5% annualized over the test period is **extremely ambitious**. This requires ~12% annualized alpha. Professional quant funds with tick data, fundamentals, and alternatives struggle to maintain this.

Most likely outcomes:
- **Best case:** S1_MOMO achieves CAGR 8-12% via momentum selection + forced rotation
- **Base case:** S1_MOMO achieves CAGR 4-8%, below target but massive improvement over -5%
- **If all fail:** Document exactly why (cost drag vs alpha, regime dependency, etc.) and propose minimum changes needed (e.g., weekly rebalance mode, fundamental data integration)
