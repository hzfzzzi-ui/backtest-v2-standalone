# cn-daily-basic-liquidity-data Specification

## Purpose

Define the formal capability boundary for `cn-daily-basic-liquidity-data` in the current mainline.
## Requirements
### Requirement: CN_A 鏃ラ娴佸姩鎬у瓧娈靛叆搴?
绯荤粺 SHALL 涓?`pams_ohlcv_daily` 涓?`market='CN_A'` 鐨勬棩绾胯褰曞瓨鍌ㄤ笌 `trade_date + symbol` 瀵归綈鐨勬棩棰戞祦鍔ㄦ€у瓧娈碉紝鑷冲皯鍖呮嫭 `turnover_rate`銆乣turnover_rate_f`銆乣volume_ratio`銆傜郴缁?MAY 涓€骞跺瓨鍌?`float_share`銆乣free_share`銆乣circ_mv` 浣滀负瀹¤涓庢墿灞曡緟鍔╁瓧娈点€傜郴缁?MUST 淇濇寔鐜版湁 `volume` 鍜?`turnover` 瀛楁璇箟涓嶅彉锛屽叾涓?`turnover` 缁х画琛ㄧず鎴愪氦棰濓紝涓嶅緱鏀逛綔鎹㈡墜鐜囥€?

绯荤粺 SHALL 涓?`pams_ohlcv_daily` 涓?`market='CN_A'` 鐨勬棩绾胯褰曞瓨鍌ㄤ笌 `trade_date + symbol` 瀵归綈鐨勬棩棰戞祦鍔ㄦ€у瓧娈碉紝鑷冲皯鍖呮嫭 `turnover_rate`銆乣turnover_rate_f`銆乣volume_ratio`銆傜郴缁?MAY 涓€骞跺瓨鍌?`float_share`銆乣free_share`銆乣circ_mv` 浣滀负瀹¤涓庢墿灞曡緟鍔╁瓧娈点€傜郴缁?MUST 淇濇寔鐜版湁 `volume` 鍜?`turnover` 瀛楁璇箟涓嶅彉锛屽叾涓?`turnover` 缁х画琛ㄧず鎴愪氦棰濓紝涓嶅緱鏀逛綔鎹㈡墜鐜囥€?

#### Scenario: daily_basic 瀛楁鎴愬姛鍐欏叆涓昏〃
- **WHEN** 瀵煎叆閾捐矾澶勭悊鏌愪釜 `CN_A` 鑲＄エ鍦ㄦ煇涓?`trade_date` 鐨?daily_basic 璁板綍
- **THEN** 绯荤粺 SHALL 灏?`turnover_rate`銆乣turnover_rate_f`銆乣volume_ratio` 鍐欏叆涓庤 `symbol + trade_date` 瀵瑰簲鐨?`pams_ohlcv_daily` 琛?

#### Scenario: 鐜版湁鎴愪氦棰濆瓧娈佃涔変繚鎸佷笉鍙?
- **WHEN** 绯荤粺瀹屾垚娴佸姩鎬у瓧娈靛洖濉?
- **THEN** 鐜版湁 `turnover` 瀛楁 SHALL 缁х画琛ㄧず鎴愪氦棰?
- **THEN** 绯荤粺 SHALL NOT 鐢?`turnover_rate` 鎴?`turnover_rate_f` 瑕嗙洊鎴栭噸鍛藉悕 `turnover`### Requirement: 杩愯鏃跺巻鍙插抚閫忎紶鍙€夋祦鍔ㄦ€у瓧娈?
绯荤粺 SHALL 鍦?`load_ohlcv_daily()` 杩斿洖鐨?history frame 涓寜鍚屼竴 `date + symbol` 閫忎紶宸插瓨鍦ㄧ殑娴佸姩鎬у瓧娈碉紝浣?MUST 淇濇寔褰撳墠蹇呴渶 canonical 鍒楅泦鍚堜笉鍙樸€傝嫢娴佸姩鎬у瓧娈靛湪琛ㄤ腑涓嶅瓨鍦ㄦ垨鏄犲皠鏈厤缃紝baseline 杩愯 MUST 缁х画鎴愬姛锛屼笉寰楀洜鏂板瀛楁缂哄け鑰屾敼鍙樼幇鏈夐粯璁よ涓恒€?

#### Scenario: 琛ㄤ腑瀛樺湪娴佸姩鎬у瓧娈垫椂閫忎紶鍒?history frame
- **WHEN** `pams_ohlcv_daily` 鍖呭惈 `turnover_rate_f` 涓?schema mapping 宸查厤缃?
- **THEN** `load_ohlcv_daily()` 杩斿洖鐨?history frame SHALL 鍖呭惈 `turnover_rate_f`

#### Scenario: 鍩虹嚎閰嶇疆鏈惎鐢ㄦ柊瀛楁鏃朵繚鎸佸吋瀹?
- **WHEN** 杩愯浣跨敤褰撳墠 baseline 閰嶇疆涓旀湭閰嶇疆浠讳綍鏂版祦鍔ㄦ€у瓧娈垫槧灏?
- **THEN** `load_ohlcv_daily()` SHALL 缁х画杩斿洖鐜版湁蹇呴渶鍒?
- **THEN** 鍥炴祴缁撴灉 SHALL NOT 鍥犳柊澧炲瓧娈电己澶辫€屽け璐?

### Requirement: 鎹㈡墜鐜囪繃婊や娇鐢ㄧ嫭绔嬮厤缃笖榛樿鍏抽棴
绯荤粺 SHALL 鎻愪緵鐙珛浜庣幇鏈夋垚浜ら杩囨护鐨勬崲鎵嬬巼杩囨护閰嶇疆銆傞粯璁ゆ儏鍐典笅鎹㈡墜鐜囪繃婊ゅ叧闂紝鐜版湁 `min_avg_turnover_20d` 鎴愪氦棰濊繃婊ゅ拰 baseline 缁撴灉 MUST 淇濇寔涓嶅彉銆傚惎鐢ㄥ悗锛岀郴缁?SHALL 浠呬娇鐢ㄦ埅鑷冲綋鏃ョ殑鍘嗗彶 `turnover_rate` 鎴?`turnover_rate_f` 璁＄畻 rolling 20 鏃ュ潎鍊硷紝骞舵嵁姝よ繃婊ゅ€欓€夎偂绁ㄣ€?

绯荤粺 SHALL 鎻愪緵鐙珛浜庣幇鏈夋垚浜ら杩囨护鐨勬崲鎵嬬巼杩囨护閰嶇疆銆傞粯璁ゆ儏鍐典笅鎹㈡墜鐜囪繃婊ゅ叧闂紝鐜版湁 `min_avg_turnover_20d` 鎴愪氦棰濊繃婊ゅ拰 baseline 缁撴灉 MUST 淇濇寔涓嶅彉銆傚惎鐢ㄥ悗锛岀郴缁?SHALL 浠呬娇鐢ㄦ埅鑷冲綋鏃ョ殑鍘嗗彶 `turnover_rate` 鎴?`turnover_rate_f` 璁＄畻 rolling 20 鏃ュ潎鍊硷紝骞舵嵁姝よ繃婊ゅ€欓€夎偂绁ㄣ€?

#### Scenario: 榛樿閰嶇疆涓嶆敼鍙樼幇鏈?amount-based 杩囨护
- **WHEN** 鐢ㄦ埛鏈缃?`min_avg_turnover_rate_20d` 鎴栧叾鍊间负 `0`
- **THEN** 绯荤粺 SHALL 涓嶅惎鐢ㄦ崲鎵嬬巼杩囨护
- **THEN** 鐜版湁 `min_avg_turnover_20d` 鎴愪氦棰濊繃婊よ涓?SHALL 淇濇寔涓嶅彉

#### Scenario: 鍚敤鑷敱娴侀€氭崲鎵嬬巼杩囨护鏃朵粎浣跨敤鍘嗗彶绐楀彛
- **WHEN** 鐢ㄦ埛璁剧疆 `min_avg_turnover_rate_20d > 0` 涓?`turnover_rate_field='turnover_rate_f'`
- **THEN** 绯荤粺 SHALL 鍩轰簬鎴嚦褰撴棩鐨?`turnover_rate_f` 鍘嗗彶绐楀彛璁＄畻 20 鏃ュ潎鍊?
- **THEN** 绯荤粺 SHALL NOT 浣跨敤鏈潵浜ゆ槗鏃ョ殑鎹㈡墜鐜囧€煎弬涓庡綋鏃ヨ繃婊ゅ垽鏂?## Requirement: 娴佸姩鎬у瓧娈垫牎楠屼笌瀹¤
褰撴崲鎵嬬巼杩囨护鍚敤鏃讹紝绯荤粺 MUST 鍦ㄨ繍琛屽墠妫€鏌ユ墍閫夋祦鍔ㄦ€у瓧娈垫槸鍚﹀瓨鍦ㄣ€佹槸鍚︿负闈炶礋鏁板€笺€佹槸鍚︽寜 `trade_date + symbol` 鍚屾棩瀵归綈銆傜郴缁?MUST NOT 閫氳繃 `bfill` 鎴栬法鏃?future fill 鍥炲～缂哄け鎹㈡墜鐜囧€笺€傚瓧娈典笉鍙敤鏃讹紝绯荤粺 SHALL 杩斿洖鏄庣‘鐨勬牎楠屽け璐ユ垨瀹¤鍛婅锛岃€屼笉鏄潤榛樺洖閫€鎴愭垚浜ら杩囨护銆?

#### Scenario: 鍚敤鎹㈡墜鐜囪繃婊や絾瀛楁缂哄け
- **WHEN** 鐢ㄦ埛鍚敤 `min_avg_turnover_rate_20d`锛屼絾鎵€閫?`turnover_rate_field` 鍦ㄨ〃涓笉瀛樺湪鎴栨槧灏勭己澶?
- **THEN** 鏁版嵁鏍￠獙 SHALL 杩斿洖澶辫触鎴栨槑纭憡璀?
- **THEN** 绯荤粺 SHALL NOT 闈欓粯鏀圭敤 `turnover` 鎴愪氦棰濆瓧娈电户缁繍琛?

#### Scenario: 鏃ラ娴佸姩鎬у瓧娈靛瓨鍦ㄧ己鍙?
- **WHEN** 鏌愯偂绁ㄦ煇鏃ョ己灏?`turnover_rate` 鎴?`turnover_rate_f`
- **THEN** 绯荤粺 SHALL 淇濈暀璇ュ€间负缂哄け鎬佹垨灏嗚鏃ユ爣璁颁负涓嶅彲鐢ㄤ簬瀵瑰簲杩囨护
- **THEN** 绯荤粺 SHALL NOT 浣跨敤鏈潵鏃ユ湡鐨勫€煎洖濉缂哄彛

### Requirement: 杩愯鏃跺巻鍙插抚閫忎紶鍙€夋祦鍔ㄦ€у瓧娈?
绯荤粺 SHALL 鍦?`load_ohlcv_daily()` 杩斿洖鐨?history frame 涓寜鍚屼竴 `date + symbol` 閫忎紶宸插瓨鍦ㄧ殑娴佸姩鎬у瓧娈碉紝浣?MUST 淇濇寔褰撳墠蹇呴渶 canonical 鍒楅泦鍚堜笉鍙樸€傝嫢娴佸姩鎬у瓧娈靛湪琛ㄤ腑涓嶅瓨鍦ㄦ垨鏄犲皠鏈厤缃紝baseline 杩愯 MUST 缁х画鎴愬姛锛屼笉寰楀洜鏂板瀛楁缂哄け鑰屾敼鍙樼幇鏈夐粯璁よ涓恒€?

#### Scenario: 琛ㄤ腑瀛樺湪娴佸姩鎬у瓧娈垫椂閫忎紶鍒?history frame
- **WHEN** `pams_ohlcv_daily` 鍖呭惈 `turnover_rate_f` 涓?schema mapping 宸查厤缃?
- **THEN** `load_ohlcv_daily()` 杩斿洖鐨?history frame SHALL 鍖呭惈 `turnover_rate_f`

#### Scenario: 鍩虹嚎閰嶇疆鏈惎鐢ㄦ柊瀛楁鏃朵繚鎸佸吋瀹?
- **WHEN** 杩愯浣跨敤褰撳墠 baseline 閰嶇疆涓旀湭閰嶇疆浠讳綍鏂版祦鍔ㄦ€у瓧娈垫槧灏?
- **THEN** `load_ohlcv_daily()` SHALL 缁х画杩斿洖鐜版湁蹇呴渶鍒?
- **THEN** 鍥炴祴缁撴灉 SHALL NOT 鍥犳柊澧炲瓧娈电己澶辫€屽け璐?

### Requirement: 娴佸姩鎬у瓧娈垫牎楠屼笌瀹¤
褰撴崲鎵嬬巼杩囨护鍚敤鏃讹紝绯荤粺 MUST 鍦ㄨ繍琛屽墠妫€鏌ユ墍閫夋祦鍔ㄦ€у瓧娈垫槸鍚﹀瓨鍦ㄣ€佹槸鍚︿负闈炶礋鏁板€笺€佹槸鍚︽寜 `trade_date + symbol` 鍚屾棩瀵归綈銆傜郴缁?MUST NOT 閫氳繃 `bfill` 鎴栬法鏃?future fill 鍥炲～缂哄け鎹㈡墜鐜囧€笺€傚瓧娈典笉鍙敤鏃讹紝绯荤粺 SHALL 杩斿洖鏄庣‘鐨勬牎楠屽け璐ユ垨瀹¤鍛婅锛岃€屼笉鏄潤榛樺洖閫€鎴愭垚浜ら杩囨护銆?

#### Scenario: 鍚敤鎹㈡墜鐜囪繃婊や絾瀛楁缂哄け
- **WHEN** 鐢ㄦ埛鍚敤 `min_avg_turnover_rate_20d`锛屼絾鎵€閫?`turnover_rate_field` 鍦ㄨ〃涓笉瀛樺湪鎴栨槧灏勭己澶?
- **THEN** 鏁版嵁鏍￠獙 SHALL 杩斿洖澶辫触鎴栨槑纭憡璀?
- **THEN** 绯荤粺 SHALL NOT 闈欓粯鏀圭敤 `turnover` 鎴愪氦棰濆瓧娈电户缁繍琛?

#### Scenario: 鏃ラ娴佸姩鎬у瓧娈靛瓨鍦ㄧ己鍙?
- **WHEN** 鏌愯偂绁ㄦ煇鏃ョ己灏?`turnover_rate` 鎴?`turnover_rate_f`
- **THEN** 绯荤粺 SHALL 淇濈暀璇ュ€间负缂哄け鎬佹垨灏嗚鏃ユ爣璁颁负涓嶅彲鐢ㄤ簬瀵瑰簲杩囨护
- **THEN** 绯荤粺 SHALL NOT 浣跨敤鏈潵鏃ユ湡鐨勫€煎洖濉缂哄彛

