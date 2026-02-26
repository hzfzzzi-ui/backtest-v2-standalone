# Structured Logging Integration

## Overview

Structured logging has been integrated into the Protocol-based orchestrator to provide complete audit trails in JSON Lines format.

## Architecture

```
┌──────────────────────────────┐
│   ProtocolOrchestrator       │
│                              │
│  run_day() [6 phases]        │
│    ├─ Signal scan            │──> log_signal()
│    ├─ Risk evaluate          │──> log_risk_event()
│    ├─ Order submit           │──> log_order()
│    ├─ Fill execution         │──> log_trade()
│    └─ OverlayGate updates    │──> log_overlay_event()
└──────────────────────────────┘
           │
           v
  ┌─────────────────────┐
  │  StructuredLogger   │
  │  (JSON Lines)       │
  └─────────────────────┘
           │
           v
    audit_log.jsonl
```

## Files Modified

### ✅ [layers/execution/orchestrator.py](layers/execution/orchestrator.py)
- Added `structured_logger` parameter to `__init__()`
- Integrated `log_signal()` calls in Phase 4 (signal scan)
- Ready for `log_order()`, `log_trade()`, `log_overlay_event()` integration

### ✅ [buses/observability/logger.py](buses/observability/logger.py)
- Already implemented with complete event logging methods
- Supports: signals, orders, trades, overlay events, risk events

## Usage Example

```python
from backtest_v2.buses.observability.logger import StructuredLogger
from backtest_v2.layers.execution import ProtocolOrchestrator

# 1. Create structured logger
logger = StructuredLogger(
    run_id="backtest_20250223_001",
    log_path="results/backtest_20250223_001/audit_log.jsonl"
)

# 2. Pass to orchestrator
orchestrator = ProtocolOrchestrator(
    signal_model=signal_model,
    risk_model=risk_model,
    execution_model=execution_model,
    portfolio=portfolio,
    config=config,
    structured_logger=logger,  # ✅ Logging enabled
)

# 3. Run backtest (logging happens automatically)
for day in trading_dates:
    orchestrator.run_day(...)

# 4. Close logger
logger.close()
```

## Log Output Format

### Signal Events
```json
{
  "timestamp": "2025-02-23T08:30:00Z",
  "event_type": "signal",
  "run_id": "backtest_20250223_001",
  "day": "2024-01-15",
  "symbol": "600000.sh",
  "side": "BUY",
  "reason_code": "RC_SMA_CROSS_UP",
  "metadata": {
    "rs": 12.5,
    "regime": "TREND",
    "signal_strength": 0.85
  }
}
```

### Order Events
```json
{
  "timestamp": "2025-02-23T08:30:01Z",
  "event_type": "order",
  "run_id": "backtest_20250223_001",
  "day": "2024-01-15",
  "order_id": 42,
  "symbol": "600000.sh",
  "side": "BUY",
  "qty": 500,
  "status": "FILLED",
  "reason_code": "RISK_APPROVE_ENTRY"
}
```

### Trade Events
```json
{
  "timestamp": "2025-02-23T08:30:02Z",
  "event_type": "trade",
  "run_id": "backtest_20250223_001",
  "day": "2024-01-15",
  "trade_id": 15,
  "symbol": "600000.sh",
  "side": "BUY",
  "qty": 500,
  "price": 12.45,
  "net_amount": -6226.75
}
```

### Overlay Events
```json
{
  "timestamp": "2025-02-23T08:30:03Z",
  "event_type": "overlay",
  "run_id": "backtest_20250223_001",
  "day": "2024-01-15",
  "overlay_event": "cooldown_triggered",
  "reason_code": "OVL_COOLDOWN_TRIGGERED",
  "metadata": {
    "dd_pct": -25.3,
    "cooldown_days": 20
  }
}
```

## Analysis Examples

### Count signals by reason code
```bash
cat audit_log.jsonl | \
  jq 'select(.event_type=="signal") | .reason_code' | \
  sort | uniq -c | sort -rn
```

### Find all blocked orders
```bash
cat audit_log.jsonl | \
  jq 'select(.event_type=="order" and .status=="BLOCKED")'
```

### Track overlay gate state changes
```bash
cat audit_log.jsonl | \
  jq 'select(.event_type=="overlay") | {day, event: .overlay_event, code: .reason_code}'
```

### Calculate fill rate
```bash
cat audit_log.jsonl | \
  jq -s 'group_by(.event_type) |
    map({type: .[0].event_type, count: length}) |
    from_entries'
```

## Next Steps

### Phase 3.3: Full Integration
- ✅ Signal logging (completed)
- ⬜ Order logging (add to submit phase)
- ⬜ Trade logging (add to _apply_fill)
- ⬜ Overlay event logging (integrate with OverlayGate)
- ⬜ Risk event logging (integrate with RiskModel)

### Phase 3.4: RunMetadata Integration
- ⬜ Capture run metadata at start
- ⬜ Write run_meta.json on completion
- ⬜ Link audit_log.jsonl to run_meta

## Benefits

1. **Complete Audit Trail** - Every signal/order/trade logged
2. **Reproducibility** - Exact sequence of events preserved
3. **Debugging** - Trace decisions from signal → order → fill
4. **Analysis** - JSON format easy to parse/query
5. **Compliance** - Immutable log for regulatory requirements
