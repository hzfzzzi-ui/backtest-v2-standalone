# multi-asset-entry-boundaries Specification

## Purpose

Define the formal capability boundary for `multi-asset-entry-boundaries` in the current mainline.
## Requirements
### Requirement: 绯荤粺蹇呴』涓烘瘡娆℃寮忚繍琛屽０鏄?canonical asset scope
绯荤粺 MUST 瑕佹眰妗岄潰杩愯鍏ュ彛銆乻tudy 瀹氫箟銆乬enerated thin script 鍜?CLI 杩愯鍏ュ彛閮借兘瑙ｆ瀽鍑?canonical `asset_scope`銆傜郴缁?SHALL NOT 闀挎湡鎶娾€滄湭澹版槑璧勪骇鑼冨洿鈥濊涓烘寮忎富璺緞鐨勫彲鎺ュ彈杈撳叆銆?

#### Scenario: 妗岄潰绔彂璧疯繍琛?
- **WHEN** 妗岄潰绔彂璧锋寮忓疄楠岃繍琛?
- **THEN** 杩愯璇锋眰 MUST 鑳借В鏋愬嚭 canonical `asset_scope`
- **THEN** 鍚庣 SHALL NOT 缁х画渚濊禆 A 鑲￠殣寮忛粯璁ゆ潵鍒ゆ柇鏈杩愯鐨勮祫浜ц涔?

#### Scenario: study 鍙戣捣杩愯
- **WHEN** `study_run` 鎵ц鏌愪釜 active study
- **THEN** 璇?study MUST 鑳藉０鏄庢垨瑙ｆ瀽鍑?canonical `asset_scope`
- **THEN** generated thin script MUST 鍙€忎紶璇ヨ祫浜ц寖鍥达紝鑰?SHALL NOT 鑷繁鎺ㄦ柇甯傚満璇箟

### Requirement: 绯荤粺蹇呴』鎶?asset scope 瑙ｆ瀽涓鸿杽 asset profile 鍜?market profile
绯荤粺 MUST 灏嗗叆鍙?`asset_scope` 瑙ｆ瀽涓?canonical `asset_profile` 涓?`market_profile`锛屽苟浣滀负 runtime compile銆乽niverse resolver銆乸rovider route 鍜岀粨鏋滈潰鎽樿鐨勫叡鍚岀湡鐩搞€?

#### Scenario: 瑙ｆ瀽褰撳墠 A 鑲′富绾?
- **WHEN** 绯荤粺鎵ц褰撳墠 `baseline_V10.1`
- **THEN** `asset_scope` MUST 瑙ｆ瀽涓哄綋鍓嶅敮涓€姝ｅ紡 A 鑲?canonical profile
- **THEN** 瑙ｆ瀽缁撴灉 MUST 涓嶆敼鍙?`V10.1` 鐨勮繍琛岃涓?

#### Scenario: 鏈敮鎸佺殑璧勪骇鑼冨洿
- **WHEN** 杩愯璇锋眰澹版槑浜嗗皻鏈寮忔帴鍏ョ殑 `asset_scope`
- **THEN** 绯荤粺 MUST 杩斿洖鏄惧紡 unsupported error
- **THEN** 绯荤粺 SHALL NOT 闈欓粯鍥為€€鍒?A 鑲?profile

### Requirement: A 鑲′笓鏈夊競鍦哄亣璁惧繀椤讳綔涓?market profile 鏄惧紡瀛樺湪
绯荤粺 MUST 灏嗕氦鏄撴棩鍘嗐€乴ot 瑙勫垯銆佸仠鐗岃涔夈€丼T 璇箟銆佽涓?鎴愬垎鏁版嵁渚濊禆鍜?benchmark 瀹舵棌绛?A 鑲′笓鏈夊亣璁鹃殧绂讳负鏄惧紡 `market_profile`锛岃€?SHALL NOT 缁х画鎶婅繖浜涘亣璁炬暎钀戒负榛樿鍏ㄥ眬琛屼负銆?

#### Scenario: A 鑲¤繍琛屼娇鐢ㄦ樉寮?market profile
- **WHEN** 绯荤粺杩愯 A 鑲?profile
- **THEN** 鍋滅墝銆丼T銆乴ot size 鍜?benchmark 瀹舵棌 MUST 閫氳繃 market profile 鎴栧搴?adapter 鎻愪緵
- **THEN** 杩欎簺瑙勫垯 SHALL NOT 浠呴€氳繃闅愬紡鍏ㄥ眬榛樿鐢熸晥

#### Scenario: 鏈潵鏂拌祫浜ф帴鍏ュ墠
- **WHEN** 绯荤粺灏氭湭姝ｅ紡瀹炵幇鏌愪釜鏂拌祫浜х殑 market profile adapter
- **THEN** 绯荤粺 MUST 鍦ㄥ叆鍙ｈ竟鐣屼笂鏄庣‘缂哄け
- **THEN** 绯荤粺 SHALL NOT 澶嶇敤 A 鑲¤鍒欏亣瑁呮敮鎸佽璧勪骇

### Requirement: 绯荤粺蹇呴』姝ｅ紡瑙ｆ瀽骞舵毚闇?`us_equity` canonical asset profile
绯荤粺 MUST 鍏佽杩愯鍏ュ彛銆乺untime compile銆乵anifest 鍜?snapshot 姝ｅ紡瑙ｆ瀽 `us_equity` 浣滀负 canonical `asset_scope`锛屽苟浜у嚭绋冲畾鐨?`asset_profile` / `market_profile` / `execution_profile` 鎽樿銆傜郴缁?SHALL NOT 鍥犱负 `us_equity` 灏氭湭鎺ュ叆鏁版嵁涓庝氦鏄?adapter锛岃€岀户缁妸璇?scope 瑙嗕负鏈煡杈撳叆銆?

#### Scenario: 瑙ｆ瀽缇庤偂涓偂璧勪骇杈圭晫
- **WHEN** 杩愯璇锋眰銆乻tudy 鎴栧凡鏈?manifest 鏄庣‘澹版槑 `asset_scope='us_equity'`
- **THEN** 绯荤粺 MUST 浜у嚭 canonical `asset_context`
- **THEN** 璇?`asset_context` MUST 鍖呭惈 `asset_scope`銆乣asset_profile_id`銆乣asset_family` 鍜?`market_profile_id`

### Requirement: 閫氱敤鍏ュ彛涓嶅緱缁х画鎶?`cn_a_equity` 浣滀负闅愬紡鍏ㄥ眬榛樿
绯荤粺 MUST 瑕佹眰 request contract銆乺untime compile銆乫rontend payload 鍜?snapshot bridge 鏄惧紡閫忎紶鎴栬В鏋愯祫浜ц寖鍥淬€傞€氱敤鍏ュ彛 SHALL NOT 鍐嶅湪鏈鏌ュ凡鏈夐厤缃€乵anifest 鎴?request 鐨勬儏鍐典笅锛岀洿鎺ュ啓鍏?`cn_a_equity` 浣滀负榛樿璧勪骇鐪熺浉銆?

#### Scenario: 鍏煎鑰?A 鑲″叆鍙ｄ絾涓嶅啀纭紪鐮侀粯璁?
- **WHEN** 褰撳墠 A 鑲?baseline 鎴栧巻鍙?artifact 鏈樉寮忓０鏄?`asset_scope`
- **THEN** 绯荤粺 MAY 閫氳繃宸叉湁 baseline/config/manifest 鍏煎瑙ｆ瀽鍑?`cn_a_equity`
- **THEN** 閫氱敤鍏ュ彛 SHALL NOT 鏃犳潯浠舵妸绌哄€奸噸鍐欐垚 `cn_a_equity`

### Requirement: 鏈疄鐜拌祫浜?adapter 鏃跺繀椤绘樉寮?unsupported
绯荤粺 MUST 鍖哄垎鈥滆祫浜ц竟鐣屽凡鍙В鏋愨€濆拰鈥滆璧勪骇宸插彲杩愯鈥濄€傚浜庡皻鏈疄鐜版暟鎹€乽niverse銆乻ync 鎴?execution adapter 鐨勮祫浜э紝绯荤粺 MUST 杩斿洖鏄惧紡 unsupported error 鎴?status锛岃€?SHALL NOT 闈欓粯鍥為€€鍒?A 鑲′富璺緞銆?

#### Scenario: 缇庤偂 scope 杩涘叆鏈疄鐜拌繍琛岃矾寰?
- **WHEN** `asset_scope='us_equity'` 杩涘叆褰撳墠浠呮敮鎸?A 鑲＄殑 resolver銆乻ync 鎴?execution 鍏ュ彛
- **THEN** 绯荤粺 MUST 鏄庣‘杩斿洖 unsupported
- **THEN** 绯荤粺 SHALL NOT 鑷姩澶嶇敤 A 鑲¤鍒欑户缁繍琛?

### Requirement: 绯荤粺蹇呴』姝ｅ紡瑙ｆ瀽 `cn_etf` canonical asset profile
绯荤粺 MUST 鍏佽璇锋眰鍏ュ彛銆乺untime compile銆乵anifest 鍜?snapshot 姝ｅ紡瑙ｆ瀽 `asset_scope='cn_etf'`锛屽苟杈撳嚭绋冲畾鐨?`asset_context`銆傝 `asset_context` MUST 鑷冲皯鍖呭惈 `asset_scope`銆乣asset_profile_id`銆乣asset_family`銆乣asset_class`銆乣market_profile_id` 鍜?`execution_profile_id`銆?

#### Scenario: 瑙ｆ瀽 A 鑲?ETF 璧勪骇杈圭晫
- **WHEN** 杩愯璇锋眰銆乻tudy 鎴栧巻鍙?manifest 鏄惧紡澹版槑 `asset_scope='cn_etf'`
- **THEN** 绯荤粺 MUST 瑙ｆ瀽鍑?canonical ETF `asset_context`
- **THEN** 璇?`asset_context` MUST 涓嶅緱鍥為€€涓?`cn_a_equity`

#### Scenario: ETF 鍏ュ彛娌跨敤涓浗澶ч檰甯傚満鎵ц澹?
- **WHEN** 绯荤粺瑙ｆ瀽 `cn_etf` 璧勪骇鑼冨洿
- **THEN** `asset_context` MUST 鏆撮湶涓浗澶ч檰甯傚満浜ゆ槗鏃ュ巻鍜?`T+1 / NEXT_OPEN / lot=100` 鐨勬墽琛岃涔?
- **THEN** 绯荤粺 MUST 涓嶆妸鑲＄エ鐗规湁杩囨护鎴栬偂绁ㄦ睜璇箟褰撴垚 ETF 榛樿鐪熺浉

