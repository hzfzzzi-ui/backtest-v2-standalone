# Spec: Stock Trend Filter

## Requirement
Only buy stocks where: `close > MA60 AND MA20 > MA60`. Both conditions checked independently per stock per day.

## Behavior
- MA20: 20-day simple moving average of close
- MA60: 60-day simple moving average of close
- If either condition fails, stock is excluded from buy candidates
- Applied as pre-filter before entry signal evaluation
- Does NOT affect existing positions (sell signals unaffected)
- First 60 trading days of data: stock automatically excluded (insufficient MA60 data)

## Parameters
| Param | Default | Range |
|-------|---------|-------|
| `enable_v2_trend_filter` | false | bool |
| `v2_trend_short_ma` | 20 | 5-60 |
| `v2_trend_long_ma` | 60 | 20-250 |

## Edge Cases
- Suspended stocks: tradable=False already filters them; MA uses forward-filled close
- MA20 > MA60 does NOT strictly imply close > MA60 (intraday drop possible), so both checked
