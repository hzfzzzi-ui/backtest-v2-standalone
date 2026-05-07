## Why

`COMPOSE_*` and related multi-alpha constants still lived in the legacy `backtest_v2.js` placeholder. That blocked the file from fully exiting shared frontend ownership.

## What Changes

- add a formal `state/multi-alpha-constants.js` owner for shared multi-alpha constants
- update desktop page load order and frontend harness to load the formal constants module
- reduce `backtest_v2.js` to a pure placeholder

## Impact

- multi-alpha constants now have a formal owner in the main path
- `backtest_v2.js` no longer owns shared runtime or shared constants
