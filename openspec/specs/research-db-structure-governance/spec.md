# research-db-structure-governance Specification

## Purpose

Define the formal capability boundary for `research-db-structure-governance` in the current mainline.
## Requirements
### Requirement: 鏍稿績鐮旂┒琛ㄧ粨鏋勬不鐞嗗垎灞?绯荤粺 MUST 瀵瑰叡浜?PostgreSQL `public` schema 涓殑鏁版嵁搴撳璞¤繘琛屽垎灞傛不鐞嗭紝骞跺皢鐮旂┒涓荤嚎鏁版嵁搴撲紭鍖栭檺鍒跺湪鏄庣‘瀹氫箟鐨勬牳蹇冪爺绌惰〃鑼冨洿鍐呫€?
绯荤粺 MUST 瀵瑰叡浜?PostgreSQL `public` schema 涓殑鏁版嵁搴撳璞¤繘琛屽垎灞傛不鐞嗭紝骞跺皢鐮旂┒涓荤嚎鏁版嵁搴撲紭鍖栭檺鍒跺湪鏄庣‘瀹氫箟鐨勬牳蹇冪爺绌惰〃鑼冨洿鍐呫€?
#### Scenario: 璇嗗埆鏍稿績鐮旂┒琛?- **WHEN** 鍥㈤槦鍒跺畾鎴栬瘎瀹″洖娴嬬郴缁熸暟鎹簱缁撴瀯浼樺寲鏂规
- **THEN** 鏂规 MUST 灏?`pams_ohlcv_daily`銆乣pit_index_daily`銆乣pit_index_constituents`銆乣pit_industry_history`銆乣pit_security_master`銆乣pit_st_history` 璇嗗埆涓烘牳蹇冪爺绌惰〃
- **THEN** 涓嶅睘浜庝笂杩伴泦鍚堢殑鍏变韩涓氬姟琛?MUST NOT 鍥犫€滈『鎵嬩紭鍖栤€濊绾冲叆鍚屼竴杞牳蹇冪爺绌舵敼鍔?
#### Scenario: 璇嗗埆澶囦唤涓庝复鏃跺璞?- **WHEN** 鍥㈤槦鐩樼偣 `public` schema 涓殑澶囦唤琛ㄦ垨涓存椂鑴氭湰瀵硅薄
- **THEN** `*_backup_*` 鎸佷箙琛?MUST 琚涓烘不鐞嗗€哄姟鑰岄潪鏍稿績鐮旂┒琛?- **THEN** 浼氳瘽绾?`tmp_*` 琛?MUST 琚涓鸿剼鏈复鏃跺璞★紝涓嶅緱琚鍒や负闀挎湡缁撴瀯璧勪骇### Requirement: L2 鏁版嵁搴撲紭鍖栧彧鍏佽闈炶涔夊瀷 DDL
绯荤粺 SHALL 灏?L2 鏁版嵁搴撶粨鏋勪紭鍖栭檺瀹氫负涓嶄細鏀瑰彉鐮旂┒鍙ｅ緞銆佹煡璇㈢粨鏋滈泦鍜岃繍琛屾椂鍚堝悓鐨勯潪璇箟鍨?DDL銆?
#### Scenario: 瀵?PIT 鎴愬垎琛ㄦ墽琛?L2 浼樺寲
- **WHEN** 鍥㈤槦瀵?`pit_index_constituents` 鍒跺畾棣栨壒 L2 浼樺寲
- **THEN** 鍏佽鐨?DDL MUST 闄愬畾涓烘柊澧為潪鍞竴绱㈠紩銆佹敞閲婃垨 runbook 閰嶅瀵硅薄
- **THEN** 璇ヤ紭鍖?MUST NOT 鏀瑰彉琛ㄥ瓧娈靛惈涔夈€佹煡璇㈡潯浠惰涔夋垨 Universe 缁撴灉闆嗗悎

#### Scenario: 瀵?PIT 琛屼笟鍘嗗彶琛ㄦ墽琛?L2 浼樺寲
- **WHEN** 鍥㈤槦瀵?`pit_industry_history` 鍒跺畾棣栨壒 L2 浼樺寲
- **THEN** 浼樺寲 MUST 浼樺厛瑕嗙洊 `industry_l1 + 鐢熸晥鍖洪棿 + ts_code` 鏌ヨ妯″紡
- **THEN** 璇ヤ紭鍖?MUST NOT 淇敼 `start_date` / `end_date` 鐨?PIT 瑙ｉ噴鏂瑰紡

### Requirement: L2 DDL 蹇呴』鍐呭缓楠岃瘉涓庡洖閫€
姣忎竴涓?L2 鏁版嵁搴撶粨鏋勫彉鏇?MUST 鍚屾椂鎻愪緵鎵ц鍓嶅熀绾裤€佹墽琛屽悗楠岃瘉鍜岄潪鐮村潖鎬у洖閫€鏂规銆?
#### Scenario: 鎵ц绱㈠紩鍙樻洿鍓?- **WHEN** 鍥㈤槦鍑嗗鎵ц浠讳綍 L2 绱㈠紩 DDL
- **THEN** 鏂规 MUST 璁板綍瀵瑰簲涓绘煡璇㈢殑 `EXPLAIN` 鍩虹嚎
- **THEN** 鏂规 MUST 璁板綍鐩爣琛ㄧ殑鍏抽敭琛屾暟鎴栧幓閲嶇粺璁★紝浣滀负璇箟鏍￠獙渚濇嵁

#### Scenario: 鎵ц绱㈠紩鍙樻洿鍚?- **WHEN** 鍥㈤槦瀹屾垚浠讳綍 L2 绱㈠紩 DDL
- **THEN** 鏂规 MUST 閲嶆柊鎵ц鐩稿悓鏌ヨ鐨?`EXPLAIN` 鎴?`EXPLAIN ANALYZE`
- **THEN** 鏂规 MUST 楠岃瘉鍏抽敭缁撴灉闆嗕笌鍙樻洿鍓嶄竴鑷?- **THEN** 鏂规 MUST 鎻愪緵 `DROP INDEX CONCURRENTLY` 绾у埆鐨勫洖閫€ DDL

### Requirement: 绾︽潫澧炲己涓庤繍琛屾椂鏁版嵁婧愬垏鎹㈠睘浜?L3
浠讳綍鍙兘鏀瑰彉鍐欏叆鍚堝悓銆佽繍琛屾椂鏁版嵁鏉ユ簮銆佸叡浜簱鍏煎鎬ф垨 PIT 璇箟杈圭晫鐨勭粨鏋勮皟鏁?MUST 浣滀负 L3 鍙樻洿鍗曠嫭绔嬮」銆?
#### Scenario: 鎻愯澧炲姞绾︽潫
- **WHEN** 鍥㈤槦鎻愯涓?`pit_index_constituents`銆乣pit_industry_history` 鎴?`pit_st_history` 澧炲姞涓婚敭銆佸敮涓€绾︽潫銆侀潪绌虹害鏉熸垨鍖洪棿閲嶅彔绾︽潫
- **THEN** 璇ユ彁璁?MUST 琚綊绫讳负 L3
- **THEN** 鍦ㄧ嫭绔?spec銆佹暟鎹璁″拰鍥炲綊楠岃瘉瀹屾垚鍓?SHALL NOT 鐩存帴瀹炴柦

#### Scenario: 鎻愯鍒囨崲浜ゆ槗鏃ユ棩鍘嗙湡婧?- **WHEN** 鍥㈤槦鎻愯灏嗚繍琛屾椂浜ゆ槗鏃ユ棩鍘嗕富鏉ユ簮浠庣幇鏈変环鏍艰〃鍒囨崲鍒?`pit_trade_cal`
- **THEN** 璇ユ彁璁?MUST 琚綊绫讳负 L3
- **THEN** 鍦ㄦ槑纭獙璇佸彛寰勪竴鑷存€т箣鍓?SHALL NOT 涓庣储寮曚紭鍖栦竴骞跺疄鏂?
### Requirement: 鎸佷箙鍖栧浠借〃蹇呴』鍙楁不鐞嗙害鏉?绯荤粺 MUST 瀵?`public` schema 涓殑鎸佷箙鍖栧浠借〃寤虹珛娌荤悊杈圭晫锛岄伩鍏嶄竴娆℃€ц剼鏈骇鐗╅暱鏈熸贩鍏ヤ富缁撴瀯璁ょ煡銆?
绯荤粺 MUST 瀵?`public` schema 涓殑鎸佷箙鍖栧浠借〃寤虹珛娌荤悊杈圭晫锛岄伩鍏嶄竴娆℃€ц剼鏈骇鐗╅暱鏈熸贩鍏ヤ富缁撴瀯璁ょ煡銆?
#### Scenario: 鏂板鎸佷箙鍖栧浠借〃
- **WHEN** 鍥㈤槦闇€瑕佷负杩愯惀鎴栦慨澶嶇洰鐨勬柊澧炴寔涔呭寲澶囦唤琛?- **THEN** 璇ヨ〃 MUST 璁板綍鏉ユ簮銆佸垱寤烘棩鏈熴€侀鏈熶繚鐣欐湡鍜屽垹闄?杩佺Щ璐ｄ换浜?- **THEN** 璇ヨ〃 MUST NOT 琚爣璁颁负鏍稿績鐮旂┒琛?
#### Scenario: 鐩樼偣鏃㈡湁澶囦唤琛?- **WHEN** 鍥㈤槦鐩樼偣 `public` schema 涓棦鏈?`*_backup_*` 琛?- **THEN** 鐩樼偣缁撴灉 MUST 鏄庣‘杩欎簺琛ㄤ笉灞炰簬 baseline 涓荤嚎杩愯鏃朵緷璧?- **THEN** 鍚庣画濡傞渶杩佺Щ鎴栧垹闄わ紝蹇呴』閫氳繃鐙珛鍙樻洿鎵ц### Requirement: L2 鏁版嵁搴撲紭鍖栧彧鍏佽闈炶涔夊瀷 DDL
绯荤粺 SHALL 灏?L2 鏁版嵁搴撶粨鏋勪紭鍖栭檺瀹氫负涓嶄細鏀瑰彉鐮旂┒鍙ｅ緞銆佹煡璇㈢粨鏋滈泦鍜岃繍琛屾椂鍚堝悓鐨勯潪璇箟鍨?DDL銆?
#### Scenario: 瀵?PIT 鎴愬垎琛ㄦ墽琛?L2 浼樺寲
- **WHEN** 鍥㈤槦瀵?`pit_index_constituents` 鍒跺畾棣栨壒 L2 浼樺寲
- **THEN** 鍏佽鐨?DDL MUST 闄愬畾涓烘柊澧為潪鍞竴绱㈠紩銆佹敞閲婃垨 runbook 閰嶅瀵硅薄
- **THEN** 璇ヤ紭鍖?MUST NOT 鏀瑰彉琛ㄥ瓧娈靛惈涔夈€佹煡璇㈡潯浠惰涔夋垨 Universe 缁撴灉闆嗗悎

#### Scenario: 瀵?PIT 琛屼笟鍘嗗彶琛ㄦ墽琛?L2 浼樺寲
- **WHEN** 鍥㈤槦瀵?`pit_industry_history` 鍒跺畾棣栨壒 L2 浼樺寲
- **THEN** 浼樺寲 MUST 浼樺厛瑕嗙洊 `industry_l1 + 鐢熸晥鍖洪棿 + ts_code` 鏌ヨ妯″紡
- **THEN** 璇ヤ紭鍖?MUST NOT 淇敼 `start_date` / `end_date` 鐨?PIT 瑙ｉ噴鏂瑰紡

### Requirement: transactions 鐢熷懡鍛ㄦ湡涓昏〃灞炰簬涓氬姟浜嬪姟鍩熸寮忓璞?绯荤粺 SHALL 鍦ㄦ暟鎹簱缁撴瀯娌荤悊涓槑纭?`transactions` 鐢熷懡鍛ㄦ湡涓昏〃灞炰簬涓氬姟浜嬪姟鍩熸寮忓璞★紝骞朵笌鐮旂┒鏁版嵁鍩熴€佸疄楠屽煙鍒嗙銆?
#### Scenario: 浜嬪姟涓昏〃鍩熷綊灞炴竻鏅?- **WHEN** 鏂囨。鎴栧疄鐜板０鏄庢暟鎹簱瀵硅薄鐨勬寮忓綊灞?- **THEN** `transactions` 鐢熷懡鍛ㄦ湡涓昏〃 MUST 琚綊绫诲埌涓氬姟浜嬪姟鍩?
### Requirement: sim_account 姝ｅ紡瀵硅薄灞炰簬涓氬姟浜嬪姟鍩?绯荤粺 SHALL 鍦ㄦ暟鎹簱缁撴瀯娌荤悊涓槑纭?`accounts`銆乣holdings_snapshots`銆乣cash_ledger`銆乣sync_logs` 灞炰簬涓氬姟浜嬪姟鍩熸寮忓璞°€?
#### Scenario: sim_account 瀵硅薄鍩熷綊灞炴槑纭?- **WHEN** 鏂囨。鎴栧疄鐜板０鏄?`sim_account` 鐩稿叧瀵硅薄鐨勬寮忓綊灞?- **THEN** 杩欎簺瀵硅薄 MUST 琚綊绫诲埌涓氬姟浜嬪姟鍩?

