## Context

The current system already has useful research components:

- M1 market/style state shadow output.
- Industry health by申万一级行业.
- Rotation pressure over held positions and candidates.
- Current stock-leg trade/path outputs.

This design does not replace those components. It uses them to evaluate whether
a new top-down strategy architecture is worth implementing later.

## Candidate Architecture

### Layer 1: Market State

Market state determines gross exposure permission.

Initial shadow labels:

- `risk_on`: broad/index trend is supportive.
- `neutral`: market is mixed; allow reduced exposure.
- `risk_off`: market is deteriorating; no new stock risk.

The first shadow phase may derive this from existing `style_state_label` and
market/industry breadth outputs. It must record the source fields used.

### Layer 2: Industry Permission

Industry state determines whether a stock can be held or newly bought.

Initial shadow labels:

- `allow`: industry is healthy/strong.
- `watch`: industry is mixed or deteriorating.
- `block`: industry is weak.

The first shadow phase may derive this from
`industry_health_by_industry_daily.csv` and held/candidate industry pressure
outputs. It must not use future return columns.

### Layer 3: Stock Execution Eligibility

Stock eligibility is only evaluated after market and industry gates.

Initial shadow labels:

- `eligible`: market allows risk and industry is allow/watch.
- `reduced`: market is neutral or industry is watch.
- `blocked`: market risk-off or industry block.

This layer should replay the current stock-leg trade/path samples and ask:

- Which losing trades would have been blocked or reduced?
- Which winning trades would have been wrongly blocked or reduced?
- Which recent 2025-2026 loss clusters are explained by state deterioration?

## First Shadow Study

The first implementation should be diagnostic only.

Inputs:

- `outputs/studies/cn_stock_etf/cn_stock_style_industry_state_switch_shadow_v1/<window>/M1_STYLE_STATE/machine/*.csv`
- current stock-leg trade/path detail artifacts
- recent industry path audit outputs when available

Windows:

- `2016-2026`: main development window
- `2012-2017`: hard-gate window
- `2012-2026`: full audit window
- optional recent `2025-2026` lens

Outputs:

- daily state table
- trade-level state audit
- industry-level state audit
- false-positive/false-negative summary
- human report with continue/reject/hold recommendation

## Acceptance

Continue to AB design only if the shadow proves:

- loss filtering is not concentrated in one year or one industry only;
- blocked/reduced losers materially exceed blocked/reduced winners;
- 2025 computer/basic-chemical drag is explained better than by local exit
  patches alone;
- hard-gate window does not show obvious overblocking of major winners;
- all state labels are explainable from same-day or prior-day inputs.

## Risks

- State labels can become a hidden overfit surface if too many regimes are
  introduced.
- Industry gates can miss stock-led turns where the stock leads the industry.
- If market state is too slow, this becomes another lagging diagnostic rather
  than an executable strategy.
