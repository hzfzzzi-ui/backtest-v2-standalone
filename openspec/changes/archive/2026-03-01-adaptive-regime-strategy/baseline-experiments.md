# Baseline Experiments — Pure Trend Strategy (SMA Cross)

Recorded: 2026-03-01

## Current Default Parameters

From `configs/pams_cn_pg.json`:
- Strategy: `sma_cross`
- Fast MA: 5
- Slow MA: 20
- Order size: 1000
- Initial capital: 100,000
- Lot size: 100

Workbench defaults (from previous parameter sweep):
- Universe: ALL_A, limit=100 (best performer)
- Max positions: 10
- Exclude ST: true
- Exclude suspended: true

## Baseline Results

All experiments: initial_capital=1,000,000, max_positions=10, SMA 5/20

### ALL_A Universe (limit=100)

| # | Period | Total Return | CAGR | Max Drawdown | Sharpe | Trades |
|---|--------|-------------|------|-------------|--------|--------|
| 1 | 2020-01 ~ 2026-02 (full cycle) | 14.26% | 2.29% | -18.89% | 0.230 | 1784 |
| 2 | 2024-01 ~ 2026-02 (trending) | 30.84% | 14.06% | -15.57% | 0.695 | 846 |
| 3 | 2021-01 ~ 2023-12 (sideways/bear) | 8.94% | 3.01% | -5.30% | 0.530 | 718 |

### HS300_ZZ500 Universe (limit=100)

| # | Period | Total Return | CAGR | Max Drawdown | Sharpe | Trades |
|---|--------|-------------|------|-------------|--------|--------|
| 4 | 2020-01 ~ 2026-02 (full cycle) | 19.29% | 3.04% | -20.71% | 0.299 | 1819 |
| 5 | 2024-01 ~ 2026-02 (trending) | 3.46% | 1.68% | -11.12% | 0.201 | 907 |
| 6 | 2021-01 ~ 2023-12 (sideways/bear) | 0.20% | 0.07% | -9.56% | 0.053 | 674 |

## Key Observations

1. **ALL_A universe significantly outperforms HS300_ZZ500** — especially in trending period (14.06% vs 1.68% CAGR)
2. **Sideways period (2021-2023) is the main drag** — only 3% CAGR on ALL_A, near-zero on HS300
3. **Full cycle CAGR ceiling ~2-3%** with pure SMA cross
4. **Trending period (2024-2026) shows strategy potential** — 14% CAGR with good Sharpe
5. **Goal: 15%+ CAGR** — need to either avoid losses in sideways or generate alpha during sideways

## Target for Adaptive Regime Strategy

- In trending regime: match or exceed 14% CAGR (EXP2 baseline)
- In sideways regime: achieve positive returns instead of near-zero drag
- Full cycle: aim for 8%+ CAGR (vs current 2.3%)
