# candidate-plan-boundary-contracts Specification

## Purpose

Define the formal capability boundary for `candidate-plan-boundary-contracts` in the current mainline.
## Requirements
### Requirement: 绯荤粺蹇呴』鎻愪緵鍊欓€夎鍒掓寮忓悎鍚?绯荤粺 MUST 鍦?`candidate_boundary_v1` 涓庢墽琛屽唴鏍镐箣闂存彁渚?`candidate_plan_v1` 姝ｅ紡鍚堝悓銆傝鍚堝悓 MUST 琛ㄨ揪鍊欓€夎竟鐣岀‘璁ゅ悗鐨勬渶缁堝€欓€夎鍒掋€佽疆鎹㈡浛鎹㈢粨鏋溿€佺幇閲戞劅鐭ラ€夋嫨缁撴灉鍜岃鍒掑眰鎷掔粷鎽樿銆?
#### Scenario: 涓偂瀛愮郴缁熺敓鎴愬€欓€夎鍒掑悎鍚?- **WHEN** A鑲′釜鑲″瓙绯荤粺瀹屾垚鍊欓€夎竟鐣岀‘璁ゅ苟鍑嗗杩涘叆鎵ц鍐呮牳
- **THEN** 绯荤粺 MUST 鐢熸垚 `candidate_plan_v1`
- **THEN** 璇?payload MUST 鑷冲皯鍖呭惈鏈€缁堜拱鍏ュ€欓€夐『搴忋€佽鍒掑眰鎷掔粷鍘熷洜璁℃暟鍜岃疆鎹㈡浛鎹㈡憳瑕?
#### Scenario: ETF 瀛愮郴缁熺洿閫氬€欓€夎鍒掑悎鍚?- **WHEN** ETF 瀛愮郴缁熷綋鍓嶆棤闇€鐜伴噾鎰熺煡鎼滅储鎴栬疆鎹㈡浛鎹?- **THEN** 绯荤粺 MUST 浠嶇敓鎴愬悎娉曠殑 `candidate_plan_v1`
- **THEN** 璇?payload MAY 涓烘渶灏忕洿閫氳鍒掔粨鏋滐紝浣?SHALL 淇濇寔缁熶竴鍚堝悓缁撴瀯

### Requirement: 鍊欓€夎鍒掑悎鍚屽繀椤诲厛浜庢墽琛屽唴鏍告敹鏁涘€欓€夊吋瀹硅涔?绯荤粺 MUST 鍦ㄨ繘鍏ユ墽琛屽唴鏍稿墠锛屽厛浜?`order_planning` 鏀舵暃 `candidate_plan_mode`銆佺幇閲戞劅鐭ユ悳绱㈠拰杞崲鏇挎崲绛夊€欓€夎鍒掑吋瀹硅涔夈€傛墽琛屽唴鏍?SHALL NOT 鐩存帴鍩轰簬杩欎簺閰嶇疆瀛楁閲嶆柊鎺ㄥ鍊欓€夎鍒掋€?
#### Scenario: 鍊欓€夎鍒掓ā寮忓惎鐢?- **WHEN** 杩愯鏃跺惎鐢ㄤ簡鐜伴噾鎰熺煡鎼滅储鎴栬疆鎹㈡浛鎹?- **THEN** 杩欎簺鍏煎璇箟 MUST 鍦?`candidate_plan_v1` 鐢熸垚闃舵瀹屾垚
- **THEN** 鎵ц鍐呮牳 SHALL 鍙秷璐硅鍒掔粨鏋滆€屼笉鏄師濮嬫ā寮忛厤缃?
### Requirement: candidate_plan 鍙厑璁镐綔涓哄唴閮ㄦ垨杩佺Щ缁撴瀯瀛樺湪
绯荤粺 SHALL 灏?`candidate_plan` 瀹氫綅涓哄瓙绯荤粺鍐呴儴缁撴瀯鎴栬縼绉绘湡 compat 缁撴瀯锛屼笉寰楃户缁妸瀹冧綔涓哄叡浜墽琛岃竟鐣屼富鍚堝悓銆?
#### Scenario: candidate_plan 涓嶅啀瀹氫箟鍏变韩杈圭晫
- **WHEN** 绯荤粺鎻忚堪鍏变韩鎵ц杈圭晫杈撳叆
- **THEN** `candidate_plan` MUST 涓嶅啀琚垪涓烘寮忓叡浜悎鍚?

