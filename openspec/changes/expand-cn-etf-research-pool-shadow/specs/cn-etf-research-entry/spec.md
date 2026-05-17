## ADDED Requirements

### Requirement: cn_etf research entry MUST support a controlled shadow pool preset
`cn_etf` research entry MUST support `cn_etf_research_shadow_pool_v1` as a controlled research-only preset. The preset SHALL expand only through the ETF catalog whitelist and SHALL NOT bypass catalog validation with raw ad hoc symbols.

#### Scenario: shadow pool preset expands through catalog
- **WHEN** 用户选择 `cn_etf_research_shadow_pool_v1`
- **THEN** universe resolver MUST expand it through ETF catalog entries
- **THEN** run metadata MUST expose `etf_batch = cn_etf_research_shadow_pool_v1`
- **THEN** unsupported symbols MUST fail catalog validation instead of entering the research universe silently

### Requirement: cn_etf research entry MUST expose formal, shadow, and deferred classifications
`cn_etf` research entry MUST expose per-symbol classification so downstream audit can distinguish formal ETF scope, research-only shadow candidates, and deferred candidates.

#### Scenario: research metadata is emitted for mixed ETF candidates
- **WHEN** `cn_etf` research entry materializes an ETF candidate set
- **THEN** metadata MUST include `formal_scope_symbols`
- **THEN** metadata MUST include `shadow_symbols` and their role map when a shadow preset is selected
- **THEN** metadata MUST include deferred or rejected symbols with reason codes when requested symbols are not eligible for the selected preset

### Requirement: shadow research entry MUST preserve ETF data truth boundaries
Shadow ETF research MUST continue to use the ETF daily truth table and ETF catalog lineage. It SHALL NOT fall back to stock PIT membership, stock V2 canonical tables, or frontend-derived symbol lists.

#### Scenario: shadow pool run builds its data bundle
- **WHEN** a study runs with `asset_scope = cn_etf` and `cn_etf_research_shadow_pool_v1`
- **THEN** the data bundle MUST use `pams_cn_etf_daily`
- **THEN** run metadata MUST expose ETF coverage evidence
- **THEN** stock PIT lineage SHALL NOT be emitted as the truth source for the ETF universe
