## MODIFIED Requirements

### Requirement: Governed ETF phase1 defense sleeve MUST use a capital-real defense asset in defensive states
The governed ETF phase1 contract MUST treat `511010.SH` as the formal limited-defense asset so that `TRANS_DOWN` and `RISK_OFF` can maintain persistent defense capital instead of relying on one-off transition orders.

#### Scenario: default governed ETF contract is built
- **WHEN** the default governed ETF beta contract is built
- **THEN** `limited_defense_candidates` MUST include `511010.SH`
- **AND** `defense_asset_weights` MUST allocate the phase1 defense bucket to `511010.SH`

#### Scenario: formal phase1 scope is evaluated
- **WHEN** formal phase1 scope and alignment are evaluated
- **THEN** `511010.SH` MUST be inside formal limited-defense scope
- **AND** `511010.SH` MUST NOT appear in formal excluded symbols
- **AND** defensive-state targets using `511010.SH` MUST be treated as in-scope formal allocation
