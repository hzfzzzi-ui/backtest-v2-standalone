# accounting-integrity-audit Specification

## Purpose

Define the formal capability boundary for `accounting-integrity-audit` in the current mainline.
## Requirements
### Requirement: 涓荤嚎浼氳瀹¤蹇呴』鍩轰簬姝ｅ紡璁拌处蹇収
绯荤粺 MUST 浠庡綋鍓嶆寮忔墽琛岄摼鐨?canonical accounting snapshot 鎴栫瓑浠锋寮忓揩鐓х敓鎴愪細璁″璁¤瘉鎹紝SHALL NOT 閫氳繃浜嬪悗閲嶆斁 `portfolio_trades.csv` 鎴栧鐢ㄥ巻鍙叉梺璺鏌ュ櫒浣滀负鍞竴鐪熺浉銆?

绯荤粺 MUST 浠庡綋鍓嶆寮忔墽琛岄摼鐨?canonical accounting snapshot 鎴栫瓑浠锋寮忓揩鐓х敓鎴愪細璁″璁¤瘉鎹紝SHALL NOT 閫氳繃浜嬪悗閲嶆斁 `portfolio_trades.csv` 鎴栧鐢ㄥ巻鍙叉梺璺鏌ュ櫒浣滀负鍞竴鐪熺浉銆?

#### Scenario: stage pipeline 璺緞鎻愪緵姝ｅ紡蹇収
- **WHEN** 褰撳墠姝ｅ紡 stage pipeline 瀹屾垚鏌愪釜浜ゆ槗鏃ョ殑 fill accounting 鍜?daily accounting
- **THEN** 浼氳瀹¤ SHALL 浣跨敤璇ヤ氦鏄撴棩鐨勬寮忚璐﹀揩鐓т綔涓虹幇閲戙€佹寔浠撳拰 NAV 鏍￠獙杈撳叆
- **THEN** 鍚屼竴浜ゆ槗鏃ョ殑浼氳瀹¤缁撴灉 SHALL 鍙鍚庣画 `audit.json` 涓?`research_audit` 澶嶇敤### Requirement: 浼氳瀹¤蹇呴』鏍￠獙鐜伴噾瀹堟亽涓庢寔浠撳畧鎭?
绯荤粺 MUST 瀵规瘡涓氦鏄撴棩鏍￠獙 `cash_before + sell_net - buy_net = cash_after`锛屽苟鏍￠獙姣忎釜鏍囩殑涓庣粍鍚堝眰鐨勬寔浠撴暟閲忓畧鎭掑叧绯汇€?

#### Scenario: 鐜伴噾涓庢寔浠撳畧鎭掗€氳繃
- **WHEN** 鏌愪氦鏄撴棩鐨勪拱鍗栨垚浜ゃ€佺幇閲戝彉鍔ㄥ拰鏀剁洏鍚庢寔浠撴暟閲忓叏閮ㄤ笌姝ｅ紡璁拌处蹇収涓€鑷?
- **THEN** 璇ヤ氦鏄撴棩 SHALL 琚爣璁颁负鐜伴噾瀹堟亽閫氳繃涓旀寔浠撳畧鎭掗€氳繃
- **THEN** 浼氳瀹¤鎽樿 SHALL 绱姞鐩稿簲閫氳繃璁℃暟

#### Scenario: 鐜伴噾鎴栨寔浠撳畧鎭掑け璐?
- **WHEN** 鏌愪氦鏄撴棩鐨?`cash_after` 涓庢湡鏈涚幇閲戜笉涓€鑷达紝鎴栦换涓€鏍囩殑 `position_after != position_before + qty_buy - qty_sell`
- **THEN** 璇ヤ氦鏄撴棩 SHALL 琚爣璁颁负浼氳寮傚父
- **THEN** 浼氳瀹¤ SHALL 璁板綍澶辫触绫诲瀷銆佹棩鏈熷拰鍙楁帶鏍锋湰

### Requirement: 浼氳瀹¤蹇呴』鏍￠獙 NAV 涓€鑷存€т笌纭竟鐣?
绯荤粺 MUST 鏍￠獙 `nav = cash + market_value`锛屽苟鎶婅礋鐜伴噾銆佽秴鍑?`max_positions` 涓婇檺鍜岄潪娉?NAV 瑙嗕负纭€у紓甯搞€?

绯荤粺 MUST 鏍￠獙 `nav = cash + market_value`锛屽苟鎶婅礋鐜伴噾銆佽秴鍑?`max_positions` 涓婇檺鍜岄潪娉?NAV 瑙嗕负纭€у紓甯搞€?

#### Scenario: NAV 涓€鑷翠笖纭竟鐣岄€氳繃
- **WHEN** 鏌愪氦鏄撴棩鐨?`nav` 涓?`cash + market_value` 鍦ㄧ害瀹氬宸唴涓€鑷达紝涓?`cash >= 0`銆佹寔浠撴暟鏈秴杩囦笂闄?
- **THEN** 璇ヤ氦鏄撴棩 SHALL 琚爣璁颁负 NAV 鏍￠獙閫氳繃

#### Scenario: 鍑虹幇纭€у紓甯?
- **WHEN** 鏌愪氦鏄撴棩鍑虹幇璐熺幇閲戙€佽秴浠撲笂闄愩€佽礋 NAV銆丯aN NAV 鎴?NAV 鎭掔瓑寮忎笉鎴愮珛
- **THEN** 浼氳瀹¤ SHALL 灏嗚浜ゆ槗鏃ユ爣璁颁负纭€уけ璐?
- **THEN** 浼氳瀹¤鎽樿 SHALL 璁板綍瀵瑰簲寮傚父璁℃暟### Requirement: 浼氳瀹¤蹇呴』杈撳嚭鍙楁帶鎽樿涓庡け璐ユ牱鏈?
绯荤粺 MUST 杈撳嚭鍙緵姝ｅ紡瀹¤娑堣垂鐨勪細璁℃憳瑕侊紝鍖呮嫭閫氳繃/澶辫触璁℃暟銆佸紓甯哥被鍒鏁板拰鍙楁帶澶辫触鏍锋湰锛涚郴缁?SHALL NOT 灏嗗叏閲忔棩绾у揩鐓х洿鎺ュ唴鑱斿埌涓诲璁℃枃浠朵腑銆?

#### Scenario: 鍐欏叆鍙楁帶鎽樿
- **WHEN** 涓€娆″疄楠屽畬鎴愬苟鐢熸垚姝ｅ紡 execution audit
- **THEN** 浼氳瀹¤杈撳嚭 SHALL 鍖呭惈鐜伴噾瀹堟亽銆佹寔浠撳畧鎭掋€丯AV 鏍￠獙銆佽礋鐜伴噾鍜岃秴浠撳紓甯哥殑鎽樿璁℃暟
- **THEN** 姣忕被澶辫触 SHALL 鑷冲皯淇濈暀鏈夐檺鏁伴噺鐨勬牱鏈褰曚緵浜哄伐澶嶆牳

### Requirement: 浼氳瀹¤蹇呴』鏍￠獙鐜伴噾瀹堟亽涓庢寔浠撳畧鎭?
绯荤粺 MUST 瀵规瘡涓氦鏄撴棩鏍￠獙 `cash_before + sell_net - buy_net = cash_after`锛屽苟鏍￠獙姣忎釜鏍囩殑涓庣粍鍚堝眰鐨勬寔浠撴暟閲忓畧鎭掑叧绯汇€?

#### Scenario: 鐜伴噾涓庢寔浠撳畧鎭掗€氳繃
- **WHEN** 鏌愪氦鏄撴棩鐨勪拱鍗栨垚浜ゃ€佺幇閲戝彉鍔ㄥ拰鏀剁洏鍚庢寔浠撴暟閲忓叏閮ㄤ笌姝ｅ紡璁拌处蹇収涓€鑷?
- **THEN** 璇ヤ氦鏄撴棩 SHALL 琚爣璁颁负鐜伴噾瀹堟亽閫氳繃涓旀寔浠撳畧鎭掗€氳繃
- **THEN** 浼氳瀹¤鎽樿 SHALL 绱姞鐩稿簲閫氳繃璁℃暟

#### Scenario: 鐜伴噾鎴栨寔浠撳畧鎭掑け璐?
- **WHEN** 鏌愪氦鏄撴棩鐨?`cash_after` 涓庢湡鏈涚幇閲戜笉涓€鑷达紝鎴栦换涓€鏍囩殑 `position_after != position_before + qty_buy - qty_sell`
- **THEN** 璇ヤ氦鏄撴棩 SHALL 琚爣璁颁负浼氳寮傚父
- **THEN** 浼氳瀹¤ SHALL 璁板綍澶辫触绫诲瀷銆佹棩鏈熷拰鍙楁帶鏍锋湰

### Requirement: 浼氳瀹¤蹇呴』杈撳嚭鍙楁帶鎽樿涓庡け璐ユ牱鏈?
绯荤粺 MUST 杈撳嚭鍙緵姝ｅ紡瀹¤娑堣垂鐨勪細璁℃憳瑕侊紝鍖呮嫭閫氳繃/澶辫触璁℃暟銆佸紓甯哥被鍒鏁板拰鍙楁帶澶辫触鏍锋湰锛涚郴缁?SHALL NOT 灏嗗叏閲忔棩绾у揩鐓х洿鎺ュ唴鑱斿埌涓诲璁℃枃浠朵腑銆?

#### Scenario: 鍐欏叆鍙楁帶鎽樿
- **WHEN** 涓€娆″疄楠屽畬鎴愬苟鐢熸垚姝ｅ紡 execution audit
- **THEN** 浼氳瀹¤杈撳嚭 SHALL 鍖呭惈鐜伴噾瀹堟亽銆佹寔浠撳畧鎭掋€丯AV 鏍￠獙銆佽礋鐜伴噾鍜岃秴浠撳紓甯哥殑鎽樿璁℃暟
- **THEN** 姣忕被澶辫触 SHALL 鑷冲皯淇濈暀鏈夐檺鏁伴噺鐨勬牱鏈褰曚緵浜哄伐澶嶆牳

### Requirement: 主线会计审计必须校验显式分红应收与到账闭环
主线会计审计 MUST 在 canonical accounting snapshot 中同时验证 ETF 分红应收创建、到账结转与现金/NAV 闭环。

#### Scenario: pay-date 口径下应收与到账闭环通过
- **WHEN** 某 ETF 分红在除息日创建 `dividend_receivable`，并在到账日转入 `cash`
- **THEN** 会计审计同时通过 receivable 守恒、cash 守恒与 NAV 一致性检查

#### Scenario: 分红到账缺失会被审计标记
- **WHEN** 某 ETF 分红已在除息日创建 receivable，但到账日未完成结转或重复结转
- **THEN** 会计审计 SHALL 记录对应失败样本与失败类型

