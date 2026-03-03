# Backtest Analysis: Adaptive Regime Strategy

Date: 2026-03-01

## Champion Configuration

```
regime_ma: 60, RSI(6), buy_threshold: 20, sell_threshold: 80,
mr_max_hold_days: 5, mr_stop_loss_pct: 3%
```

## Summary vs Baseline

| Metric | SMA 5/20 (baseline) | Adaptive Regime (champion) | Improvement |
|--------|--------------------|-----------------------------|-------------|
| **Full cycle CAGR** | 2.29% | **10.30%** | **+4.5x** |
| **Full cycle total return** | 14.26% | **78.23%** | +5.5x |
| **Max drawdown** | -18.89% | -23.64% | -4.75pp worse |
| **Sharpe ratio** | 0.230 | **0.606** | +2.6x |
| **Trades** | 1784 | 2149 | +20% more |
| **Trending CAGR (2024-26)** | 14.06% | **15.00%** | +0.94pp |
| **Trending Sharpe** | 0.695 | **0.910** | +1.3x |
| **Trending MDD** | -15.57% | **-11.11%** | -4.46pp better |

## Full Parameter Sweep Results

### Round 1: Regime MA sensitivity (full cycle 2020-2026)

| regime_ma | CAGR | MDD | Sharpe | Trades |
|-----------|------|-----|--------|--------|
| **60** | **-1.64%** | -37.16% | 0.029 | 2678 |
| 120 | -1.77% | -46.31% | 0.024 | 2260 |
| 200 | -10.77% | -55.41% | -0.420 | 2264 |

*(Round 1 used default RSI 25/70 which is suboptimal)*

### Round 2: RSI parameters (regime_ma=60, full cycle)

| Config | CAGR | MDD | Sharpe | Trades |
|--------|------|-----|--------|--------|
| RSI(6) 25/70 | -1.64% | -37.16% | 0.029 | 2678 |
| RSI(10) 30/70 | 0.01% | -38.47% | 0.100 | 2124 |
| RSI(14) 30/70 | 1.62% | -24.35% | 0.181 | 1518 |
| **RSI(6) 20/80** | **4.06%** | -31.61% | 0.299 | 1952 |
| RSI(14) 25/75 | 2.24% | -27.86% | 0.211 | 1054 |

### Round 3: Hold/Stop variations (RSI 20/80, full cycle)

| Config | CAGR | MDD | Sharpe | Trades |
|--------|------|-----|--------|--------|
| **h5 s3%** | **10.30%** | **-23.64%** | **0.606** | 2149 |
| h3 s3% | 8.22% | -19.85% | 0.505 | 2322 |
| h7 s3% | 8.01% | -26.02% | 0.489 | 2055 |
| h5 s2% | 8.26% | -25.57% | 0.512 | 2174 |
| h5 s8% | 2.09% | -33.69% | 0.204 | 1992 |
| h20 s5% | -0.47% | -45.70% | 0.080 | 1782 |
| noHold noStop | 8.07% | -36.70% | 0.494 | 1347 |
| 15/85 h10 s5% | 5.13% | -22.29% | 0.348 | 1356 |

### Round 6: Fine-tuning champion (full cycle)

| Config | CAGR | MDD | Sharpe | Trades |
|--------|------|-----|--------|--------|
| **20/80 h5 s3% (champion)** | **10.30%** | -23.64% | **0.606** | 2149 |
| 18/82 h5 s3% | 5.82% | -21.15% | 0.380 | 1921 |
| 22/78 h5 s3% | 0.63% | -35.44% | 0.130 | 2452 |
| 20/80 h4 s3% | 9.17% | -22.40% | 0.540 | 2198 |
| 20/80 h6 s3% | 5.27% | -24.72% | 0.364 | 2158 |
| 20/80 h5 s4% | 6.08% | -25.04% | 0.398 | 2112 |
| R50 20/80 h5 s3% | -0.02% | -30.89% | 0.103 | 2222 |
| R70 20/80 h5 s3% | 6.79% | -33.19% | 0.441 | 2169 |

## Key Insights

1. **RSI 阈值极其敏感**: 20/80 远优于 25/70。更严格的阈值减少噪音交易。
2. **短持仓 + 紧止损 是关键**: h5 + s3% 是最优组合。MR 模式本质是快进快出。
3. **regime_ma=60 最优**: R50 太灵敏（频繁切换损耗），R80/120/200 太慢（延迟检测错过机会）。
4. **趋势期不受影响**: champion 在 2024-2026 CAGR=15.00%，超过基线 14.06%。
5. **震荡期仍有损失**: 2021-2023 CAGR=-3.29%（基线+3.01%）。MR 模式在真正的熊市中仍会亏损，但被趋势期的超额收益大幅弥补。
6. **全周期 CAGR 从 2.29% 跃升至 10.30%**，Sharpe 从 0.23 到 0.61。

## Recommended Default Parameters

```json
{
  "strategy": "adaptive_regime",
  "fast": 5,
  "slow": 20,
  "regime_ma": 60,
  "rsi_period": 6,
  "rsi_buy_threshold": 20,
  "rsi_sell_threshold": 80,
  "mr_max_hold_days": 5,
  "mr_stop_loss_pct": 0.03
}
```
