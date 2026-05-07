# csi800-formal-history-materialization Specification

## Purpose

Define the formal capability boundary for `csi800-formal-history-materialization` in the current mainline.
## Requirements
### Requirement: CSI800 姝ｅ紡鍘嗗彶閾剧墿鍖?
绯荤粺 MUST 鎻愪緵 `CSI800/000906.SH` 姝ｅ紡鍘嗗彶閾剧墿鍖栬兘鍔涳紝鑳藉浠庤鐩?`2007+` 鐨勯暱鍘嗗彶 seed 鍜屽彲閫夊熬閮?patch 鐢熸垚鍗曚竴 formal chain锛屽苟杈撳嚭鍙璁＄殑 provenance/coverage 鎽樿銆?

绯荤粺 MUST 鎻愪緵 `CSI800/000906.SH` 姝ｅ紡鍘嗗彶閾剧墿鍖栬兘鍔涳紝鑳藉浠庤鐩?`2007+` 鐨勯暱鍘嗗彶 seed 鍜屽彲閫夊熬閮?patch 鐢熸垚鍗曚竴 formal chain锛屽苟杈撳嚭鍙璁＄殑 provenance/coverage 鎽樿銆?

#### Scenario: 鐢ㄩ暱鍘嗗彶 seed 鐗╁寲姝ｅ紡閾?
- **WHEN** 杩愮淮鎻愪緵瑕嗙洊 `2007+` 鐨?`000906.SH` seed CSV 浠ョ敓鎴愭寮忓巻鍙查摼
- **THEN** 绯荤粺 MUST 杈撳嚭鍙洿鎺ュ鍏?`pit_index_constituents` 鐨?`changes.csv`
- **THEN** 杈撳嚭璁板綍鐨?`source` MUST 缁熶竴涓哄崟涓€ formal source label
- **THEN** summary MUST 鍖呭惈 seed/patch 鏉ユ簮銆佹渶鏃╄捣鐐广€佹渶鏅氱粓鐐瑰拰鏄惁瑕嗙洊 `required_start`

#### Scenario: 鐢?patch 鏇挎崲 seed 灏鹃儴
- **WHEN** 杩愮淮鍚屾椂鎻愪緵 seed CSV 鍜?patch CSV
- **THEN** 绯荤粺 MUST 浠呬粠 patch 鏈€鏃?`start_date` 璧锋浛鎹?seed 灏鹃儴
- **THEN** 绯荤粺 MUST 淇濈暀 patch 杈圭晫涔嬪墠鐨勯暱鍘嗗彶璁板綍
- **THEN** summary MUST 鏄庣‘杈撳嚭 patch 杈圭晫鍜屾渶缁堟寮忛摼缁熻

