## Attribution Contract

This study treats entry quality as a descriptive layer, not as a trading rule.

Entry-time features:

- `ret20`, `ret60`, `ret120`: how much the stock already rose before entry.
- `ret20_share_of_ret120`: whether the move was mostly recent acceleration.
- `ma120_distance`: how far price is above the long trend line.
- `high60_distance`: whether entry is near a 60-day high or extended above it.
- `vol20`: recent daily volatility.
- `drawdown60`: recent pullback severity before entry.
- `avg_turnover20`: liquidity.
- `membership_bucket`: `csi800_only`, `csi1000_new`, `overlap`, `unclassified`.

Outcome labels:

- forward return over 20 and 60 trading days;
- MFE and MAE over 20 and 60 trading days;
- realized holding result when the entry is later fully sold.

## Interpretation Discipline

The study should not look for one magic threshold. It should answer:

- Which visible entry shapes are repeatedly associated with poor outcomes?
- Are failures concentrated in CSI1000, low liquidity, extended entries, or
  weak follow-through paths?
- Are there combinations that explain losses better than any single factor?

## Output

Outputs are written under:

`outputs/studies/cn_stock/simple_entry_quality_attribution_v1/`

Expected files:

- `entries.csv`
- `single_factor_summary.csv`
- `pair_factor_summary.csv`
- `summary.json`
- `summary.md`
