# cn-etf-research-mainline Specification

## Purpose

Define the formal capability boundary for `cn-etf-research-mainline` in the current mainline.
## Requirements
### Requirement: 绯荤粺 MUST 鎻愪緵 research-only 鐨?ETF 鐙珛鏀剁泭涓荤嚎 R1
绯荤粺 MUST 鎻愪緵涓€鏉″悕涓?`etf/cn_broad_based_research_mainline_r1` 鐨?research-only ETF 涓荤嚎 study銆傝涓荤嚎 MUST 鏄庣‘琚爣璁颁负鐙珛鏀剁泭鐮旂┒绾匡紝鑰屼笉鏄?formal `cn-etf-beta-sleeve` 鎴?stock+ETF combo 鐨勬寮忛敋鐐广€?
#### Scenario: 鐮旂┒鍏ュ彛瑁呰浇 R1 涓荤嚎
- **WHEN** 鐢ㄦ埛鍔犺浇 `etf/cn_broad_based_research_mainline_r1`
- **THEN** 绯荤粺 MUST 灏嗗叾璇嗗埆涓?`research-only` 鐨?ETF 鐙珛鏀剁泭涓荤嚎
- **THEN** 绯荤粺 SHALL NOT 灏嗗叾瑙ｉ噴涓?formal ETF sleeve 鎴?baseline 姝ｅ紡閿氱偣

### Requirement: R1 涓荤嚎 MUST 浣跨敤鍙楁帶鐩綍鍐呯殑 A鑲℃牳蹇冩壙鎺?+ 鍥哄畾绉戝垱鎴愰暱甯綅 + 鍙岄槻瀹堝眰
R1 涓荤嚎 MUST 浠呬娇鐢ㄥ綋鍓?`cn_etf` 鍙楁帶 research entry 宸茶鐩栫殑 ETF锛屽苟鎸変互涓嬭鑹插垎灞傦細

- A鑲℃牳蹇冩壙鎺ワ細`510050.SH`銆乣510300.SH`銆乣510500.SH`銆乣512100.SH`銆乣512890.SH`
- 鍥哄畾鎴愰暱甯綅锛歚588000.SH`
- 闃插畧灞傦細`511010.SH`銆乣518880.SH`

R1 涓荤嚎 SHALL NOT 鍚屾椂鍚敤 `159915.SZ` 浣滀负骞跺垪 growth seat銆?
#### Scenario: R1 涓荤嚎鍔犺浇璧勪骇瑙掕壊
- **WHEN** 绯荤粺鐗╁寲 R1 涓荤嚎鐨?study 閰嶇疆
- **THEN** `588000.SH` MUST 琚爣璁颁负鍞竴 growth seat
- **THEN** `511010.SH` 涓?`518880.SH` MUST 鍙綔涓洪槻瀹堝眰鑰屼笉浣滀负椋庨櫓寮€鏃剁殑杩涙敾鎺掑悕鎴愬憳

### Requirement: R1 涓荤嚎 MUST 閲囩敤鍙屽懆 `core_growth_slot` 閫夋嫨缁撴瀯
R1 涓荤嚎 MUST 浣跨敤 `core_growth_slot` 浣滀负閫夋嫨閾撅紝骞朵娇鐢?`biweekly` 璋冧粨棰戠巼銆傚己鐘舵€佷笅绯荤粺 MUST 鍏佽 `core + growth` 鍙屽腑浣嶏紱寮辩姸鎬佷笅锛屽綋 `target_selected_count=1` 鏃讹紝绯荤粺 MUST 鍙繚鐣?core slot銆?
#### Scenario: 寮虹姸鎬佸厑璁稿弻甯綅
- **WHEN** R1 涓荤嚎澶勪簬 `BULL` 鎴?`TRANS_UP`锛屼笖 `target_selected_count >= 2`
- **THEN** 绯荤粺 MUST 鍏佽鍚屾椂閫夋嫨 `core slot` 涓?`growth slot`
- **THEN** `growth slot` MUST 鍙潵鑷?`588000.SH`

#### Scenario: 寮辩姸鎬佸帇鎺?growth slot
- **WHEN** R1 涓荤嚎澶勪簬 `TRANS_DOWN` 鎴?`RISK_OFF`锛屼笖 `target_selected_count = 1`
- **THEN** 绯荤粺 MUST 鍙繚鐣?`core slot`
- **THEN** 绯荤粺 SHALL NOT 鍦ㄨ鐘舵€佷笅鎶?`588000.SH` 浣滀负鍞竴 live seat

### Requirement: R1 涓荤嚎 MUST 鏀寔寮卞競鏍稿績鎵挎帴涓庡弻闃插畧鍏卞瓨
R1 涓荤嚎 MUST 鍏佽 `LIGHT`銆乣TRANS_DOWN` 涓?`RISK_OFF` 缁х画淇濈暀姝ｇ殑 A鑲℃牳蹇冩壙鎺ラ绠楋紝浣?`RISK_OFF` 鐨?live 椋庨櫓鏆撮湶 MUST 琚檺鍒朵负鍗曚竴 core seat銆傜郴缁熷悓鏃?MUST 鏀寔 `511010.SH + 518880.SH` 鍙岄槻瀹堝眰锛屼互鍙婁互 `511010.SH` 浣滀负鍗?symbol fallback銆?
#### Scenario: RISK_OFF 浠嶄繚鐣欏皬骞呮牳蹇冩壙鎺?- **WHEN** R1 涓荤嚎澶勪簬 `RISK_OFF`
- **THEN** 绯荤粺 MUST 鍏佽瀛樺湪姝ｇ殑 `target_exposure`
- **THEN** 璇ユ棰勭畻 MUST 鍙搴斿崟涓€ core seat锛岃€屼笉鏄垚闀垮腑浣嶆垨鍙岄闄╁腑浣?
#### Scenario: 鍙岄槻瀹堝眰涓?fallback 骞跺瓨
- **WHEN** R1 涓荤嚎杩涘叆寮辩姸鎬佸苟闇€瑕侀槻瀹堝眰
- **THEN** 绯荤粺 MUST 鏀寔鍚屾椂閰嶇疆 `limited_defense_candidates=[511010.SH, 518880.SH]`
- **THEN** 绯荤粺 MUST 缁х画鍏佽 `fallback_mode=single_symbol` 涓?`fallback_symbol=511010.SH`


