## ADDED Requirements

### Requirement: ETF beta sleeve MUST isolate formal scope from shadow research pools
The formal ETF beta sleeve MUST treat research shadow pools as non-formal inputs unless an explicit formal pool version change promotes those symbols. Shadow pool symbols SHALL NOT be included in formal selected ETFs, formal weak-state defense targets, or live baseline truth by default.

#### Scenario: formal sleeve receives shadow pool metadata
- **WHEN** ETF beta sleeve runtime receives metadata for `cn_etf_research_shadow_pool_v1`
- **THEN** formal view MUST keep `formal_pool_version = formal_etf_pool_v1`
- **THEN** formal selected ETFs MUST remain within the current formal scope
- **THEN** shadow candidates MAY appear only in research diagnostics or explicit shadow study outputs

### Requirement: ETF beta sleeve audit MUST reject silent shadow promotion
ETF beta sleeve audit MUST fail or warn when a symbol classified as research-only shadow appears in formal ETF outputs without a matching formal pool version change.

#### Scenario: shadow ETF appears in formal selected output
- **WHEN** `510880.SH`, `518880.SH`, `159915.SZ`, `588000.SH`, `512890.SH` or `159845.SZ` appears in formal selected ETFs
- **AND** the active formal pool version is still `formal_etf_pool_v1`
- **THEN** audit MUST emit a shadow promotion violation
- **THEN** the violation MUST identify the offending symbol and required formal pool version change
