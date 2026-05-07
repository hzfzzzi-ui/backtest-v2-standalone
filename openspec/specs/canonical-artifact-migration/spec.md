# canonical-artifact-migration Specification

## Purpose

Define the formal capability boundary for `canonical-artifact-migration` in the current mainline.
## Requirements
### Requirement: 杩愯鏃惰鍙栭摼蹇呴』鍙 canonical artifact schema
绯荤粺 MUST 浠?canonical artifact 鍛藉悕銆乧anonical counter 瀛楁鍜?canonical manifest 璧勪骇涓婁笅鏂囦綔涓鸿繍琛屾椂鍞竴鐪熺浉銆傛煡璇㈡湇鍔°€丄PI 杩斿洖鍜屽墠绔富璺緞 SHALL NOT 闀挎湡渚濊禆鏌ヨ鏃朵复鏃惰ˉ涓佸幓鎺ㄥ鍘嗗彶璧勪骇涓婁笅鏂囥€?

绯荤粺 MUST 浠?canonical artifact 鍛藉悕鍜?canonical counter 瀛楁浣滀负杩愯鏃跺敮涓€鐪熺浉銆傛煡璇㈡湇鍔°€丄PI 杩斿洖鍜屽墠绔富璺緞 SHALL NOT 缁х画鍦ㄨ繍琛屾椂甯搁┗鍘嗗彶 alias銆乴egacy trades 鏂囦欢鍚嶆垨鏃?shell label 褰掍竴鍖栭€昏緫銆?

#### Scenario: 鏌ヨ瀹為獙 artifact
- **WHEN** 鏌ヨ鏈嶅姟璇诲彇鏌愪釜瀹為獙鐩綍鐨勬爣鍑?artifact
- **THEN** 璇诲彇閾?MUST 鐩存帴娑堣垂 canonical 鏂囦欢鍛藉悕銆乧anonical counters 鍜?canonical manifest 瀛楁
- **THEN** 杩愯鏃?SHALL NOT 缁х画鎶婂巻鍙?alias 鎴栦复鏃?asset context 鎺ㄥ褰撴垚闀挎湡涓昏矾寰?

#### Scenario: 鏂板疄楠屽啓鍑烘爣鍑嗕骇鐗?
- **WHEN** 鏂板疄楠屽啓鍑?`manifest.json`銆乣perf.json`銆乣run_meta.json` 绛夋爣鍑嗕骇鐗?
- **THEN** 绯荤粺 MUST 鍙啓鍑?canonical 鍛藉悕鍜?canonical 璧勪骇涓婁笅鏂?
- **THEN** 鏂板疄楠?SHALL NOT 鐢熸垚鏂扮殑鍘嗗彶 alias 鎴栫己澶辫祫浜т笂涓嬫枃瀛楁鐨?manifest

#### Scenario: 鏂板疄楠屽啓鍑轰骇鐗?
- **WHEN** 鏂板疄楠屽啓鍑?`manifest.json`銆乣perf.json`銆乣run_meta.json` 绛夋爣鍑嗕骇鐗?
- **THEN** 绯荤粺 MUST 鍙啓鍑?canonical 鍛藉悕
- **THEN** 鏂板疄楠?SHALL NOT 鍐嶇敓鎴愭棫 alias### Requirement: 鍘嗗彶 artifact alias 蹇呴』閫氳繃绂荤嚎杩佺Щ閫€鍑鸿繍琛屾椂
绯荤粺 MUST 鎻愪緵绂荤嚎杩佺Щ鍜岃縼绉诲璁★紝鐢ㄤ簬鎶婂巻鍙?artifact銆乧ounter 瀛楁銆乻hell label 鍜岀己澶辫祫浜т笂涓嬫枃鐨?`manifest.json` 鎵归噺鏇存柊涓?canonical schema銆傝縼绉诲畬鎴愬悗锛屽巻鍙插疄楠岀殑纾佺洏 manifest MUST 鑷弿杩板叾 canonical 璧勪骇杈圭晫銆?

绯荤粺 MUST 鎻愪緵绂荤嚎杩佺Щ鍜岃縼绉诲璁★紝鐢ㄤ簬鎶婂巻鍙?artifact銆乧ounter 瀛楁銆乻hell label 鍜岀己澶辫祫浜т笂涓嬫枃鐨?`manifest.json` 鎵归噺鏇存柊涓?canonical schema銆傝縼绉诲畬鎴愬悗锛屽巻鍙插疄楠岀殑纾佺洏 manifest MUST 鑷弿杩板叾 canonical 璧勪骇杈圭晫銆?

#### Scenario: 鍥炲～鍘嗗彶 manifest 璧勪骇涓婁笅鏂?
- **WHEN** 鏌愪釜鍘嗗彶瀹為獙鐨?`manifest.json` 缂哄皯 `asset_scope`銆乣asset_profile_id`銆乣market_profile_id`銆乣execution_profile_id` 鎴?`asset_context`
- **THEN** 杩佺Щ宸ュ叿 MUST 浠?`config.json`銆乣run_config.json`銆乣compiled_plan.json` 绛夋爣鍑嗚緭鍏ユ帹瀵煎苟鍥炲～ canonical 瀛楁
- **THEN** 鑻ユ棤娉曞彲闈犳帹瀵硷紝杩佺Щ宸ュ叿 MUST 璁板綍璺宠繃鍘熷洜骞惰緭鍑哄埌瀹¤缁撴灉锛岃€?SHALL NOT 闈欓粯鍐欏叆涓嶅彲淇″€?

#### Scenario: 杩佺Щ鍘嗗彶浜х墿
- **WHEN** 闇€瑕佹竻鐞嗗巻鍙?artifact alias
- **THEN** 绯荤粺 MUST 鍏堣緭鍑鸿縼绉诲璁℃姤鍛婏紝鍒楀嚭鍙楀奖鍝嶇洰褰曘€佸瓧娈点€佹枃浠跺悕涓庡洖濉粨鏋?
- **THEN** 绯荤粺 MUST 閫氳繃绂荤嚎杩佺Щ鎵归噺鏇存柊鍘嗗彶浜х墿锛屽啀鍒犻櫎杩愯鏃堕暱鏈?alias 褰掍竴鍖栦緷璧?

#### Scenario: 杩佺Щ鍚庡洖褰掓牎楠?
- **WHEN** 鏌愭壒鍘嗗彶浜х墿瀹屾垚 canonical migration
- **THEN** 绯荤粺 MUST 浠ュ墠鍚庡鐓?`V10.1 -> exp_20260314_144548534_7db9` 鍜屼唬琛ㄦ€у巻鍙插疄楠屽仛璇诲彇鍥炲綊
- **THEN** 鑻ョ粨鏋滄垨 manifest 璇箟鍙戠敓婕傜Щ锛岃縼绉?SHALL NOT 杩涘叆涓昏矾寰?

### Requirement: 鍘嗗彶浜х墿鍏煎蹇呴』閫€鍑鸿繍琛屾椂骞舵敼涓虹绾胯縼绉?
绯荤粺 MUST 灏嗗巻鍙?artifact alias銆佹棫 counter 瀛楁鍜屾棫 shell label 鐨勫鐞嗛檺鍒跺湪绂荤嚎杩佺Щ宸ュ叿涓庤縼绉诲璁′腑銆傝繍琛屾椂 contract SHALL NOT 鍐嶄负杩欎簺鍘嗗彶鍚嶇О淇濈暀甯搁┗鍏煎璇诲彇銆?

#### Scenario: 闇€瑕佽鍙栨棫浜х墿鐩綍
- **WHEN** 鏌愭壒鍘嗗彶浜х墿浠嶄娇鐢ㄦ棫鍛藉悕
- **THEN** 绯荤粺 MUST 鍏堥€氳繃绂荤嚎 migration 灏嗗叾杞垚 canonical schema
- **THEN** 杩愯鏃舵帴鍙?SHALL NOT 鍥犺繖浜涙棫浜х墿缁х画淇濈暀鍏煎鍒嗘敮

#### Scenario: 杩佺Щ鍚庡洖褰掓牎楠?
- **WHEN** 鍘嗗彶浜х墿瀹屾垚 canonical migration
- **THEN** 绯荤粺 MUST 浠ュ墠鍚庡鐓?`baseline_V10.1 -> exp_20260314_144548534_7db9` 澶嶆牳璇诲彇缁撴灉
- **THEN** 鑻ュ嚭鐜扮粨鏋滄紓绉伙紝杩佺Щ SHALL NOT 杩涘叆涓昏矾寰?

