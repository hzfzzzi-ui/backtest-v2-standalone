# cn-etf-single-leg-architecture Specification

## Purpose

Define the formal capability boundary for `cn-etf-single-leg-architecture` in the current mainline.
## Requirements
### Requirement: ETF 鍗曡吙蹇呴』閫氳繃绋冲畾 facade 淇濈暀鏃㈡湁鍏ュ彛

绯荤粺 MUST 鍦ㄧ涓€杞噸鏋勪腑淇濈暀 ETF 鍗曡吙鐨勬棦鏈夊叕寮€鍏ュ彛锛屼娇澶栭儴璋冪敤鐐规棤闇€鍚岃疆淇敼 import銆傚唴閮ㄥ疄鐜?MAY 杩佺Щ鍒版柊鐨?ETF 瀛愭ā鍧楋紝浣嗘棫鍏ュ彛鏂囦欢 SHALL 閫€鍖栦负 facade 鎴?re-export銆?
#### Scenario: Contract 鍏ュ彛淇濇寔绋冲畾

- **WHEN** 璋冪敤鏂圭户缁粠 `backend/core/config/etf_beta_contract.py` 瀵煎叆 ETF contract 鐩稿叧鍏紑鍑芥暟
- **THEN** 绯荤粺 MUST 缁х画鎻愪緵杩欎簺鍏紑绗﹀彿
- **THEN** 鏃ф枃浠?MUST 鍙壙鎷?facade 鎴?re-export 璐ｄ换锛岃€屼笉鏄户缁壙杞藉叏閮ㄥ疄鐜?
#### Scenario: Provider 鍏ュ彛淇濇寔绋冲畾

- **WHEN** 璋冪敤鏂圭户缁粠 `backend/core/engine_vector/cn_etf_beta_signal_provider.py` 瀵煎叆 `CNETFBetaSignalProvider`
- **THEN** 绯荤粺 MUST 缁х画鎻愪緵鐩稿悓绫诲悕涓庣ǔ瀹氳繍琛屽叆鍙?- **THEN** 澶栭儴 runtime 璋冪敤閾?SHALL NOT 鍥犲唴閮ㄥ瓙妯″潡鎷嗗垎鑰岃杩悓姝ヨ縼绉?
### Requirement: ETF 鍚堝悓瀹炵幇蹇呴』鎷嗗垎涓洪粯璁ゅ€笺€佸綊涓€鍖栥€佹毚闇茶涔夊拰 summary 杈圭晫

绯荤粺 MUST 灏?ETF 鍗曡吙鍚堝悓瀹炵幇鎷嗗垎涓鸿亴璐ｅ崟涓€鐨勫瓙妯″潡锛岃嚦灏戣鐩栭粯璁ゅ€笺€佸綊涓€鍖栥€佹毚闇茶涔夊拰 summary 鍥涚被杈圭晫銆傚悎鍚屽眰 SHALL 淇濇寔鈥滆緭鍏ユ竻娲椻€濆拰鈥滃悎鍚屾眰瑙ｂ€濆垎绂伙紝summary 閫昏緫 SHALL NOT 缁х画鍙嶅悜姹℃煋鍚堝悓姹傝В涓昏矾寰勩€?
#### Scenario: 榛樿鍊间笌褰掍竴鍖栨湁鐙珛 owner

- **WHEN** 绯荤粺闇€瑕佹瀯寤?ETF 榛樿 contract 鎴栨竻娲?governed `etf_beta` 閰嶇疆
- **THEN** 榛樿鍊间笌褰掍竴鍖栭€昏緫 MUST 鍒嗗埆鐢变笓灞炲瓙妯″潡璐熻矗
- **THEN** 鏆撮湶璇箟妯″潡 SHALL 浠呮秷璐瑰綊涓€鍖栧悗鐨勮緭鍏ワ紝鑰屼笉鏄噸澶嶅吋瀹瑰師濮嬮厤缃櫔澹?
#### Scenario: 鏆撮湶璇箟涓?summary 涓嶅啀娣峰湪鍚屼竴 owner

- **WHEN** 绯荤粺闇€瑕佽绠?`target_exposure`銆乣deployment_pace`銆乥ucket target 鎴?phase1 summary
- **THEN** 鏆撮湶璇箟涓?summary MUST 鐢变笉鍚屽瓙妯″潡鍒嗗埆璐熻矗
- **THEN** `summary` 缁勮 SHALL NOT 缁х画鍦ㄥ悎鍚岀儹鐐归噷鐩存帴娣峰啓鎵ц璇箟

### Requirement: ETF provider 瀹炵幇蹇呴』鎷嗗垎涓洪厤缃閰嶃€侀€夋嫨銆佹墽琛岃矾寰勫拰璇婃柇鑱氬悎

绯荤粺 MUST 灏?ETF provider 鐨勫唴閮ㄥ疄鐜版媶鍒嗕负鍙嫭绔嬬淮鎶ょ殑杈圭晫锛岃嚦灏戝寘鍚厤缃閰嶃€乸rovider state owner銆佸€欓€夋睜/鎺掑簭閫夋嫨銆佹墽琛岃矾寰勫拰璇婃柇鑱氬悎銆俻rovider facade SHALL 鍙繚鐣欑ǔ瀹氬崗璁笌璋冨害鑱岃矗銆?
#### Scenario: Provider state 涓庨厤缃閰嶅厛浜庤矾寰勬媶鍒?
- **WHEN** 绯荤粺寮€濮嬫媶鍒?ETF provider
- **THEN** 绯荤粺 MUST 鍏堝缓绔嬮泦涓寲鐨?provider config 涓?state owner
- **THEN** 鍚庣画閫夋嫨銆佹墽琛屽拰璇婃柇妯″潡 MUST 閫氳繃璇?owner 璁块棶鍏变韩鐘舵€侊紝鑰屼笉鏄户缁墿鏁ｆ柊鐨勯殣寮?`self` 瀛楁

#### Scenario: 鎵ц璺緞涓嶅啀涓庤瘖鏂嫾瑁呮贩鍐?
- **WHEN** 绯荤粺澶勭悊 monthly rebalance銆乣TRANS_UP` redeploy 鎴栧叾浠?ETF 鎵ц璺緞
- **THEN** 鎵ц璺緞妯″潡 MUST 璐熻矗涔板崠鍐崇瓥涓庝笅鍗曡矾寰?- **THEN** 璇婃柇妯″潡 MUST 鐙珛璐熻矗 reason code銆乪xecution path 鏍囩鍜?gap 璇佹嵁鑱氬悎

### Requirement: ETF actual exposure 涓?formal-research view 蹇呴』閫氳繃涓撳睘 accounting 杈圭晫杈撳嚭

绯荤粺 MUST 涓?ETF 鍗曡吙寤虹珛涓撳睘 accounting 杈圭晫锛岀粺涓€杈撳嚭 actual exposure銆乸olicy/timing/residual gap 鍜?formal/research view銆傞€氱敤 `daily_accounting.py` SHALL 浠呬繚鐣欑紪鎺掕亴璐ｏ紝涓嶅緱缁х画闀挎湡鎵胯浇 ETF 棰嗗煙瑙ｉ噴鐪熺浉銆?
#### Scenario: 閫氱敤 daily accounting 濮旀墭 ETF 涓撳睘 accounting

- **WHEN** stage pipeline 鍦?ETF 鍗曡吙杩愯涓敓鎴愭棩绾?accounting
- **THEN** `daily_accounting.py` MUST 灏?ETF actual exposure 涓?gap 瑙ｉ噴濮旀墭缁?ETF 涓撳睘 accounting 妯″潡
- **THEN** 閫氱敤璁拌处鐑偣 SHALL NOT 缁х画鐩存帴鎷艰 ETF formal/research view 缁嗚妭

#### Scenario: Gap 瑙ｉ噴鍏变韩鍚屼竴浠?ETF accounting 鐪熺浉

- **WHEN** research audit銆乫ormal audit 鎴?artifact 鍥哄寲灞傛秷璐?ETF 鐨?target/actual 宸紓瑙ｉ噴
- **THEN** `pace_policy_gap`銆乣rebalance_timing_gap` 鍜?`execution_residual_gap` MUST 鏉ヨ嚜鍚屼竴 ETF accounting 杈圭晫
- **THEN** 绯荤粺 SHALL NOT 鍦ㄥ涓棤鍏虫ā鍧椾腑鍚勮嚜閲嶇畻骞舵紓绉昏繖浜涘瓧娈?
### Requirement: ETF summary 涓?artifact 濂戠害蹇呴』鍏煎涓斾笉寰楁墿灞曡寖鍥?
绯荤粺 MUST 鍦ㄧ涓€杞?ETF 鍗曡吙閲嶆瀯涓繚鎸佸綋鍓?study 鍏ュ彛銆乻emantic config 鍏ュ彛浠ュ強 ETF summary / artifact 瀛楁鍏煎銆傝閲嶆瀯 SHALL NOT 鍊熸満鎵╁睍鍒?stock+ETF combo銆佸墠绔伐浣滃彴鎴栨柊鐨勭爺绌惰涔夈€?
#### Scenario: ETF summary 瀛楁淇濇寔鍏煎

- **WHEN** `artifacts_finalize.py` 涓?ETF 鍗曡吙杩愯鍐欏叆 `run_meta`銆乣governed_snapshot` 鎴栫瓑浠?summary 缁撴瀯
- **THEN** ETF 鐩稿叧瀛楁鍚嶅拰椤跺眰鏀剧疆浣嶇疆 MUST 淇濇寔涓庣幇鏈夋秷璐硅€呭吋瀹?- **THEN** API 灞?MAY 鏀逛负娑堣垂鏂扮殑 summary 妯″潡锛屼絾 SHALL NOT 閲嶆柊瀹氫箟绗簩濂?ETF summary 鐪熺浉

#### Scenario: 鏈閲嶆瀯涓嶅緱鎵╁ぇ鍒?combo 鎴栧墠绔?
- **WHEN** 鏈 change 杩涘叆 apply 闃舵
- **THEN** `cn_stock_etf_unified_runtime_service.py`銆乻tock+ETF combo 璇箟鍜屽墠绔姞杞介摼璺?MUST 淇濇寔涓嶅湪鏈瀹炵幇鑼冨洿鍐?- **THEN** 浠讳綍涓哄吋瀹?import 鑰屽彂鐢熺殑鏀瑰姩 SHALL 浠呴檺浜?ETF 鍗曡吙涓婚摼鐨勮杽鍖呰锛屼笉寰楁紨鍙樹负璺ㄧ郴缁熼噸鏋?
### Requirement: ETF 鍗曡吙鏂拌竟鐣屽繀椤讳繚鎸佸崟鍚戜緷璧?
绯荤粺 MUST 璁?ETF 鍗曡吙鐨勬柊妯″潡閬靛畧鍗曞悜渚濊禆鏂瑰悜锛氬悎鍚屼笌閰嶇疆灞傚湪涓婃父锛屾墽琛屽眰鍦ㄤ腑娓革紝accounting 涓?artifact 娑堣垂灞傚湪涓嬫父銆備笅娓告ā鍧?SHALL NOT 鍙嶅悜鎴愪负鍚堝悓鎴?provider 鐨勪緷璧栥€?
#### Scenario: Accounting 涓?artifact 涓嶅緱鍙嶅悜杩涘叆鍚堝悓灞?
- **WHEN** 绯荤粺鏂板 ETF contract銆乸rovider銆乤ccounting 鎴?summary 瀛愭ā鍧?- **THEN** `stage_pipeline/adapters` 涓?`api/artifacts` 灞?SHALL NOT 琚?`config` 鎴?`engine_vector` 涓婃父妯″潡鍙嶅悜 import
- **THEN** ETF 鍚堝悓鍜屾墽琛屽眰 MUST 浠呭悜涓嬫父鏆撮湶绋冲畾鏁版嵁缁撴瀯锛岃€屼笉鏄緷璧栦笅娓稿疄鐜扮粏鑺?

