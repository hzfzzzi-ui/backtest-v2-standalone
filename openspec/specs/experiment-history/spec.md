# experiment-history Specification

## Purpose

Define the formal capability boundary for `experiment-history` in the current mainline.

## Requirements

### Requirement: 瀹為獙绱㈠紩鏂囦欢
绯荤粺 SHALL 鍦?`outputs/experiments/index.json` 缁存姢涓€涓叏灞€瀹為獙绱㈠紩锛屾瘡娆″洖娴嬪畬鎴愬悗鑷姩杩藉姞銆?

#### Scenario: 鍥炴祴瀹屾垚鍚庤拷鍔犵储寮?
- **WHEN** 涓€娆″洖娴嬪疄楠屾垚鍔熷畬鎴愬苟閫氳繃 stabilize 闃舵
- **THEN** 绯荤粺 SHALL 鍦?index.json 涓拷鍔犱竴鏉¤褰曪紝鍖呭惈 exp_id銆乴abel銆乧reated_at銆乻tatus銆乼otal_return銆乵ax_drawdown銆乻harpe銆乼rades銆乭as_report 瀛楁

#### Scenario: 鑷姩鐢熸垚鍙鏍囩
- **WHEN** workbench_config 鍖呭惈 strategy="SMA_CROSS", sma.fast_ma=5, sma.slow_ma=20, universe_mode="CUSTOM", 2 鍙爣鐨? price_adj="hfq", 鍖洪棿 2024-01~06
- **THEN** label 瀛楁 SHALL 涓?"SMA_CROSS 5/20 | CUSTOM 2鍙?| HFQ | 2024-01~06"

#### Scenario: index.json 涓嶅瓨鍦ㄦ椂鑷姩鍒涘缓
- **WHEN** index.json 鏂囦欢涓嶅瓨鍦紙棣栨杩愯鎴栨竻绌哄悗锛?
- **THEN** 绯荤粺 SHALL 鍒涘缓鏂扮殑 index.json 骞跺啓鍏?`[{...}]`

---

### Requirement: 瀹為獙鍒楄〃 API
绯荤粺 SHALL 鎻愪緵 `GET /api/backtest_v2/experiments` 绔偣杩斿洖瀹為獙鍒楄〃銆?

#### Scenario: 姝ｅ父杩斿洖鍒楄〃
- **WHEN** 瀹㈡埛绔皟鐢?GET /api/backtest_v2/experiments
- **THEN** 绯荤粺 SHALL 杩斿洖 index.json 鍐呭锛屾寜 created_at 鍊掑簭鎺掑垪锛堟渶鏂板湪鍓嶏級

#### Scenario: 鏃犲疄楠屾椂杩斿洖绌哄垪琛?
- **WHEN** index.json 涓虹┖鎴栦笉瀛樺湪
- **THEN** 绯荤粺 SHALL 杩斿洖 `[]`

#### Scenario: 瀛ゅ効璁板綍鑷姩娓呯悊
- **WHEN** index.json 涓煇鏉¤褰曠殑瀹為獙鐩綍宸蹭笉瀛樺湪
- **THEN** 绯荤粺 SHALL 鍦ㄨ繑鍥炲垪琛ㄦ椂杩囨护鎺夎鏉¤褰曪紝骞舵洿鏂?index.json

---

### Requirement: 瀹為獙鎶ュ憡鏌ョ湅 API
绯荤粺 SHALL 鎻愪緵 `GET /api/backtest_v2/experiments/{exp_id}/report` 绔偣杩斿洖 report.html銆?

#### Scenario: report.html 瀛樺湪
- **WHEN** 瀹㈡埛绔姹傛煇瀹為獙鐨勬姤鍛婁笖 report.html 瀛樺湪
- **THEN** 绯荤粺 SHALL 杩斿洖 HTML 鍐呭锛圕ontent-Type: text/html锛?

#### Scenario: report.html 涓嶅瓨鍦?
- **WHEN** 瀹㈡埛绔姹傛煇瀹為獙鐨勬姤鍛婁絾 report.html 涓嶅瓨鍦?
- **THEN** 绯荤粺 SHALL 杩斿洖 404

---

### Requirement: 鍒犻櫎鍗曚釜瀹為獙 API
绯荤粺 SHALL 鎻愪緵 `DELETE /api/backtest_v2/experiments/{exp_id}` 绔偣鍒犻櫎鍗曚釜瀹為獙銆?

#### Scenario: 鍒犻櫎鎴愬姛
- **WHEN** 瀹㈡埛绔皟鐢?DELETE 涓斿疄楠岀洰褰曞瓨鍦?
- **THEN** 绯荤粺 SHALL 鍒犻櫎瀹為獙鐩綍鍙婃墍鏈夊唴瀹癸紝浠?index.json 绉婚櫎瀵瑰簲璁板綍锛岃繑鍥?`{"status": "deleted"}`

#### Scenario: 瀹為獙涓嶅瓨鍦?
- **WHEN** 瀹㈡埛绔皟鐢?DELETE 浣嗗疄楠岀洰褰曚笉瀛樺湪
- **THEN** 绯荤粺 SHALL 杩斿洖 404

---

### Requirement: 娓呯┖鎵€鏈夊疄楠?API
绯荤粺 SHALL 鎻愪緵 `DELETE /api/backtest_v2/experiments` 绔偣娓呯┖鎵€鏈夊疄楠屻€?

#### Scenario: 娓呯┖鎴愬姛
- **WHEN** 瀹㈡埛绔皟鐢?DELETE /api/backtest_v2/experiments
- **THEN** 绯荤粺 SHALL 鍒犻櫎 experiments 鐩綍涓嬫墍鏈?exp_* 瀛愮洰褰曪紝閲嶇疆 index.json 涓?`[]`锛岃繑鍥?`{"status": "cleared", "count": N}`

---

### Requirement: stock_names.json 鎸佷箙鍖?
绯荤粺 SHALL 鍦?stabilize 闃舵灏嗕腑鏂囪偂绁ㄥ悕鏌ヨ缁撴灉鍐欏叆 `stock_names.json`銆?

#### Scenario: 姝ｅ父鍐欏叆
- **WHEN** portfolio_trades.csv 鍖呭惈 symbol 鍒楋紝鍚?600519.SH 鍜?000001.SZ
- **THEN** 绯荤粺 SHALL 鏌ヨ DB 鑾峰彇涓枃鍚嶇О锛屽啓鍏?stock_names.json 濡?`{"600519.SH": "璐靛窞鑼呭彴", "000001.SZ": "骞冲畨閾惰"}`

#### Scenario: 鏃犱氦鏄撹褰?
- **WHEN** portfolio_trades.csv 涓嶅瓨鍦ㄦ垨涓虹┖
- **THEN** 绯荤粺 SHALL 鍐欏叆绌?`stock_names.json` 濡?`{}`

---

### Requirement: tier 鎸佷箙鍖栧埌 run_meta.json
绯荤粺 SHALL 鍦?stabilize 闃舵灏嗙瓥鐣ヨ瘎绾?tier 鍐欏叆 run_meta.json銆?

#### Scenario: tier 鍐欏叆
- **WHEN** 鍥炴祴缁撴灉鍖呭惈 tier 瀛楁
- **THEN** run_meta.json 椤跺眰 SHALL 鍖呭惈 `"tier": "T0"` 瀛楁

---

### Requirement: 鍓嶇 History 闈㈡澘
鍓嶇 SHALL 鍦?Drawer 涓柊澧炪€屽疄楠屽巻鍙层€嶉潰鏉匡紝閫氳繃 Rail 绗?5 涓浘鏍囧垏鎹€?

#### Scenario: 闈㈡澘灞曠ず瀹為獙鍒楄〃
- **WHEN** 鐢ㄦ埛鐐瑰嚮 History 鍥炬爣
- **THEN** Drawer SHALL 鏄剧ず瀹為獙鍘嗗彶闈㈡澘锛屽寘鍚墍鏈夊疄楠屽崱鐗囷紝鎸夋椂闂村€掑簭鎺掑垪

#### Scenario: 瀹為獙鍗＄墖鍐呭
- **WHEN** 闈㈡澘娓叉煋涓€涓疄楠?
- **THEN** 鍗＄墖 SHALL 鏄剧ず锛氬彲璇绘爣绛撅紙绛栫暐鍚?鍙傛暟锛夈€佸洖娴嬪尯闂淬€佹牳蹇冩寚鏍囷紙鏀剁泭/鍥炴挙/澶忔櫘/浜ゆ槗鏁帮級銆佸垱寤烘椂闂淬€併€屾煡鐪嬫姤鍛娿€嶅拰銆屽姞杞界粨鏋溿€嶄袱涓寜閽?

#### Scenario: 鏌ョ湅鎶ュ憡
- **WHEN** 鐢ㄦ埛鐐瑰嚮銆屾煡鐪嬫姤鍛娿€嶆寜閽?
- **THEN** 绯荤粺 SHALL 鍦ㄦ柊鏍囩椤垫墦寮€璇ュ疄楠岀殑 report.html

#### Scenario: 鍔犺浇缁撴灉鍒板伐浣滃彴
- **WHEN** 鐢ㄦ埛鐐瑰嚮銆屽姞杞界粨鏋溿€嶆寜閽?
- **THEN** 绯荤粺 SHALL 鍔犺浇璇ュ疄楠岀殑鍏ㄩ儴浜х墿鍒?state.active_artifacts锛岃鐩栧綋鍓嶅伐浣滃彴鐘舵€侊紝骞跺埛鏂版墍鏈夐潰鏉?

#### Scenario: 绌虹姸鎬?
- **WHEN** 瀹為獙鍒楄〃涓虹┖
- **THEN** 闈㈡澘 SHALL 鏄剧ず绌虹姸鎬佹彁绀恒€屾殏鏃犲疄楠岃褰曪紝杩愯鍥炴祴鍚庡皢鑷姩淇濆瓨銆?

#### Scenario: 娓呯┖鍏ㄩ儴
- **WHEN** 鐢ㄦ埛鐐瑰嚮銆屾竻绌恒€嶆寜閽苟纭
- **THEN** 绯荤粺 SHALL 璋冪敤 DELETE /api/backtest_v2/experiments 娓呯┖鎵€鏈夊疄楠岋紝鍒锋柊闈㈡澘

### Requirement: 鍘嗗彶瀹為獙涓嶅啀鎻愪緵 HTML 鎶ュ憡鏌ョ湅鍏ュ彛
鍓嶇鍘嗗彶瀹為獙闈㈡澘 SHALL 涓嶅啀鎻愪緵 `report.html` 鏌ョ湅鍏ュ彛锛岃€屾槸閫氳繃缁撴灉宸ヤ綔鍙板拰 Markdown 鎶ュ憡娑堣垂瀹為獙鎶ュ憡銆?

#### Scenario: 鍘嗗彶瀹為獙鍗＄墖鍔ㄤ綔
- **WHEN** 鐢ㄦ埛鏌ョ湅鍘嗗彶瀹為獙鍗＄墖
- **THEN** 鍗＄墖 MAY 鎻愪緵鍔犺浇瀹為獙缁撴灉涓庡姞杞藉疄楠岄厤缃?
- **THEN** 鍗＄墖 SHALL NOT 鎻愪緵鈥滄煡鐪?HTML 鎶ュ憡鈥濆姩浣?


