## Design

### Goal

Test `monthly_divergence_rate` as a **bounded candidate-band rerank** without replacing the live residual ranking shell.

### Contract

`asset_context.moneyflow_overlay` gains:

- `mode = band_rerank`
- `band_limit` (required, integer >= 2)

Allowed semantics:

- factor role: `rank`
- apply layer: `candidate` or `ranking`

### Runtime behavior

1. baseline main ranking still sorts all candidates by the current live `mf_score / final_score`
2. when `band_rerank` is active:
   - take the first `band_limit` candidates from the baseline-ranked list
   - rerank only that prefix by `overlay_score` descending
   - use baseline rank as fallback tiebreak
   - keep the suffix outside the band unchanged
3. selection, exits, market filter, benchmark regime, and risk budget remain unchanged

### Diagnostics

Candidate plan debug output records:

- `moneyflow_overlay_band_limit`
- `moneyflow_overlay_rerank_count`

Candidate rows keep:

- `mf_rank` as the baseline rank
- `final_score_rank` as the post-rerank rank

This keeps the rerank auditable.

### Study shape

`v10/moneyflow_monthly_band_rerank_s1` uses:

- `B0`
- `MF_BAND20`

with the existing runtime-config-backed monthly moneyflow snapshot source.
