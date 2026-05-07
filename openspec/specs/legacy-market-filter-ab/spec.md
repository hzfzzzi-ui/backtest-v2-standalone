# legacy-market-filter-ab Specification

## Purpose

Define the formal capability boundary for `legacy-market-filter-ab` in the current mainline.
## Requirements
### Requirement: Legacy 甯傚満杩囨护 A/B 搴忓垪瀹為獙

绯荤粺 SHALL 鏀寔鍩轰簬 `baseline_V10.2` 鎵ц涓€涓笁姝ユ渶灏?A/B 搴忓垪瀹為獙锛岀敤浜庨獙璇?legacy 杩囨浮闃舵鎵ц鏄惁杩囧锛?

1. **AB1**锛氬彧鎷嗗垎 `TRANS_UP / TRANS_DOWN` multiplier
2. **AB2**锛氬湪 AB1 鍩虹涓婂惎鐢?`freeze_trans_up_entries`
3. **AB3**锛氬湪 AB2 鍩虹涓婂皢 `long_ma_window` 浠?`200` 璋冧负 `160`

姣忎竴杞疄楠?MUST 浠庡悓涓€浠?`baseline_V10.2` 鍩哄噯閰嶇疆鍏嬮殕锛屽苟淇濊瘉 intended diff 浠呭寘鍚杞柊澧炲彉閲忋€?

绯荤粺 SHALL 鏀寔鍩轰簬 `baseline_V10.2` 鎵ц涓€涓笁姝ユ渶灏?A/B 搴忓垪瀹為獙锛岀敤浜庨獙璇?legacy 杩囨浮闃舵鎵ц鏄惁杩囧锛?

1. **AB1**锛氬彧鎷嗗垎 `TRANS_UP / TRANS_DOWN` multiplier
2. **AB2**锛氬湪 AB1 鍩虹涓婂惎鐢?`freeze_trans_up_entries`
3. **AB3**锛氬湪 AB2 鍩虹涓婂皢 `long_ma_window` 浠?`200` 璋冧负 `160`

姣忎竴杞疄楠?MUST 浠庡悓涓€浠?`baseline_V10.2` 鍩哄噯閰嶇疆鍏嬮殕锛屽苟淇濊瘉 intended diff 浠呭寘鍚杞柊澧炲彉閲忋€?

#### Scenario: AB1 intended diff
- **WHEN** 杩愯 AB1
- **THEN** 鐩稿 baseline 鐨?intended diff SHALL 浠呭寘鍚?`trans_down_multiplier` 涓?`trans_up_multiplier`

#### Scenario: AB2 intended diff
- **WHEN** 杩愯 AB2
- **THEN** 鐩稿 AB1 鐨?intended diff SHALL 浠呭寘鍚?`freeze_trans_up_entries = true`

#### Scenario: AB3 intended diff
- **WHEN** 杩愯 AB3
- **THEN** 鐩稿 AB2 鐨?intended diff SHALL 浠呭寘鍚?`long_ma_window = 160`### Requirement: Legacy 甯傚満杩囨护 A/B 浜х墿

绯荤粺 SHALL 涓鸿搴忓垪瀹為獙杈撳嚭姝ｅ紡瀵圭収浜х墿锛岃嚦灏戝寘鎷細
- `summary.json`
- `report.md`
- `performance_comparison.csv`

浜х墿 MUST 璇存槑锛?
- baseline / AB1 / AB2 / AB3 鐨勫疄楠?ID
- 姣忕粍 intended diff
- 鏀剁泭銆佸勾鍖栥€丼harpe銆佹渶澶у洖鎾ゃ€佷氦鏄撴暟
- 椋庨櫓銆侀獙璇佷笌鍥為€€璺緞

#### Scenario: 姝ｅ紡瀵圭収浜х墿瀹屾暣
- **WHEN** 搴忓垪 A/B 杩愯瀹屾垚
- **THEN** 杈撳嚭鐩綍 SHALL 鍚屾椂鍖呭惈 `summary.json`銆乣report.md`銆乣performance_comparison.csv`

### Requirement: Legacy 甯傚満杩囨护 A/B 浜х墿

绯荤粺 SHALL 涓鸿搴忓垪瀹為獙杈撳嚭姝ｅ紡瀵圭収浜х墿锛岃嚦灏戝寘鎷細
- `summary.json`
- `report.md`
- `performance_comparison.csv`

浜х墿 MUST 璇存槑锛?
- baseline / AB1 / AB2 / AB3 鐨勫疄楠?ID
- 姣忕粍 intended diff
- 鏀剁泭銆佸勾鍖栥€丼harpe銆佹渶澶у洖鎾ゃ€佷氦鏄撴暟
- 椋庨櫓銆侀獙璇佷笌鍥為€€璺緞

#### Scenario: 姝ｅ紡瀵圭収浜х墿瀹屾暣
- **WHEN** 搴忓垪 A/B 杩愯瀹屾垚
- **THEN** 杈撳嚭鐩綍 SHALL 鍚屾椂鍖呭惈 `summary.json`銆乣report.md`銆乣performance_comparison.csv`

