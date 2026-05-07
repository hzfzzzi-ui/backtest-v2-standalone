# backtest-report-export Specification

## Purpose

Define the formal capability boundary for `backtest-report-export` in the current mainline.

## Requirements

### Requirement: 瀵煎嚭鍥炴祴鎶ュ憡鎸夐挳
宸ヤ綔鍙?SHALL 鎻愪緵"瀵煎嚭鎶ュ憡"鎸夐挳锛岀偣鍑诲悗鍦ㄦ柊娴忚鍣ㄦ爣绛鹃〉涓墦寮€鍚庣宸茬敓鎴愮殑 report.html銆傚鏋滃悗绔?report.html 涓嶅瓨鍦紙鏃у疄楠岋級锛宖allback 鍒板墠绔湰鍦扮敓鎴愩€?

#### Scenario: 鍥炴祴瀹屾垚鍚庡鍑猴紙鍚庣鎶ュ憡瀛樺湪锛?
- **WHEN** 鐢ㄦ埛鐐瑰嚮"瀵煎嚭鎶ュ憡"鎸夐挳涓斿綋鍓嶅疄楠屾湁鍚庣鐢熸垚鐨?report.html
- **THEN** 绯荤粺 SHALL 鍦ㄦ柊鏍囩椤典腑鎵撳紑 `/api/backtest_v2/experiments/{exp_id}/report`

#### Scenario: 鍚庣鎶ュ憡涓嶅瓨鍦ㄦ椂 fallback
- **WHEN** 鐢ㄦ埛鐐瑰嚮"瀵煎嚭鎶ュ憡"鎸夐挳浣嗗悗绔?report.html 涓嶅瓨鍦紙404锛?
- **THEN** 绯荤粺 SHALL fallback 鍒板墠绔?generateReport() 鏈湴鐢熸垚骞跺湪鏂版爣绛鹃〉灞曠ず

#### Scenario: 鏃犲洖娴嬬粨鏋滄椂瀵煎嚭
- **WHEN** 鐢ㄦ埛鐐瑰嚮"瀵煎嚭鎶ュ憡"鎸夐挳浣嗘棤宸插畬鎴愮殑鍥炴祴缁撴灉
- **THEN** 绯荤粺 SHALL 鎻愮ず"璇峰厛杩愯鍥炴祴"

### Requirement: 鎶ュ憡鍖呭惈姒傝绔犺妭
鎶ュ憡 搂1 姒傝 SHALL 鍖呭惈绛栫暐鍩烘湰淇℃伅鍜屾牳蹇?KPI銆?

#### Scenario: 姒傝鍐呭
- **WHEN** 鎶ュ憡鐢熸垚
- **THEN** 搂1 SHALL 鏄剧ず锛氬疄楠?ID銆佸洖娴嬪尯闂达紙璧锋鏃ユ湡锛夈€佸熀鍑嗘寚鏁颁唬鐮?
- **THEN** 搂1 SHALL 鏄剧ず KPI 鍗＄墖锛氬勾鍖栨敹鐩婏紙%锛夈€佹渶澶у洖鎾わ紙%锛夈€佸鏅瘮鐜囥€佸崱灏旈┈姣旂巼銆佷氦鏄撴鏁般€佹崲鎵嬬巼
- **THEN** 搂1 SHALL 鏄剧ず绛栫暐璇勭骇锛圱ier锛?

### Requirement: 鎶ュ憡鍖呭惈鏀剁泭鍒嗘瀽绔犺妭
鎶ュ憡 搂2 鏀剁泭鍒嗘瀽 SHALL 鍖呭惈鏈堝害鍜屽勾搴︽敹鐩婄粺璁¤〃鏍笺€?

#### Scenario: 鏈堝害鏀剁泭琛?
- **WHEN** 鎶ュ憡鐢熸垚涓?NAV 鏁版嵁鍙敤
- **THEN** 搂2 SHALL 鍖呭惈鏈堝害鏀剁泭琛ㄦ牸锛岃涓哄勾浠斤紝鍒椾负 1-12 鏈?+ 骞村害鍚堣
- **THEN** 姣忔牸鏄剧ず璇ユ湀鏀剁泭鐜囷紙%锛夛紝姝ｅ€肩豢鑹层€佽礋鍊肩孩鑹?

#### Scenario: NAV 鏁版嵁涓嶅彲鐢?
- **WHEN** 鎶ュ憡鐢熸垚浣?NAV 鏁版嵁缂哄け
- **THEN** 搂2 SHALL 鏄剧ず"NAV 鏁版嵁涓嶅彲鐢?

### Requirement: 鎶ュ憡鍖呭惈椋庨櫓鍒嗘瀽绔犺妭
鎶ュ憡 搂3 椋庨櫓鍒嗘瀽 SHALL 鍖呭惈鏈€澶у洖鎾ゆ槑缁嗐€?

#### Scenario: 鍥炴挙鏄庣粏
- **WHEN** 鎶ュ憡鐢熸垚涓?NAV 鏁版嵁鍙敤
- **THEN** 搂3 SHALL 鏄剧ず鏈€澶у洖鎾ゅ箙搴︺€佸洖鎾よ捣濮嬫棩鏈熴€佸洖鎾ゆ渶浣庣偣鏃ユ湡
- **THEN** 搂3 SHALL 鏄剧ず椋庨櫓鎸囨爣锛氬鏅瘮鐜囥€佸崱灏旈┈姣旂巼

### Requirement: 鎶ュ憡鍖呭惈浜ゆ槗鍒嗘瀽绔犺妭
鎶ュ憡 搂4 浜ゆ槗鍒嗘瀽 SHALL 鍖呭惈浜ゆ槗缁熻鍜屽钩浠撳師鍥犲垎甯冦€?

#### Scenario: 浜ゆ槗缁熻
- **WHEN** 鎶ュ憡鐢熸垚涓斾氦鏄撴暟鎹彲鐢?
- **THEN** 搂4 SHALL 鏄剧ず锛氭€讳氦鏄撴鏁般€佷拱鍏ユ鏁般€佸崠鍑烘鏁?
- **THEN** 搂4 SHALL 鏄剧ず骞充粨鍘熷洜鍒嗗竷琛紙reason_code 鍙婂搴旀鏁帮紝涓枃缈昏瘧锛?

#### Scenario: 淇″彿婕忔枟
- **WHEN** 鎶ュ憡鐢熸垚涓旀紡鏂楁暟鎹彲鐢?
- **THEN** 搂4 SHALL 鏄剧ず淇″彿婕忔枟锛氬師濮嬩俊鍙?鈫?琚嫤鎴?鈫?涓嬪崟 鈫?璺宠繃 鈫?宸插钩浠?

### Requirement: 鎶ュ憡鍖呭惈鎸佷粨鍒嗘瀽绔犺妭
鎶ュ憡 搂5 鎸佷粨鍒嗘瀽 SHALL 鍖呭惈鎸佷粨鍒╃敤鐜囧拰绾︽潫瑙﹀彂缁熻銆傛湭瀹炵幇鐨勭害鏉?SHALL 鏍囨敞"鏈疄鐜?鑰岄潪鏄剧ず 0銆?

#### Scenario: 鎸佷粨缁熻
- **WHEN** 鎶ュ憡鐢熸垚涓?counters 鏁版嵁鍙敤
- **THEN** 搂5 SHALL 鏄剧ず锛氬钩鍧囨寔浠撴暟銆佹渶澶ф寔浠撴暟銆佺┖浣欎粨浣嶃€佷粨浣嶅埄鐢ㄧ巼锛?锛?

#### Scenario: 鏈疄鐜扮殑绾︽潫缁熻
- **WHEN** 鎶ュ憡鐢熸垚
- **THEN** 涓偂涓婇檺瑙﹀彂琛?SHALL 鏄剧ず `鏈疄鐜癭 鑰岄潪鏁板€?0
- **THEN** 琛屼笟涓婇檺瑙﹀彂琛?SHALL 鏄剧ず `鏈疄鐜癭 鑰岄潪鏁板€?0
- **THEN** 璧勯噾涓嶈冻璺宠繃鍜屾渶灏忔墜鏁拌烦杩?SHALL 姝ｅ父鏄剧ず璁℃暟鍊硷紙杩欎簺宸插疄鐜帮級

### Requirement: 杈呭姪鍑芥暟 鈥?閾惧紡璇诲彇 workbench_config / base_config
`buildConfigSummary()` MUST 瀹氫箟杈呭姪鍑芥暟 `wcVal(path, fallback)` 瀹炵幇涓ゅ眰閾惧紡璇诲彇锛氬厛浠?`overrides.workbench_config` 鎸?path 鍙栧€硷紝鍙栦笉鍒版椂 fallback 鍒?`base_config` 瀵瑰簲瀛楁锛屼粛鍙栦笉鍒版椂杩斿洖 `"-"`銆?

#### Scenario: workbench_config 瀛樺湪鏃朵紭鍏堣鍙?
- **WHEN** config.json 鍖呭惈 `overrides.workbench_config.signal_generation.sma.fast_ma = 5`
- **THEN** 鎶ュ憡淇″彿绛栫暐琛ㄧ殑銆屽揩绾垮懆鏈熴€嶆樉绀?`5`

#### Scenario: workbench_config 缂哄け鏃?fallback 鍒?base_config
- **WHEN** config.json 涓嶅寘鍚?`overrides.workbench_config`锛圓PI 鐩存帴璋冪敤鍦烘櫙锛?
- **THEN** 鎶ュ憡淇″彿绛栫暐琛ㄧ殑銆屽揩绾垮懆鏈熴€嶄粠 `base_config.strategy.fast` 璇诲彇骞舵樉绀?

#### Scenario: 涓ゅ眰鍧囨棤鏁版嵁鏃舵樉绀哄崰浣嶇
- **WHEN** `workbench_config` 鍜?`base_config` 鍧囨棤瀵瑰簲瀛楁
- **THEN** 璇ュ崟鍏冩牸鏄剧ず `"-"`

### Requirement: 瀛愯〃 1 鈥?淇″彿绛栫暐
鎶ュ憡 搂6 MUST 鍖呭惈銆屼俊鍙风瓥鐣ャ€嶅瓙琛紝浠?`<h3>` + `<table>` 娓叉煋锛屽睍绀轰互涓嬪瓧娈碉細
- 绛栫暐鍚嶇О锛坵c.signal_generation.strategy / bc.strategy.name锛?
- 蹇嚎鍛ㄦ湡锛坵c.signal_generation.sma.fast_ma / bc.strategy.fast锛?
- 鎱㈢嚎鍛ㄦ湡锛坵c.signal_generation.sma.slow_ma / bc.strategy.slow锛?
- 鍏ュ満缂撳啿锛坵c.signal_generation.sma.entry_buffer_pct锛夆€?鐧惧垎姣旀樉绀?
- 瓒嬪娍杩囨护 MA锛坆c.strategy.params.trend_ma锛?

ATR 绐楀彛鍜?ATR 鍊嶆暟 SHALL NOT 鍑虹幇鍦ㄤ俊鍙风瓥鐣ュ瓙琛ㄤ腑锛堣繖浜涙槸閫€鍑哄弬鏁帮紝宸插湪閫€鍑鸿鍒欏瓙琛ㄤ腑灞曠ず锛夈€?

#### Scenario: SMA_CROSS 绛栫暐鍙傛暟瀹屾暣
- **WHEN** config.json 涓?wc.signal_generation.strategy = "SMA_CROSS"锛宻ma.fast_ma = 5锛宻ma.slow_ma = 20
- **THEN** 淇″彿绛栫暐琛ㄦ樉绀虹瓥鐣ュ悕銆孲MA_CROSS銆嶃€佸揩绾裤€?銆嶃€佹參绾裤€?0銆?
- **THEN** 淇″彿绛栫暐琛?SHALL NOT 鍖呭惈 ATR 绐楀彛鎴?ATR 鍊嶆暟琛?

#### Scenario: params 瀛楁涓嶅瓨鍦?
- **WHEN** base_config.strategy 涓嶅惈 params 瀛楁
- **THEN** 瓒嬪娍杩囨护 MA 鏄剧ず "-"

### Requirement: 瀛愯〃 2 鈥?閫€鍑鸿鍒?
鎶ュ憡 搂6 MUST 鍖呭惈銆岄€€鍑鸿鍒欍€嶅瓙琛紝灞曠ず浠ヤ笅瀛楁锛?
- 鍙嶈浆閫€鍑猴紙wc.exit_rules.signal_reverse锛夆€?鍚敤/绂佺敤
- ATR 姝㈡崯锛坵c.exit_rules.atr_stop.enabled + k锛?
- 杩借釜姝㈡崯锛坵c.exit_rules.trailing.enabled + k锛?
- 鏃堕棿閫€鍑猴紙wc.exit_rules.time_exit.enabled + n_days锛?
- 閫€鍑轰紭鍏堢骇锛坵c.exit_priority锛夆€?閫楀彿鍒嗛殧鍒楄〃

#### Scenario: ATR 姝㈡崯鍚敤
- **WHEN** wc.exit_rules.atr_stop.enabled = true, k = 0.8
- **THEN** ATR 姝㈡崯琛屾樉绀恒€屽惎鐢?(k=0.8)銆?

#### Scenario: 杩借釜姝㈡崯绂佺敤
- **WHEN** wc.exit_rules.trailing.enabled = false
- **THEN** 杩借釜姝㈡崯琛屾樉绀恒€岀鐢ㄣ€?

#### Scenario: 閫€鍑轰紭鍏堢骇鍒楄〃
- **WHEN** wc.exit_priority = ["stop_loss", "reversal", "time", "trail"]
- **THEN** 閫€鍑轰紭鍏堢骇琛屾樉绀恒€宻top_loss 鈫?reversal 鈫?time 鈫?trail銆?

#### Scenario: 鏃?workbench_config 鏃堕€€鍑鸿鍒欏叏鏄剧ず鍗犱綅绗?
- **WHEN** config.json 涓嶅惈 workbench_config
- **THEN** 閫€鍑鸿鍒欏瓙琛ㄦ墍鏈夊瓧娈垫樉绀?"-"

### Requirement: 瀛愯〃 3 鈥?浠撲綅涓庨鎺?
鎶ュ憡 搂6 MUST 鍖呭惈銆屼粨浣嶄笌椋庢帶銆嶅瓙琛紝灞曠ず浠ヤ笅瀛楁锛?
- 鏈€澶ф寔浠撴暟锛坵c.position_risk.max_positions锛?
- 鍗曠エ浠撲綅涓婇檺锛坵c.position_risk.single_stock_cap锛夆€?灏忔暟鈫掔櫨鍒嗘瘮
- 琛屼笟浠撲綅涓婇檺锛坵c.position_risk.industry_cap锛夆€?灏忔暟鈫掔櫨鍒嗘瘮
- 鎵嬫暟锛坵c.position_risk.lot / bc.execution.lot_size锛?
- 鐜伴噾涓嶈冻绛栫暐锛坵c.position_risk.cash_shortage_policy锛?
- 椋庨櫓闂紙wc.risk_gate.enabled + drawdown_threshold + action + cooldown_days锛?

#### Scenario: 浠撲綅涓婇檺鐧惧垎姣旇浆鎹?
- **WHEN** wc.position_risk.single_stock_cap = 0.1, industry_cap = 0.3
- **THEN** 鍗曠エ浠撲綅涓婇檺鏄剧ず銆?0%銆嶏紝琛屼笟浠撲綅涓婇檺鏄剧ず銆?0%銆?

#### Scenario: 椋庨櫓闂ㄥ惎鐢?
- **WHEN** wc.risk_gate.enabled = true, drawdown_threshold = -0.1, action = "reduce", cooldown_days = 5
- **THEN** 椋庨櫓闂ㄨ鏄剧ず銆屽惎鐢?鈥?鍥炴挙闃堝€?10%, 鍔ㄤ綔 reduce, 鍐峰嵈 5 澶┿€?

#### Scenario: 椋庨櫓闂ㄧ鐢?
- **WHEN** wc.risk_gate.enabled = false
- **THEN** 椋庨櫓闂ㄨ鏄剧ず銆岀鐢ㄣ€?

### Requirement: 瀛愯〃 4 鈥?閫夎偂鑼冨洿
鎶ュ憡 搂6 MUST 鍖呭惈銆岄€夎偂鑼冨洿銆嶅瓙琛紝灞曠ず浠ヤ笅瀛楁锛?
- 閫夎偂妯″紡锛坵c.universe_mode 鎴?overrides.universe_mode锛?
- 鏍囩殑鏁伴噺锛坵c.universe.symbols.length 鎴?bc.universe.symbols.length锛?
- 鎺掗櫎 ST锛坵c.universe.filters.exclude_st锛?
- 鎺掗櫎鍋滅墝锛坵c.universe.filters.exclude_suspended锛?
- 鏈€灏忎笂甯傚ぉ鏁帮紙wc.universe.filters.min_list_days锛?
- 鏃ュ潎鎴愪氦棰濅笅闄愶紙wc.universe.filters.min_avg_turnover_20d锛夆€?鏍煎紡鍖栦负涓囧厓
- 浠锋牸鍖洪棿锛坵c.universe.filters.price_min ~ price_max锛?
- ATR 娉㈠姩鍖洪棿锛坵c.universe.filters.atr_pct_range锛?
- 娑ㄨ穼鍋滆鍒欙紙wc.universe.filters.limit_rule锛?
- 浠锋牸鍙ｅ緞锛坵c.universe.price_adj / overrides.price_adj锛?

#### Scenario: 瀹屾暣杩囨护鏉′欢灞曠ず
- **WHEN** wc.universe.filters 鍖呭惈 exclude_st=true, min_list_days=180, min_avg_turnover_20d=100000000
- **THEN** 鎺掗櫎 ST 鏄剧ず銆屾槸銆嶏紝鏈€灏忎笂甯傚ぉ鏁版樉绀恒€?80銆嶏紝鏃ュ潎鎴愪氦棰濅笅闄愭樉绀恒€?0,000 涓囥€?

#### Scenario: 浠锋牸鍙ｅ緞璇诲彇
- **WHEN** wc.universe.price_adj = "hfq"
- **THEN** 浠锋牸鍙ｅ緞琛屾樉绀恒€屽悗澶嶆潈 (hfq)銆?

#### Scenario: 閫夎偂妯″紡 CUSTOM
- **WHEN** wc.universe_mode 涓嶅瓨鍦ㄤ笖 bc.universe.symbols 鏈?3 鍙爣鐨?
- **THEN** 閫夎偂妯″紡鏄剧ず "-"锛屾爣鐨勬暟閲忔樉绀恒€?銆?

### Requirement: 瀛愯〃 5 鈥?鎵ц鍋囪
鎶ュ憡 搂6 MUST 鍖呭惈銆屾墽琛屽亣璁俱€嶅瓙琛紝灞曠ず浠ヤ笅瀛楁锛?
- 浣ｉ噾鐜囷紙bc.costs.commission_rate锛夆€?涓囧垎姣旀樉绀猴紙濡?3鈥憋級
- 鏈€浣庝剑閲戯紙bc.costs.commission_min锛?
- 鍗拌姳绋庣巼锛坆c.costs.stamp_tax_rate锛夆€?鍗冨垎姣旀樉绀猴紙濡?1鈥帮級
- 婊戠偣锛坆c.costs.slippage_bps锛夆€?鍗曚綅 bps
- 鎵嬫暟锛坆c.execution.lot_size锛?
- T+1锛坆c.execution.t_plus_one锛夆€?鏄?鍚?
- 鍒濆璧勯噾锛坆c.initial_capital锛夆€?璐у竵鏍煎紡

#### Scenario: 榛樿鎴愭湰鍙傛暟
- **WHEN** bc.costs = {commission_rate: 0.0003, commission_min: 5, stamp_tax_rate: 0.001, slippage_bps: 2}
- **THEN** 浣ｉ噾鐜囨樉绀恒€?鈥便€嶏紝鏈€浣庝剑閲戞樉绀恒€?.00銆嶏紝鍗拌姳绋庣巼鏄剧ず銆?鈥般€嶏紝婊戠偣鏄剧ず銆? bps銆?

#### Scenario: T+1 鎵ц瑙勫垯
- **WHEN** bc.execution.t_plus_one = true, lot_size = 100
- **THEN** T+1 鏄剧ず銆屾槸銆嶏紝鎵嬫暟鏄剧ず銆?00銆?

### Requirement: 澶嶅悎淇″彿瀛愯〃 鈥?鏉′欢娓叉煋
褰?`wc.signal_composition.enabled === true` 涓?`wc.signal_composition.modules.length > 0` 鏃讹紝椤婚澶栨覆鏌撲竴涓€屽鍚堜俊鍙枫€嶅瓙琛ㄣ€傝瀛愯〃 SHALL 鏍囨敞"鏈疄鐜?琛ㄦ槑鍚庣灏氭棤澶嶅悎淇″彿閫昏緫銆?

#### Scenario: 澶嶅悎淇″彿鍚敤涓旀湁妯″潡
- **WHEN** wc.signal_composition.enabled = true, modules 闈炵┖
- **THEN** 娓叉煋澶嶅悎淇″彿瀛愯〃锛屾爣棰樺悗 SHALL 杩藉姞 `(鏈疄鐜?` 鏍囨敞

#### Scenario: 澶嶅悎淇″彿绂佺敤鎴栨ā鍧椾负绌?
- **WHEN** wc.signal_composition.enabled = false 鎴?modules 涓虹┖
- **THEN** 涓嶆覆鏌撳鍚堜俊鍙峰瓙琛?

### Requirement: 鎶ュ憡鍖呭惈浜ゆ槗鏄庣粏闄勫綍
鎶ュ憡 搂7 闄勫綍 SHALL 鍖呭惈鍏ㄩ儴浜ゆ槗璁板綍鏄庣粏琛ㄣ€?

#### Scenario: 浜ゆ槗鏄庣粏琛?
- **WHEN** 鎶ュ憡鐢熸垚涓斾氦鏄撴暟鎹彲鐢?
- **THEN** 搂7 SHALL 鍖呭惈鍏ㄩ儴浜ゆ槗璁板綍琛ㄦ牸锛屽垪涓猴細鏃ユ湡銆佹爣鐨勩€佹柟鍚戙€佷环鏍笺€佹暟閲忋€侀噾棰濄€佸師鍥?
- **THEN** 鏂瑰悜鍒?SHALL 鏄剧ず涓枃锛堜拱鍏?鍗栧嚭锛?
- **THEN** 閲戦鍒?SHALL 鏄剧ず鍗冨垎浣嶆牸寮?

### Requirement: 鏁版嵁鏍煎紡涓撲笟鍖栨樉绀?
宸ヤ綔鍙版墍鏈夋暟鍊?SHALL 鎸夎涔夌被鍨嬩娇鐢ㄥ搴旀牸寮忓嚱鏁版樉绀恒€?

#### Scenario: KPI 鍗＄墖鏍煎紡鍖?
- **WHEN** KPI 闈㈡澘娓叉煋
- **THEN** 骞村寲鏀剁泭銆佹渶澶у洖鎾ゃ€佹崲鎵嬬巼銆乀op10闆嗕腑搴?SHALL 鏄剧ず涓虹櫨鍒嗘瘮锛堝 -2.18%锛?
- **THEN** 澶忔櫘姣旂巼銆佸崱灏旈┈姣旂巼 SHALL 鏄剧ず 2 浣嶅皬鏁帮紙濡?-0.05锛?
- **THEN** 浜ゆ槗娆℃暟 SHALL 鏄剧ず鍗冨垎浣嶆暣鏁帮紙濡?2,166锛?

#### Scenario: 浜ゆ槗鏄庣粏琛ㄦ牸寮忓寲
- **WHEN** 浜ゆ槗鏄庣粏琛ㄦ覆鏌?
- **THEN** 浠锋牸 SHALL 鏄剧ず 3 浣嶅皬鏁?
- **THEN** 鏁伴噺 SHALL 鏄剧ず鍗冨垎浣嶆暣鏁?
- **THEN** 閲戦 SHALL 鏄剧ず鍗冨垎浣?+ 2 浣嶅皬鏁?

#### Scenario: Explain 闈㈡澘璁℃暟鍣ㄦ牸寮忓寲
- **WHEN** Explain 闈㈡澘瑙﹀彂缁熻娓叉煋
- **THEN** 璁℃暟绫绘寚鏍囷紙exit count銆乥lock count锛塖HALL 鏄剧ず涓烘暣鏁?
- **THEN** 姣旂巼绫绘寚鏍囷紙applied_rate銆乷n_rate锛塖HALL 鏄剧ず涓虹櫨鍒嗘瘮

### Requirement: 鐣岄潰涓枃鍖?
宸ヤ綔鍙?SHALL 灏嗘墍鏈夎嫳鏂囨爣绛剧炕璇戜负涓枃锛堜繚鐣欐妧鏈缉鍐欏 ATR銆丼MA锛夈€?

#### Scenario: KPI 鏍囩涓枃鍖?
- **WHEN** KPI 闈㈡澘娓叉煋
- **THEN** 鏍囩 SHALL 涓猴細骞村寲鏀剁泭銆佹渶澶у洖鎾ゃ€佸鏅瘮鐜囥€佸崱灏旈┈姣旂巼銆佷氦鏄撴鏁般€佹崲鎵嬬巼銆乀op10闆嗕腑搴︺€佽瘎绾?

#### Scenario: 鍥捐〃鍥句緥涓枃鍖?
- **WHEN** 鍥炴挙鍥炬覆鏌?
- **THEN** 鍥句緥 SHALL 鏄剧ず"绛栫暐鍥炴挙"鍜?鍩哄噯鍥炴挙"

#### Scenario: Explain 闈㈡澘涓枃鍖?
- **WHEN** 瑙﹀彂缁熻琛ㄦ覆鏌?
- **THEN** 琛ㄥご SHALL 涓?璁℃暟鍣?鍜?鍊?
- **THEN** 璁℃暟鍣ㄥ悕绉?SHALL 缈昏瘧涓轰腑鏂囷紙濡?atr_stop_exit_count 鈫?ATR姝㈡崯骞充粨锛?

#### Scenario: Execution 闈㈡澘涓枃鍖?
- **WHEN** Execution 闈㈡澘娓叉煋
- **THEN** "Candidates TopN" SHALL 鏄剧ず涓?鍊欓€夋爣鐨?TopN"
- **THEN** "Target positions" SHALL 鏄剧ず涓?鐩爣鎸佷粨"

#### Scenario: 浜ゆ槗鍘熷洜鐮佷腑鏂囧寲
- **WHEN** 浜ゆ槗鏄庣粏鎴栨姤鍛婁腑鏄剧ず reason_code
- **THEN** 宸茬煡 reason_code SHALL 缈昏瘧涓轰腑鏂囷紙SMA_CROSS_UP 鈫?鍧囩嚎閲戝弶锛?
- **THEN** 鏈煡 reason_code SHALL 鏄剧ず鍘熷鍊间綔涓?fallback

### Requirement: 浜ゆ槗鏄庣粏琛ㄧ編鍖?
浜ゆ槗鏄庣粏琛?SHALL 鍏峰涓撲笟閲戣瀺杞欢鐨勮瑙夊搧璐ㄣ€?

#### Scenario: 鏂瑰悜鍒楁牱寮?
- **WHEN** 浜ゆ槗鏄庣粏琛ㄦ覆鏌?
- **THEN** 涔板叆 SHALL 鏄剧ず涓虹豢鑹?badge 鏍囩
- **THEN** 鍗栧嚭 SHALL 鏄剧ず涓虹孩鑹?badge 鏍囩

#### Scenario: 鏁板瓧鍒楀榻?
- **WHEN** 浜ゆ槗鏄庣粏琛ㄦ覆鏌?
- **THEN** 浠锋牸銆佹暟閲忋€侀噾棰濆垪 SHALL 鍙冲榻愬苟浣跨敤绛夊瀛椾綋

### Requirement: perf.json 鍖呭惈瀹屾暣 KPI 瀛楁
perf.json SHALL 鍖呭惈 calmar銆乼op10_profit_concentration銆乼ier 涓変釜瀛楁銆?

#### Scenario: Calmar 姣旂巼璁＄畻
- **WHEN** 鍥炴祴瀹屾垚涓?max_drawdown 鈮?0
- **THEN** perf.json 鐨?`calmar` SHALL 绛変簬 `cagr / |max_drawdown|`

#### Scenario: Calmar 姣旂巼杈圭晫鍊?
- **WHEN** max_drawdown = 0锛堟棤鍥炴挙锛?
- **THEN** `calmar` SHALL 涓?0.0

#### Scenario: Top10 鍒╂鼎闆嗕腑搴?
- **WHEN** 鍥炴祴瀹屾垚涓斿瓨鍦ㄧ泩鍒╀氦鏄?
- **THEN** `top10_profit_concentration` SHALL 绛変簬鍒╂鼎鏈€楂樼殑 10 鍙偂绁ㄥ埄娑︿箣鍜?/ 鍏ㄩ儴姝ｅ埄娑︿箣鍜?
- **THEN** 鍊煎煙 SHALL 涓?[0, 1]

#### Scenario: Top10 鏃犵泩鍒?
- **WHEN** 鍥炴祴瀹屾垚浣嗘棤姝ｅ埄娑?
- **THEN** `top10_profit_concentration` SHALL 涓?0.0

#### Scenario: 绛栫暐璇勭骇
- **WHEN** 鍥炴祴瀹屾垚
- **THEN** `tier` SHALL 鍩轰簬 sharpe銆乵ax_drawdown銆乧almar 鍒嗙骇锛?
  - T1: sharpe >= 1.0 涓?max_drawdown > -0.20 涓?calmar >= 1.0
  - T2: sharpe >= 0.5 涓?max_drawdown > -0.30
  - T3: sharpe >= 0.0
  - T4: 鍏朵粬

### Requirement: 鍓嶇 KPI 闈㈡澘鏄剧ず瀹屾暣
KPI 闈㈡澘 SHALL 姝ｇ‘鏄剧ず鎵€鏈?8 涓?KPI 瀛楁鐨勮绠楀€笺€?

#### Scenario: KPI 闈炵┖鏄剧ず
- **WHEN** 鍥炴祴瀹屾垚涓?perf.json 鍖呭惈瀛楁鍊?
- **THEN** 鍗″皵椹瘮鐜?SHALL 鏄剧ず鏁板€硷紙闈?0.00 闄ら潪瀹為檯涓?0锛?
- **THEN** Top10闆嗕腑搴?SHALL 鏄剧ず鐧惧垎姣旓紙闈?鈥旓級
- **THEN** 璇勭骇 SHALL 鏄剧ず T1/T2/T3/T4锛堥潪 鈥旓級

### Requirement: 鎶ュ憡瀵煎嚭蹇呴』浣跨敤 Markdown
宸ヤ綔鍙?SHALL 鎻愪緵 Markdown 鎶ュ憡瀵煎嚭锛屼笉鍐嶆墦寮€鎴栧鍑哄悗绔?`report.html`銆?

#### Scenario: 瀵煎嚭宸叉湁瀹為獙鎶ュ憡
- **WHEN** 鐢ㄦ埛鐐瑰嚮瀵煎嚭鎶ュ憡
- **THEN** 绯荤粺 SHALL 瀵煎嚭褰撳墠瀹為獙鐨?Markdown 鎶ュ憡
- **THEN** 绯荤粺 SHALL NOT 鎵撳紑 `report.html`

#### Scenario: 鏃犲疄楠岀粨鏋滄椂瀵煎嚭
- **WHEN** 鐢ㄦ埛鐐瑰嚮瀵煎嚭鎶ュ憡浣嗗綋鍓嶆病鏈夊彲鐢ㄥ疄楠岀粨鏋?
- **THEN** 绯荤粺 SHALL 鎻愮ず鐢ㄦ埛鍏堣繍琛屾垨鍔犺浇瀹為獙

