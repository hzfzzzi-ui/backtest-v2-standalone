# market-snapshot-daily Specification

## Purpose

Define the formal capability boundary for `market-snapshot-daily` in the current mainline.
## Requirements
### Requirement: 绯荤粺蹇呴』涓烘寚瀹氫氦鏄撴棩鐢熸垚鐙珛鐨勫叏 A 鑲″競鍦哄揩鐓?
绯荤粺 SHALL 鏀寔鎸変氦鏄撴棩鐢熸垚鐙珛浜庡洖娴嬪疄楠岀殑 `market_snapshot.json`锛屽苟灏嗕骇鐗╁啓鍏?`outputs/market_snapshots/YYYY-MM-DD/`銆傝蹇収蹇呴』浠ュ崟涓€ `trade_date` 涓洪敋鐐癸紝涓旀墍鏈夊瓧娈甸粯璁ゅ彧浣跨敤璇ヤ氦鏄撴棩鏀剁洏鍚庡強鍘嗗彶鍙緱鏁版嵁銆?

绯荤粺 SHALL 鏀寔鎸変氦鏄撴棩鐢熸垚鐙珛浜庡洖娴嬪疄楠岀殑 `market_snapshot.json`锛屽苟灏嗕骇鐗╁啓鍏?`outputs/market_snapshots/YYYY-MM-DD/`銆傝蹇収蹇呴』浠ュ崟涓€ `trade_date` 涓洪敋鐐癸紝涓旀墍鏈夊瓧娈甸粯璁ゅ彧浣跨敤璇ヤ氦鏄撴棩鏀剁洏鍚庡強鍘嗗彶鍙緱鏁版嵁銆?

#### Scenario: 涓哄崟涓氦鏄撴棩鐢熸垚蹇収
- **WHEN** 鐢ㄦ埛鎴栫郴缁熻姹傛瀯寤烘煇涓€浜ゆ槗鏃ョ殑甯傚満蹇収
- **THEN** 绯荤粺蹇呴』鍦ㄥ搴旀棩鏈熺洰褰曚笅鐢熸垚 `market_snapshot.json`
- **AND** 浜х墿涓嶅緱鍐欏叆鐜版湁鍥炴祴瀹為獙鐩綍

#### Scenario: 鍚屼竴浜ゆ槗鏃ラ噸澶嶆瀯寤?
- **WHEN** 鍚屼竴 `trade_date` 琚啀娆℃瀯寤?
- **THEN** 绯荤粺蹇呴』浠ュ箓绛夋柟寮忛噸鍐欒鏃ユ湡蹇収
- **AND** 涓嶅緱鏀瑰彉鏃犲叧鏃ユ湡鐩綍鐨勫唴瀹?## Requirement: 甯傚満蹇収蹇呴』瑕嗙洊鍏眰甯傚満鐘舵€佸瓧娈?
绯荤粺 SHALL 鍦?`market_snapshot.json` 涓嚦灏戣緭鍑轰互涓嬪叚灞傜粨鏋勶細`index_layer`銆乣style_layer`銆乣breadth_layer`銆乣liquidity_layer`銆乣sentiment_layer`銆乣risk_layer`銆傛瘡灞傚瓧娈靛繀椤绘湁鍥哄畾璇箟锛屼笉寰楁妸涓嶅悓灞傜殑鎸囨爣娣锋垚鍗曚竴鍖垮悕鍒嗘暟銆?

#### Scenario: 杈撳嚭鏈€灏忓叚灞?schema
- **WHEN** 甯傚満蹇収鏋勫缓瀹屾垚
- **THEN** `market_snapshot.json` 蹇呴』鍖呭惈鍏眰瀛楁瀵硅薄
- **AND** 缂哄け瀛楁蹇呴』浠?`warnings` 鎴栬鐩栫巼淇℃伅鏄惧紡璇存槑

#### Scenario: 浣跨敤鍘嗗彶婊氬姩鍙ｅ緞
- **WHEN** 鏌愬瓧娈甸渶瑕?zscore銆乹uantile 鎴?heat 璁＄畻
- **THEN** 绯荤粺蹇呴』浠呬娇鐢?`t` 鏃ュ強涔嬪墠鐨勬粴鍔ㄧ獥鍙?
- **AND** 涓嶅緱浣跨敤鍏ㄦ牱鏈粺璁￠噺

### Requirement: 绯荤粺蹇呴』杈撳嚭鍙汉宸ラ槄璇荤殑甯傚満绠€鎶?
绯荤粺 SHALL 鍩轰簬鍚屼竴浠藉競鍦哄揩鐓ф暟鎹敓鎴?`market_brief.md`锛岀敤浜庢敹鐩樺悗澶嶇洏鍜屽悗缁崐鑷姩鍖栨棩鏇撮槄璇汇€?

绯荤粺 SHALL 鍩轰簬鍚屼竴浠藉競鍦哄揩鐓ф暟鎹敓鎴?`market_brief.md`锛岀敤浜庢敹鐩樺悗澶嶇洏鍜屽悗缁崐鑷姩鍖栨棩鏇撮槄璇汇€?

#### Scenario: 鐢熸垚甯傚満绠€鎶?
- **WHEN** 鏌愭棩甯傚満蹇収鏋勫缓瀹屾垚
- **THEN** 绯荤粺蹇呴』鍦ㄥ悓鐩綍涓嬬敓鎴?`market_brief.md`
- **AND** 绠€鎶ヨ嚦灏戝寘鍚粖鏃ョ粨璁恒€佹寚鏁颁笌椋庢牸銆佸箍搴︿笌鎴愪氦銆佹儏缁姸鎬併€侀闄╂彁绀轰簲涓儴鍒?## Requirement: 绯荤粺蹇呴』璁板綍鏁版嵁鏉ユ簮銆佽鐩栫巼鍜屽憡璀?
绯荤粺 SHALL 涓哄競鍦哄揩鐓ц褰?`sources`銆乣warnings` 浠ュ強鑳藉瑙ｉ噴瑕嗙洊涓嶈冻鎴栧彂甯冩椂闂存粸鍚庣殑杈呭姪淇℃伅锛屼互淇濊瘉鍚庣画鐮旂┒鍜?UI 鍙互鍒ゆ柇璇ュ揩鐓ф槸鍚﹀彲闈犮€?

#### Scenario: 鏉ユ簮鍙拷婧?
- **WHEN** 甯傚満蹇収鐢熸垚瀹屾垚
- **THEN** 浜х墿蹇呴』璁板綍鍚勫眰涓昏瀛楁鐨勬暟鎹潵婧?
- **AND** 鏉ユ簮蹇呴』鑳藉鍖哄垎浜ゆ槗鎵€/鎸囨暟鍏徃/鏈湴娲剧敓璁＄畻绛変笉鍚屾潵婧愮被鍨?

#### Scenario: 鏁版嵁涓嶈冻鏃舵樉寮忓憡璀?
- **WHEN** 鏌愬眰瀛楁缂哄け銆佹粸鍚庢垨瑕嗙洊涓嶈冻
- **THEN** 绯荤粺蹇呴』鍦?`warnings` 涓褰曞師鍥?
- **AND** 涓嶅緱闈欓粯鍐欓浂鎴栦吉閫犲彲鐢ㄧ姸鎬?

### Requirement: 棣栬疆甯傚満蹇収涓嶅緱鐩存帴鏀瑰彉绛栫暐鎴?baseline 琛屼负
绯荤粺 SHALL 灏嗗競鍦哄揩鐓у畾浣嶄负鐙珛鐨勬弿杩版€т笌鐮旂┒杈呭姪浜х墿锛岄杞疄鐜颁笉寰楃洿鎺ユ敼鍙樼幇鏈?`baseline_V9.1` 浜ゆ槗閫昏緫銆佸洖娴嬫寚鏍囨垨 `run_meta` 涓?schema銆?

绯荤粺 SHALL 灏嗗競鍦哄揩鐓у畾浣嶄负鐙珛鐨勬弿杩版€т笌鐮旂┒杈呭姪浜х墿锛岄杞疄鐜颁笉寰楃洿鎺ユ敼鍙樼幇鏈?`baseline_V9.1` 浜ゆ槗閫昏緫銆佸洖娴嬫寚鏍囨垨 `run_meta` 涓?schema銆?

#### Scenario: 鏋勫缓甯傚満蹇収涓嶅奖鍝?baseline
- **WHEN** 寮€鍚垨鍏抽棴甯傚満蹇収鏋勫缓
- **THEN** 鐜版湁鍥炴祴瀹為獙鐨?`perf.json`銆乣run_meta.json`銆乣nav.csv` 鍙ｅ緞蹇呴』淇濇寔涓嶅彉
- **AND** `market_snapshot` 涓嶅緱琚啓鍏ョ幇鏈?baseline 浜х墿閾句綔涓哄繀闇€瀛楁### Requirement: 甯傚満蹇収蹇呴』瑕嗙洊鍏眰甯傚満鐘舵€佸瓧娈?
绯荤粺 SHALL 鍦?`market_snapshot.json` 涓嚦灏戣緭鍑轰互涓嬪叚灞傜粨鏋勶細`index_layer`銆乣style_layer`銆乣breadth_layer`銆乣liquidity_layer`銆乣sentiment_layer`銆乣risk_layer`銆傛瘡灞傚瓧娈靛繀椤绘湁鍥哄畾璇箟锛屼笉寰楁妸涓嶅悓灞傜殑鎸囨爣娣锋垚鍗曚竴鍖垮悕鍒嗘暟銆?

#### Scenario: 杈撳嚭鏈€灏忓叚灞?schema
- **WHEN** 甯傚満蹇収鏋勫缓瀹屾垚
- **THEN** `market_snapshot.json` 蹇呴』鍖呭惈鍏眰瀛楁瀵硅薄
- **AND** 缂哄け瀛楁蹇呴』浠?`warnings` 鎴栬鐩栫巼淇℃伅鏄惧紡璇存槑

#### Scenario: 浣跨敤鍘嗗彶婊氬姩鍙ｅ緞
- **WHEN** 鏌愬瓧娈甸渶瑕?zscore銆乹uantile 鎴?heat 璁＄畻
- **THEN** 绯荤粺蹇呴』浠呬娇鐢?`t` 鏃ュ強涔嬪墠鐨勬粴鍔ㄧ獥鍙?
- **AND** 涓嶅緱浣跨敤鍏ㄦ牱鏈粺璁￠噺

### Requirement: 绯荤粺蹇呴』璁板綍鏁版嵁鏉ユ簮銆佽鐩栫巼鍜屽憡璀?
绯荤粺 SHALL 涓哄競鍦哄揩鐓ц褰?`sources`銆乣warnings` 浠ュ強鑳藉瑙ｉ噴瑕嗙洊涓嶈冻鎴栧彂甯冩椂闂存粸鍚庣殑杈呭姪淇℃伅锛屼互淇濊瘉鍚庣画鐮旂┒鍜?UI 鍙互鍒ゆ柇璇ュ揩鐓ф槸鍚﹀彲闈犮€?

#### Scenario: 鏉ユ簮鍙拷婧?
- **WHEN** 甯傚満蹇収鐢熸垚瀹屾垚
- **THEN** 浜х墿蹇呴』璁板綍鍚勫眰涓昏瀛楁鐨勬暟鎹潵婧?
- **AND** 鏉ユ簮蹇呴』鑳藉鍖哄垎浜ゆ槗鎵€/鎸囨暟鍏徃/鏈湴娲剧敓璁＄畻绛変笉鍚屾潵婧愮被鍨?

#### Scenario: 鏁版嵁涓嶈冻鏃舵樉寮忓憡璀?
- **WHEN** 鏌愬眰瀛楁缂哄け銆佹粸鍚庢垨瑕嗙洊涓嶈冻
- **THEN** 绯荤粺蹇呴』鍦?`warnings` 涓褰曞師鍥?
- **AND** 涓嶅緱闈欓粯鍐欓浂鎴栦吉閫犲彲鐢ㄧ姸鎬?

