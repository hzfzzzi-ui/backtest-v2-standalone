# execution-lineage-ledger Specification

## Purpose

Define the formal capability boundary for `execution-lineage-ledger` in the current mainline.
## Requirements
### Requirement: 鎵ц閾惧疄浣撳繀椤绘惡甯︾ǔ瀹?lineage id
绯荤粺 MUST 鍦ㄦ寮忔墽琛岄摼涓负淇″彿銆佽鍗曞拰鎴愪氦鐢熸垚绋冲畾涓斿彲澶嶇幇鐨?lineage id锛屽苟鏄惧紡琛ㄨ揪 `signal_id -> order_id -> fill_id` 鐨勭埗瀛愬叧绯汇€?

绯荤粺 MUST 鍦ㄦ寮忔墽琛岄摼涓负淇″彿銆佽鍗曞拰鎴愪氦鐢熸垚绋冲畾涓斿彲澶嶇幇鐨?lineage id锛屽苟鏄惧紡琛ㄨ揪 `signal_id -> order_id -> fill_id` 鐨勭埗瀛愬叧绯汇€?

#### Scenario: 淇″彿鐢熸垚绋冲畾 signal_id
- **WHEN** 鏌愭潯姝ｅ紡涔板叆鎴栧崠鍑轰俊鍙疯繘鍏ユ墽琛岄摼
- **THEN** 绯荤粺 SHALL 涓鸿淇″彿鐢熸垚绋冲畾 `signal_id`
- **THEN** 鐩稿悓杈撳叆鏉′欢涓嬮噸鏂拌繍琛屽疄楠屾椂锛岃淇″彿 SHALL 鐢熸垚鐩稿悓鐨?`signal_id`

#### Scenario: 璁㈠崟鍜屾垚浜ょ户鎵跨埗閾捐矾
- **WHEN** 鏌愭潯淇″彿琚帓绋嬩负璁㈠崟骞舵渶缁堝舰鎴愭垚浜?
- **THEN** 璁㈠崟 SHALL 鐢熸垚 `order_id` 骞舵樉寮忓紩鐢ㄧ埗 `signal_id`
- **THEN** 鎴愪氦 SHALL 鐢熸垚 `fill_id` 骞舵樉寮忓紩鐢ㄧ埗 `order_id`### Requirement: 鐢熷懡鍛ㄦ湡鍙拌处蹇呴』璁板綍鍏抽敭鐘舵€佹祦杞?
绯荤粺 MUST 涓鸿繘鍏ユ寮忔墽琛岄摼鐨勫疄浣撹褰曟渶灏忕敓鍛藉懆鏈熺姸鎬佹祦杞紝鑷冲皯瑕嗙洊 `generated`銆乣scheduled`銆乣filled`銆乣rejected`銆乣canceled` 鎴?`expired` 绛夊叧閿姸鎬侊紝浠ュ強瀵瑰簲鏃ユ湡銆佸師鍥犲拰鏍稿績璇婃柇瀛楁銆?

#### Scenario: 姝ｅ父 next-day 鎴愪氦
- **WHEN** 鏌愭潯淇″彿鍦ㄤ氦鏄撴棩 T 鐢熸垚锛屽苟鍦?T+1 琚帓绋嬩笖鎴愪氦
- **THEN** 鍙拌处 SHALL 璁板綍璇ュ疄浣撲粠 `generated` 鍒?`scheduled` 鍐嶅埌 `filled` 鐨勭姸鎬佹祦杞?
- **THEN** 姣忎釜鐘舵€?SHALL 甯︽湁瀵瑰簲鏃ユ湡涓?lineage id

#### Scenario: 璁㈠崟鏈垚浜よ€岀粓姝?
- **WHEN** 鏌愭潯璁㈠崟鏈舰鎴愭垚浜ゅ苟浠ユ嫆缁濄€佸彇娑堟垨澶辨晥缁撴潫
- **THEN** 鍙拌处 SHALL 璁板綍瀵瑰簲缁堟€佸強鍘熷洜
- **THEN** 瀹¤閾?SHALL 鑳藉尯鍒嗗畠涓庘€滀涪澶辫褰曗€濅笉鏄悓涓€绫婚棶棰?

### Requirement: lineage 鏄庣粏涓庢憳瑕佸繀椤诲垎灞傝緭鍑?
绯荤粺 MUST 灏嗗叏閲忕敓鍛藉懆鏈熸槑缁嗚緭鍑哄埌鐙珛 ledger artifact锛屽苟鍦ㄤ富瀹¤鏂囦欢涓彧淇濈暀鎽樿銆佸紓甯告牱鏈拰寮曠敤銆?

#### Scenario: 涓诲璁″紩鐢ㄥ彴璐?
- **WHEN** 涓€娆″疄楠屽畬鎴愬苟鐢熸垚鏍囧噯 artifacts
- **THEN** 绯荤粺 SHALL 鍐欏嚭鐙珛鐨?lineage ledger artifact
- **THEN** `audit.json` SHALL 浠呭寘鍚?lineage 鎽樿銆佸紓甯告牱鏈笌 ledger 寮曠敤锛岃€屼笉鏄唴鑱斿叏閲忔槑缁?

### Requirement: 鐢熷懡鍛ㄦ湡鍙拌处蹇呴』璁板綍鍏抽敭鐘舵€佹祦杞?
绯荤粺 MUST 涓鸿繘鍏ユ寮忔墽琛岄摼鐨勫疄浣撹褰曟渶灏忕敓鍛藉懆鏈熺姸鎬佹祦杞紝鑷冲皯瑕嗙洊 `generated`銆乣scheduled`銆乣filled`銆乣rejected`銆乣canceled` 鎴?`expired` 绛夊叧閿姸鎬侊紝浠ュ強瀵瑰簲鏃ユ湡銆佸師鍥犲拰鏍稿績璇婃柇瀛楁銆?

#### Scenario: 姝ｅ父 next-day 鎴愪氦
- **WHEN** 鏌愭潯淇″彿鍦ㄤ氦鏄撴棩 T 鐢熸垚锛屽苟鍦?T+1 琚帓绋嬩笖鎴愪氦
- **THEN** 鍙拌处 SHALL 璁板綍璇ュ疄浣撲粠 `generated` 鍒?`scheduled` 鍐嶅埌 `filled` 鐨勭姸鎬佹祦杞?
- **THEN** 姣忎釜鐘舵€?SHALL 甯︽湁瀵瑰簲鏃ユ湡涓?lineage id

#### Scenario: 璁㈠崟鏈垚浜よ€岀粓姝?
- **WHEN** 鏌愭潯璁㈠崟鏈舰鎴愭垚浜ゅ苟浠ユ嫆缁濄€佸彇娑堟垨澶辨晥缁撴潫
- **THEN** 鍙拌处 SHALL 璁板綍瀵瑰簲缁堟€佸強鍘熷洜
- **THEN** 瀹¤閾?SHALL 鑳藉尯鍒嗗畠涓庘€滀涪澶辫褰曗€濅笉鏄悓涓€绫婚棶棰?

