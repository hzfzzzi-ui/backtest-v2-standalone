# Runtime Diagnostics Field Mapping

## Source Inputs

| Source | Raw field | Meaning |
| --- | --- | --- |
| `day_signals.diagnostics` | `raw_buy_signal_count` | Provider-level raw BUY signal count before portfolio screening |
| `day_signals.diagnostics` | `raw_alpha_signal_count` | Raw alpha signal count before composition |
| `day_signals.diagnostics` | `composed_buy_signal_count` | BUY signal count after composition |
| `day_signals.diagnostics` | `composed_sell_signal_count` | SELL signal count after composition |
| `day_signals.diagnostics` | `buy_candidate_count` | Provider-emitted candidate count before held filter normalization |
| `day_signals.diagnostics` | `after_held_filter_count` | Provider-emitted count after held-already suppression |
| `debug_plan` | `buy_candidates_count` | Portfolio planner candidate count entering ranking/allocation |
| `debug_plan` | `selected_count` / `selected_symbols` | Final selected BUY count before fills |
| `debug_plan` | `after_slot_filter_count` / `after_sleeve_budget_count` | Count surviving slot / sleeve budget stage |
| `debug_plan` | `after_cash_lot_count` | Count surviving cash / lot stage |
| `daily_row` | `benchmark_regime_on` | Route hint needed by breakout funnel normalization |

## Canonical Runtime Diagnostics Input

`daily_accounting.py` now writes `diagnostics_input_json` per daily row. The payload is represented by `RuntimeDiagnosticsInput` and stores:

- route identity
- raw provider diagnostics counts
- raw portfolio/debug plan counts
- benchmark regime hint
- raw provider diagnostics mapping
- raw planner debug plan mapping

Execution-layer daily columns remain as flattened observations, but the final buy-stage funnel semantics are no longer owned there.

## Final Funnel Mapping

| Funnel stage field | Canonical source | Notes |
| --- | --- | --- |
| `raw_signal` | `sum(raw_buy_signal_count)` | Always aggregated from canonical diagnostics input |
| `buy_candidate_count` | `raw_buy_candidate_count` | For non-breakout routes |
| `after_held_filter_count` | `raw_after_held_filter_count` | For non-breakout routes |
| `after_slot_filter_count` | `raw_after_slot_filter_count` | `None` means stage unavailable |
| `after_cash_lot_count` | `raw_after_cash_lot_count` | `None` means stage unavailable |

### Breakout Route Normalization

For `route_id == "provider_breakout_runtime"` the final funnel semantics are centralized in `artifacts_diagnostics.py`:

- `stage_mid_count = raw_after_held_filter_count` when `candidates_count > 0` or `benchmark_regime_on`
- otherwise `stage_mid_count = 0`
- `buy_candidate_count = stage_mid_count`
- `after_held_filter_count = stage_mid_count`
- `after_slot_filter_count = stage_mid_count`
- `after_cash_lot_count = selected_count`

This preserves the current `V10.1` funnel contract while removing route-specific final semantics from execution accounting.
