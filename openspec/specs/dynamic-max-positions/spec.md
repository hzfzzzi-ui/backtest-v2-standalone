# dynamic-max-positions

## Purpose

Map breadth score to a per-day max_positions value, replacing the fixed constant with market-state-adaptive position management.

## Requirements

### R1: Step Mapping (step)
- score >= step_high (default 0.60) -> max_positions = max_pos (default 15)
- step_mid <= score < step_high (default 0.45) -> max_positions = baseline value (default 10)
- score < step_mid -> max_positions = min_pos (default 3)

### R2: Smooth Mapping (smooth)
- `scale = clip((score - smooth_lo) / smooth_range, 0, 1)`
- `max_positions = round(min_pos + scale * (max_pos - min_pos))`
- Defaults: smooth_lo=0.40, smooth_range=0.20, min_pos=3, max_pos=15

### R3: Engine Integration
- In `_run_unified_loop`, max_positions changes from fixed int to per-day array
- Each day uses `maxpos_arr[i]` instead of fixed value
- `calc_buy_slots(day_max, positions_after_sell)` uses dynamic value
- When breadth is not enabled, maxpos_arr filled entirely with original fixed max_positions (behavior unchanged)

### R4: Forced Sell (Position Reduction on Overallocation)
- Triggered when `len(positions) > day_max`
- Sort rule: ascending by strength (close/MA120 - 1), weakest sold first
- Constraint: positions not yet meeting min_hold_days are excluded from forced sell (skipped)
- If all positions protected by min_hold, day maxpos temporarily raised to actual position count (soft enforcement)
- Forced sell produces normal trade records, reason_code = "BREADTH_FORCED_SELL"
- Transaction costs same as normal sell

### R5: Configuration
- `BreadthConfig` dataclass, enabled defaults to false
- score_type: A / B / C / combo
- mapping_mode: step / smooth
- min_positions / max_positions / step_high / step_mid / smooth_lo / smooth_range
- ema_fast / ema_slow (used for breadth_momo calculation)

### R6: API Passthrough
- workbench_config.breadth section -> runtime BreadthConfig
- Frontend Position & Risk panel adds controls (checkbox + select + input)

### R7: Diagnostic Artifacts
- daily_rows adds: `breadth_score`, `dynamic_maxpos`, `forced_sell_count`
- perf.json adds: `avg_dynamic_maxpos`, `breadth_score_mean`, `forced_sell_total`
- loop_state adds: `breadth_forced_sell_count`, `breadth_avg_maxpos`
