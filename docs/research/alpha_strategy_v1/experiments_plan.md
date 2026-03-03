# Alpha Strategy Research v1 — Experiment Plan

## Pre-requisites

### P0: API Gap Fix (~10 lines)
Add to `BacktestV2ExperimentRequest` in `_experiment_runner_api.py`:
```python
enable_strength_rank: bool | None = None
strength_ma: int | None = None
strength_top_k_mode: str | None = None
enable_multifactor_rank: bool | None = None
mf_topk: int | None = None
```
And add corresponding override passthrough in the overrides builder.

Without this, ALL experiments run without momentum ranking (strength_rank=False) which defeats the core strategy thesis.

### P1: Docker Rebuild
After API fix, rebuild and deploy Docker container.

---

## Experiment Matrix

### Common Parameters (all experiments unless noted)

```json
{
  "config_path": "configs/pams_cn_pg.json",
  "workbench_mode": "workbench",
  "universe_mode": "ALL_A",
  "universe_limit": 800,
  "base_order_value": 10000,
  "price_adj": "hfq"
}
```

### Cost Definitions

| Label | commission_rate | stamp_tax_rate | Round-trip est. |
|-------|----------------|----------------|-----------------|
| 5bp   | 0.0005         | 0.001          | ~21bp |
| 15bp  | 0.0015         | 0.001          | ~40bp |
| 30bp  | 0.003          | 0.001          | ~70bp |
| 50bp  | 0.005          | 0.001          | ~110bp |

### Bull/Bear/Sideways Segment Definition

Using benchmark (CSI800) with EMA(200):
- **Bull:** close > EMA(200) AND 200d return > 0
- **Bear:** close < EMA(200) AND 200d return < 0
- **Sideways:** other

Approximate segments in 2015-2025:
```
2015-01 to 2015-06: Bull (pre-crash rally)
2015-06 to 2016-02: Bear (crash + aftershock)
2016-02 to 2017-12: Sideways/Bull (recovery)
2018-01 to 2019-01: Bear (trade war)
2019-01 to 2021-02: Bull (recovery + COVID rebound)
2021-02 to 2022-12: Bear (regulatory + lockdown)
2023-01 to 2024-09: Sideways
2024-09 to 2025-01: Bull (Q4 rally)
```

---

## Phase 0: Baseline Reproduction

### EXP-B0: Current Baseline (no strength rank)
**Purpose:** Confirm baseline and get segment decomposition.

```json
{
  "signal_generation": {
    "strategy": "EMA_CROSS",
    "ema": {"fast_ma": 8, "slow_ma": 25}
  },
  "exit_rules": {
    "take_profit": {"enabled": true, "mode": "pct", "pct": 0.30},
    "atr_stop": {"enabled": true, "k": 2.0},
    "trailing": {"enabled": true, "k": 6.0},
    "hold_constraint": {"min_hold_days": 5, "cooldown_days": 5}
  },
  "costs": {"commission_rate": 0.003, "stamp_tax_rate": 0.001}
}
```
- `enable_strength_rank`: false (current default)
- Full period: 2015-01-01 ~ 2025-01-01
- Expected: CAGR ~-5%, confirms prior result

### EXP-B1: Baseline WITH Strength Ranking
**Purpose:** Measure isolated impact of momentum selection.

Same as B0 but `enable_strength_rank: true, strength_ma: 120`

**Key comparison:** B1 vs B0 = pure impact of stock selection.

---

## Phase 1: Strategy 1 (S1_MOMO) — Momentum Selection

### 1A: Full Period Runs (5 param combos)

| Run ID | fast | slow | trail_k | time_exit | Notes |
|--------|------|------|---------|-----------|-------|
| S1_CENTER | 10 | 30 | 5.0 | 45 | Center |
| S1_FAST | 8 | 25 | 5.0 | 45 | Faster entry |
| S1_SLOW | 12 | 40 | 5.0 | 45 | Slower entry |
| S1_TIGHT | 10 | 30 | 4.0 | 45 | Tighter trail |
| S1_LONG | 10 | 30 | 5.0 | 60 | Longer hold |

All with:
```json
{
  "enable_strength_rank": true,
  "strength_ma": 120,
  "max_positions": 10,
  "signal_generation": {
    "strategy": "EMA_CROSS",
    "ema": {"fast_ma": VAR, "slow_ma": VAR}
  },
  "exit_rules": {
    "take_profit": {"enabled": true, "mode": "pct", "pct": 0.25},
    "atr_stop": {"enabled": true, "k": 2.5},
    "fixed_stop": {"enabled": true, "pct": 0.08},
    "trailing": {"enabled": true, "k": VAR},
    "time_exit": {"enabled": true, "n_days": VAR},
    "hold_constraint": {"min_hold_days": 10, "cooldown_days": 15}
  },
  "position_risk": {
    "market_filter": {
      "enabled": true,
      "slope_ma_period": 50,
      "slope_window": 10,
      "light_multiplier": 0.6
    }
  },
  "costs": {"commission_rate": 0.003, "stamp_tax_rate": 0.001}
}
```
Period: 2015-01-01 ~ 2025-01-01
**Total: 5 API calls**

### 1B: Walk-Forward (best S1 variant)
Pick the BEST S1 variant by Sharpe. Run 10 × 1-year windows:
```
2015-01-01 ~ 2016-01-01
2016-01-01 ~ 2017-01-01
...
2024-01-01 ~ 2025-01-01
```
**Total: 10 API calls**

### 1C: Cost Sensitivity (best S1 variant)
Same params, vary commission_rate:
| Run ID | commission_rate |
|--------|----------------|
| S1_COST_5BP | 0.0005 |
| S1_COST_15BP | 0.0015 |
| S1_COST_30BP | (same as 1A run) |
| S1_COST_50BP | 0.005 |
**Total: 3 API calls** (30bp already run in 1A)

### S1 Total: 5 + 10 + 3 = 18 API calls

---

## Phase 2: Strategy 2 (S2_REGIME) — Regime Adaptive

### 2A: Full Period Runs (5 param combos)

| Run ID | regime_ma | trail_k | rsi_buy | mr_hold | Notes |
|--------|-----------|---------|---------|---------|-------|
| S2_CENTER | 50 | 6.0 | 25 | 5 | Center |
| S2_FAST_REG | 40 | 6.0 | 25 | 5 | Faster regime |
| S2_SLOW_REG | 60 | 6.0 | 25 | 5 | Slower regime |
| S2_DEEP_RSI | 50 | 6.0 | 20 | 5 | Deeper RSI |
| S2_LONG_MR | 50 | 6.0 | 25 | 8 | Longer MR |

Using REGIME_ROUTER strategy:
```json
{
  "enable_strength_rank": true,
  "strength_ma": 120,
  "max_positions": 10,
  "signal_generation": {
    "strategy": "REGIME_ROUTER",
    "regime_detection": {
      "regime_ma": VAR
    },
    "trend": {
      "strategy": "EMA_CROSS",
      "fast_ma": 8,
      "slow_ma": 25
    },
    "mr": {
      "rsi_period": 6,
      "rsi_buy_threshold": VAR,
      "rsi_sell_threshold": 75,
      "mr_max_hold_days": VAR,
      "mr_stop_loss_pct": 0.05
    }
  },
  "exit_rules": {
    "take_profit": {"enabled": true, "mode": "pct", "pct": 0.30},
    "atr_stop": {"enabled": true, "k": 2.0},
    "trailing": {"enabled": true, "k": VAR},
    "hold_constraint": {"min_hold_days": 5, "cooldown_days": 10}
  },
  "costs": {"commission_rate": 0.003, "stamp_tax_rate": 0.001}
}
```
**Total: 5 API calls**

### 2B: Walk-Forward + Cost (best S2 variant)
- 10 × 1yr WF + 3 cost sensitivity runs
**Total: 13 API calls**

### S2 Total: 5 + 13 = 18 API calls

---

## Phase 3: Strategy 3 (S3_LOWTURN) — Low Turnover Momentum

### 3A: Full Period Runs (4 param combos)

| Run ID | fast | slow | trail_k | time_exit | max_pos | Notes |
|--------|------|------|---------|-----------|---------|-------|
| S3_CENTER | 15 | 40 | 6.0 | 60 | 8 | Center |
| S3_FASTER | 12 | 30 | 6.0 | 60 | 8 | Faster signals |
| S3_WIDER | 15 | 40 | 7.0 | 60 | 8 | Wider trail |
| S3_MORE | 15 | 40 | 6.0 | 60 | 10 | More positions |

All with:
```json
{
  "enable_strength_rank": true,
  "strength_ma": 120,
  "enable_multifactor_rank": true,
  "max_positions": VAR,
  "signal_generation": {
    "strategy": "EMA_CROSS",
    "ema": {"fast_ma": VAR, "slow_ma": VAR}
  },
  "exit_rules": {
    "take_profit": {"enabled": false},
    "atr_stop": {"enabled": false},
    "fixed_stop": {"enabled": true, "pct": 0.10},
    "trailing": {"enabled": true, "k": VAR},
    "time_exit": {"enabled": true, "n_days": VAR},
    "hold_constraint": {"min_hold_days": 15, "cooldown_days": 20}
  },
  "costs": {"commission_rate": 0.003, "stamp_tax_rate": 0.001}
}
```
**Total: 4 API calls**

### 3B: Walk-Forward + Cost (best S3 variant)
- 10 × 1yr WF + 3 cost sensitivity runs
**Total: 13 API calls**

### S3 Total: 4 + 13 = 17 API calls

---

## Execution Order & Decision Gates

```
Phase 0: Baseline (2 runs)
   ├── B0: Current baseline → confirm -5% CAGR
   └── B1: + strength rank → measure selection alpha
          │
          ▼
   GATE 0: If B1 - B0 < 3pp improvement → strength rank not enough,
           need different entry signal. Adjust S1/S2/S3 before proceeding.
          │
Phase 1: S1_MOMO (18 runs)
   ├── 1A: 5 param combos → pick best by Sharpe
   ├── Sanity check: trades/yr, avg_positions, holding_ratio
   ├── GATE 1: CAGR > 0% → proceed to WF; else STOP, analyze why
   ├── 1B: 10yr WF of best combo
   └── 1C: 4 cost tiers
          │
Phase 2: S2_REGIME (18 runs)
   ├── Only if Phase 1 fails to hit target OR for comparison
   ├── 2A: 5 param combos
   ├── GATE 2: Same as Gate 1
   └── 2B: WF + cost of best
          │
Phase 3: S3_LOWTURN (17 runs)
   ├── Run in parallel with Phase 2 (independent)
   ├── 3A: 4 param combos
   ├── GATE 3: Same criteria
   └── 3B: WF + cost of best
          │
Final: Report generation
```

**Total budget: 2 + 18 + 18 + 17 = 55 API calls**
At ~5-8 min per ALL_A 800 run ≈ 4-7 hours total compute time.

---

## Output Artifacts Per Run

Each run produces:
- `results_dir/portfolio_daily.csv` — daily NAV/return series
- `results_dir/portfolio_trades.csv` — all trades with reason codes
- `results_dir/portfolio_candidates.csv` — signal funnel
- Return dict with: CAGR, MaxDD, Sharpe, Calmar, trades, avg_positions, exit counts

### Post-processing (experiment script responsibility)
From the raw outputs, the script computes:
1. **wf_summary.csv** — per-year metrics for WF runs
2. **segment_report.csv** — bull/bear/sideways breakdown (using benchmark EMA200)
3. **robustness.csv** — parameter neighbor comparison table
4. **cost_sensitivity.csv** — 5/15/30/50bp degradation curve
5. **reason_code.csv** — exit reason distribution (from trade reason_code field)

---

## Naming Convention

```
Run ID format: {strategy}_{variant}_{period}_{cost}

Examples:
  S1_CENTER_FULL_30BP      — S1 center params, full 10yr, 30bp
  S1_CENTER_WF_2019_30BP   — S1 center, walk-forward 2019 window
  S1_CENTER_FULL_5BP        — S1 center, full 10yr, 5bp costs
  B0_FULL_30BP              — baseline, full 10yr, 30bp
```

---

## Pass/Fail Criteria

### Per-Strategy Go/No-Go (after Phase A runs)

| Check | Threshold | Action if fail |
|-------|-----------|----------------|
| CAGR (10yr, 30bp) | > 0% | STOP — strategy is losing money |
| Trades per year | 50 ~ 400 | If < 50: too conservative; > 400: too costly |
| Avg positions | 3 ~ 10 | If < 3: not invested; > 10: check max_pos |
| Holding ratio | >= 40% | If < 40%: market filter too aggressive |
| Win rate | >= 35% | If < 35%: signal quality insufficient |

### Final Pass (after WF + cost + robustness)

| Check | Threshold | Hard/Soft |
|-------|-----------|-----------|
| CAGR (10yr, 30bp) | >= 10% | Hard target |
| CAGR (10yr, 30bp) | >= 8% | Soft target (acceptable) |
| MaxDD | <= 30% | Hard |
| Sharpe | >= 0.6 | Hard |
| WF positive years | >= 7/10 | Hard |
| WF median CAGR | >= 6% | Hard |
| Single year max contribution | <= 35% | Hard |
| Cost monotonicity | 5bp > 15bp > 30bp > 50bp | Hard |
| Param neighbor stability | Sharpe within +-0.15 of best | Hard |
| Bear segment CAGR | >= -5% | Hard |
| Holding ratio | >= 40% | Hard |

---

## Experiment Script Architecture

```python
# run_alpha_v1.py (to be created)
#
# Structure:
#   1. submit_job(wb_config, overrides) → job_id
#   2. poll(job_id) → result dict
#   3. extract_metrics(result) → {cagr, maxdd, sharpe, ...}
#   4. Phase dispatch: baseline → S1 → gate → S2/S3
#   5. Post-processing: WF summary, segment analysis, etc.
#   6. Report generation: final_report.md
#
# The script uses the same HTTP API pattern as run_gate_v2.py:
#   POST /api/backtest_v2/experiment/run_async
#   GET  /api/backtest_v2/jobs/{job_id}
```
