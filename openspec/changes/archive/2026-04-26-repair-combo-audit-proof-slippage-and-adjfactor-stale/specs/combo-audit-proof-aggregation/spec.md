## ADDED Requirements

### Requirement: 组合层必须正式聚合 component timing 证明链
系统 SHALL 在 `unified_combo_phase1` 组合 audit 中复用 stock / ETF component 的 `timing_alignment` 结果，而不是只按组合 shell 名称做硬判断。

#### Scenario: 组合层通过 component `NEXT_OPEN` 证明链
- **WHEN** 组合结果目录可解析出 stock / ETF component 的 `run_meta.json`，且两个 component 的 `timing_alignment` 都是 `PASS`
- **THEN** 组合层 `timing_alignment` MUST 返回 `PASS`

#### Scenario: component timing 证据缺失时不允许误判通过
- **WHEN** 任一 component 的 timing 证据缺失或不是 `PASS`
- **THEN** 组合层 `timing_alignment` MUST 返回 `WARN` / `UNKNOWN` / `FAIL`，不得直接返回 `PASS`

### Requirement: 组合层必须正式聚合 component universe lineage 证明链
系统 SHALL 在 `unified_combo_phase1` 组合 audit 中显式聚合 stock `PIT_DYNAMIC` 与 ETF `DIRECT_SYMBOLS` 证明链。

#### Scenario: stock 与 ETF lineage 都通过时组合层通过
- **WHEN** stock component 的 `universe_lineage` 是 `PASS`，且 ETF component 的 `universe_lineage` 是 `PASS`
- **THEN** 组合层 `universe_lineage` MUST 返回 `PASS`

#### Scenario: component lineage 失败时组合层失败
- **WHEN** 任一 component 的 `universe_lineage` 是 `FAIL`
- **THEN** 组合层 `universe_lineage` MUST 返回 `FAIL`
