# V2 Stage 2: Market Regime MA60

## What
Change the market regime filter default from MA120 to MA60, and ensure HS300 > MA60 is the canonical market gate. This is V2 Stage 2 (Market Regime).

## Why
MA120 is too slow for A-share market cycles. MA60 provides better responsiveness while still filtering bear markets. The rule: if HS300 close < MA60, prohibit all new entries.

## Current State
`regime_ma` defaults to 120 in `portfolio_simulator_strict.py`. The logic is fully implemented — this is primarily a parameter default change plus config wiring verification.

## Scope
- Change `regime_ma` default from 120 to 60
- Verify all engine paths (SMA, Generic, RegimeRouter) respect this
- Ensure API and frontend correctly expose `regime_ma` parameter
