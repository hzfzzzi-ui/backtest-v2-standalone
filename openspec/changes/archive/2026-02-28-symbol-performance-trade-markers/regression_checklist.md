# Symbol Performance + Trade Markers Regression Checklist

## Scope
- Frontend symbol performance list, filter, and sorting
- Main chart portfolio/symbol mode switch
- Buy/sell markers overlay in symbol mode
- Backward compatibility for old experiment artifacts

## Cases
1. New experiment with `symbol_performance.csv` present:
   - `wbSymbolPerfBody` renders rows.
   - Default sort is `return_desc`.
   - Clicking a row switches chart mode to `symbol`.

2. Symbol filter and sort:
   - Typing in `wbSymbolFilter` narrows rows by `symbol` substring.
   - `wbSymbolSort=drawdown_asc` and `trades_desc` reorder rows correctly.

3. Symbol mode chart:
   - `wbChartMode=symbol` loads `/api/backtest_v2/series/symbol`.
   - Main line changes to selected symbol.
   - Benchmark toggle still controls benchmark K-line overlay.

4. Trade markers:
   - BUY renders green `arrowUp`.
   - SELL renders red `arrowDown`.
   - Only selected symbol markers are shown.

5. Approximation hint:
   - `wbSymbolPerfHint` shows unrealized approximation note.
   - If fallback valuation exists, hint includes fallback count.

6. Old experiment compatibility:
   - Missing `symbol_performance` does not block page.
   - Symbol panel shows empty state, core KPI/chart still render.

