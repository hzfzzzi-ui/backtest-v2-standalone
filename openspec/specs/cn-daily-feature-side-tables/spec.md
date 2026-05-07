# cn-daily-feature-side-tables Specification

## Purpose

Define the formal capability boundary for `cn-daily-feature-side-tables` in the current mainline.
## Requirements
### Requirement: CN_A 鏃ラ鎹㈡墜鐜囦晶琛ㄥ叆搴?
绯荤粺 MUST 涓?`market='CN_A'` 鐨勪釜鑲℃棩棰?`daily_basic` 鏁版嵁鎻愪緵鐙珛渚ц〃锛屾寜 `symbol + trade_date` 瀛樺偍鏄惧紡鎹㈡墜鐜囧瓧娈点€傞鐗堜晶琛?MUST 鑷冲皯鍖呭惈 `turnover_rate`銆乣turnover_rate_f`銆乣source`銆乣created_at`銆乣updated_at`銆?

绯荤粺 MUST 涓?`market='CN_A'` 鐨勪釜鑲℃棩棰?`daily_basic` 鏁版嵁鎻愪緵鐙珛渚ц〃锛屾寜 `symbol + trade_date` 瀛樺偍鏄惧紡鎹㈡墜鐜囧瓧娈点€傞鐗堜晶琛?MUST 鑷冲皯鍖呭惈 `turnover_rate`銆乣turnover_rate_f`銆乣source`銆乣created_at`銆乣updated_at`銆?

#### Scenario: 鏄惧紡鎹㈡墜鐜囨寜浜ゆ槗鏃ュ叆搴?
- **WHEN** 鍚屾鑴氭湰鑾峰彇鍒版煇鍙?`CN_A` 鑲＄エ鍦ㄦ煇涓?`trade_date` 鐨?`daily_basic` 璁板綍
- **THEN** 绯荤粺 SHALL 灏?`turnover_rate` 鍜?`turnover_rate_f` 鎸?`symbol + trade_date` 鍐欏叆渚ц〃

#### Scenario: 鍚屼竴涓婚敭閲嶅鍚屾鏃跺箓绛夋洿鏂?
- **WHEN** 鍚屾鑴氭湰閲嶅澶勭悊鍚屼竴 `symbol + trade_date`
- **THEN** 绯荤粺 SHALL 浠?upsert 鏂瑰紡鏇存柊璇ヨ锛岃€屼笉鏄彃鍏ラ噸澶嶈褰?## Requirement: CN_A 鏃ラ moneyflow 鍒嗘。渚ц〃鍏ュ簱
绯荤粺 MUST 涓?`market='CN_A'` 鐨勪釜鑲℃棩棰戣祫閲戞祦鎻愪緵鐙珛渚ц〃锛屼笖棣栫増 MUST 閲囩敤 Tushare `moneyflow` 鍙ｅ緞銆備晶琛?MUST 鎸?`symbol + trade_date` 瀛樺偍灏忓崟銆佷腑鍗曘€佸ぇ鍗曘€佺壒澶у崟鐨勪拱鍗栭噺棰濓紝浠ュ強 `net_mf_vol`銆乣net_mf_amount`銆?

#### Scenario: 涓诲姩涔板崠鍗曞垎妗ｅ瓧娈靛畬鏁村啓鍏?
- **WHEN** 鍚屾鑴氭湰鑾峰彇鍒版煇鍙?`CN_A` 鑲＄エ鍦ㄦ煇涓?`trade_date` 鐨?`moneyflow` 璁板綍
- **THEN** 绯荤粺 SHALL 灏嗗洓妗ｄ拱鍗栭噺棰濆瓧娈靛拰鍑€娴佸叆瀛楁鎸?`symbol + trade_date` 鍐欏叆渚ц〃

#### Scenario: 涓嶆贩鍏ュ叾浠栬祫閲戞祦鍙ｅ緞
- **WHEN** 绯荤粺鎵ц moneyflow 渚ц〃鍚屾
- **THEN** 绯荤粺 SHALL NOT 浣跨敤 `moneyflow_ths` 鎴?`moneyflow_dc` 鏇夸唬鎴栨贩鍚堝啓鍏ヨ渚ц〃

### Requirement: 渚ц〃鍥炲～杈圭晫涓庡閲忓悓姝ュ彲瀹¤
绯荤粺 MUST 鏀寔浠?`2007-01-04` 鍒板綋鍓嶆渶鏂板彲寰椾氦鏄撴棩鐨勫巻鍙插洖濉紝骞舵敮鎸佹寜浜ゆ槗鏃ョ獥鍙ｆ墽琛屽悗缁閲忓悓姝ャ€傜郴缁?MUST 涓烘瘡娆¤繍琛岃緭鍑哄彲瀹¤鎽樿锛岃嚦灏戝寘鍚紑濮嬫棩鏈熴€佺粨鏉熸棩鏈熴€佸啓鍏ヨ鏁般€佺己澶变氦鏄撴棩鎴栧け璐ユ壒娆′俊鎭€?

绯荤粺 MUST 鏀寔浠?`2007-01-04` 鍒板綋鍓嶆渶鏂板彲寰椾氦鏄撴棩鐨勫巻鍙插洖濉紝骞舵敮鎸佹寜浜ゆ槗鏃ョ獥鍙ｆ墽琛屽悗缁閲忓悓姝ャ€傜郴缁?MUST 涓烘瘡娆¤繍琛岃緭鍑哄彲瀹¤鎽樿锛岃嚦灏戝寘鍚紑濮嬫棩鏈熴€佺粨鏉熸棩鏈熴€佸啓鍏ヨ鏁般€佺己澶变氦鏄撴棩鎴栧け璐ユ壒娆′俊鎭€?

#### Scenario: 榛樿鍘嗗彶鍥炲～浠ュ綋鍓嶆渶鏂板彲寰椾氦鏄撴棩鏀跺彛
- **WHEN** 鐢ㄦ埛鏈樉寮忔寚瀹?`--end`
- **THEN** 绯荤粺 SHALL 浣跨敤褰撳墠鏈€鏂板彲寰椾氦鏄撴棩浣滀负鍥炲～涓婄晫锛岃€屼笉鏄啓鍏ユ湭鏉ユ棩鏈?

#### Scenario: 杩愯浜х墿璁板綍鍐欏叆鎯呭喌
- **WHEN** 鍚屾鑴氭湰瀹屾垚涓€娆″巻鍙插洖濉垨澧為噺鏇存柊
- **THEN** 绯荤粺 SHALL 杈撳嚭鎽樿鏂囦欢鍜屾牱鏈枃浠讹紝浠ュ睍绀烘椂闂磋寖鍥淬€佸啓鍏ョ粨鏋滀笌缂哄彛淇℃伅### Requirement: 渚ц〃瑕嗙洊鐜囧繀椤诲彲鐙珛瀹¤
绯荤粺 MUST 鎻愪緵鐙珛瑕嗙洊鐜囧璁¤兘鍔涳紝鎸?`trade_date` 灏?`pit_stock_daily_basic` 涓?`pit_stock_moneyflow` 鐨勫疄闄呰惤搴撹鏁板鐓?`pams_ohlcv_daily` 涓?`market='CN_A'` 鐨勫弬鑰冭鏁帮紝骞惰緭鍑鸿鐩栫巼銆佽鐩栨渶宸氦鏄撴棩鍜岀己鍙ｆ牱鏈€?

#### Scenario: 鍥炲～瀹屾垚鍚庤緭鍑洪€愪氦鏄撴棩瑕嗙洊鐜?
- **WHEN** 鐢ㄦ埛鍦ㄤ换鎰忔棩鏈熺獥鍙ｆ墽琛岃鐩栫巼瀹¤
- **THEN** 绯荤粺 SHALL 杈撳嚭姣忎釜 `trade_date` 鐨勫弬鑰冭鏁般€乣daily_basic` 琛屾暟銆乣moneyflow` 琛屾暟锛屼互鍙婂搴旇鐩栫巼

#### Scenario: 瀹¤缁撴灉鏆撮湶鏈€宸鐩栦氦鏄撴棩
- **WHEN** 鏌愪簺浜ゆ槗鏃ョ殑 `daily_basic` 鎴?`moneyflow` 鐩稿鍙傝€冭〃瀛樺湪缂哄彛
- **THEN** 绯荤粺 SHALL 杈撳嚭缂哄彛鏈€涓ラ噸浜ゆ槗鏃ュ垪琛ㄥ拰缂哄彛鏍锋湰 symbol 鏂囦欢锛岃€屼笉鏄彧缁欐€婚噺姹囨€?

### Requirement: 鏂颁晶琛ㄤ笉寰楁敼鍙樼幇鏈変富琛屾儏鍚堝悓
绯荤粺 MUST 淇濇寔 `pams_ohlcv_daily` 鐨勬棦鏈夎涔夊拰 baseline 榛樿娑堣垂璺緞涓嶅彉銆傛湰娆℃敼鍔?SHALL 閫氳繃鏂板渚ц〃琛ュ厖鏁版嵁锛岃€屼笉鏄姹備富琛屾儏琛ㄦ柊澧炲繀闇€瀛楁鎴栨敼鍙樼幇鏈?provider 榛樿璇诲彇鍚堝悓銆?

绯荤粺 MUST 淇濇寔 `pams_ohlcv_daily` 鐨勬棦鏈夎涔夊拰 baseline 榛樿娑堣垂璺緞涓嶅彉銆傛湰娆℃敼鍔?SHALL 閫氳繃鏂板渚ц〃琛ュ厖鏁版嵁锛岃€屼笉鏄姹備富琛屾儏琛ㄦ柊澧炲繀闇€瀛楁鎴栨敼鍙樼幇鏈?provider 榛樿璇诲彇鍚堝悓銆?

#### Scenario: 鏈惎鐢ㄦ柊渚ц〃鏃?baseline 淇濇寔涓嶅彉
- **WHEN** 鐢ㄦ埛缁х画杩愯褰撳墠 baseline 鍜屾棦鏈夋棩棰戜富閾捐矾
- **THEN** 绯荤粺 SHALL 涓嶅洜鏂板渚ц〃鑰屾敼鍙樼幇鏈変富琛ㄤ緷璧栥€侀粯璁ゆ煡璇㈣矾寰勬垨鍥炴祴缁撴灉鍙ｅ緞

#### Scenario: 渚ц〃鍒涘缓澶辫触涓嶆薄鏌撲富琛?
- **WHEN** 鏂颁晶琛ㄥ悓姝ュ湪寤鸿〃鎴栧啓鍏ラ樁娈靛け璐?
- **THEN** 绯荤粺 SHALL NOT 瀵?`pams_ohlcv_daily` 宸叉湁鏁版嵁鎵ц鍥為€€鎬ф敼鍐欐垨璇箟鏇挎崲### Requirement: CN_A 鏃ラ moneyflow 鍒嗘。渚ц〃鍏ュ簱
绯荤粺 MUST 涓?`market='CN_A'` 鐨勪釜鑲℃棩棰戣祫閲戞祦鎻愪緵鐙珛渚ц〃锛屼笖棣栫増 MUST 閲囩敤 Tushare `moneyflow` 鍙ｅ緞銆備晶琛?MUST 鎸?`symbol + trade_date` 瀛樺偍灏忓崟銆佷腑鍗曘€佸ぇ鍗曘€佺壒澶у崟鐨勪拱鍗栭噺棰濓紝浠ュ強 `net_mf_vol`銆乣net_mf_amount`銆?

#### Scenario: 涓诲姩涔板崠鍗曞垎妗ｅ瓧娈靛畬鏁村啓鍏?
- **WHEN** 鍚屾鑴氭湰鑾峰彇鍒版煇鍙?`CN_A` 鑲＄エ鍦ㄦ煇涓?`trade_date` 鐨?`moneyflow` 璁板綍
- **THEN** 绯荤粺 SHALL 灏嗗洓妗ｄ拱鍗栭噺棰濆瓧娈靛拰鍑€娴佸叆瀛楁鎸?`symbol + trade_date` 鍐欏叆渚ц〃

#### Scenario: 涓嶆贩鍏ュ叾浠栬祫閲戞祦鍙ｅ緞
- **WHEN** 绯荤粺鎵ц moneyflow 渚ц〃鍚屾
- **THEN** 绯荤粺 SHALL NOT 浣跨敤 `moneyflow_ths` 鎴?`moneyflow_dc` 鏇夸唬鎴栨贩鍚堝啓鍏ヨ渚ц〃

### Requirement: 渚ц〃瑕嗙洊鐜囧繀椤诲彲鐙珛瀹¤
绯荤粺 MUST 鎻愪緵鐙珛瑕嗙洊鐜囧璁¤兘鍔涳紝鎸?`trade_date` 灏?`pit_stock_daily_basic` 涓?`pit_stock_moneyflow` 鐨勫疄闄呰惤搴撹鏁板鐓?`pams_ohlcv_daily` 涓?`market='CN_A'` 鐨勫弬鑰冭鏁帮紝骞惰緭鍑鸿鐩栫巼銆佽鐩栨渶宸氦鏄撴棩鍜岀己鍙ｆ牱鏈€?

#### Scenario: 鍥炲～瀹屾垚鍚庤緭鍑洪€愪氦鏄撴棩瑕嗙洊鐜?
- **WHEN** 鐢ㄦ埛鍦ㄤ换鎰忔棩鏈熺獥鍙ｆ墽琛岃鐩栫巼瀹¤
- **THEN** 绯荤粺 SHALL 杈撳嚭姣忎釜 `trade_date` 鐨勫弬鑰冭鏁般€乣daily_basic` 琛屾暟銆乣moneyflow` 琛屾暟锛屼互鍙婂搴旇鐩栫巼

#### Scenario: 瀹¤缁撴灉鏆撮湶鏈€宸鐩栦氦鏄撴棩
- **WHEN** 鏌愪簺浜ゆ槗鏃ョ殑 `daily_basic` 鎴?`moneyflow` 鐩稿鍙傝€冭〃瀛樺湪缂哄彛
- **THEN** 绯荤粺 SHALL 杈撳嚭缂哄彛鏈€涓ラ噸浜ゆ槗鏃ュ垪琛ㄥ拰缂哄彛鏍锋湰 symbol 鏂囦欢锛岃€屼笉鏄彧缁欐€婚噺姹囨€?

