# artifact-protocol-convergence Specification

## Purpose

Define the formal capability boundary for `artifact-protocol-convergence` in the current mainline.
## Requirements
### Requirement: 鍗忚鏍囧噯鍛藉悕蹇呴』鍞竴
绯荤粺 MUST 閲囩敤鍞竴 canonical 浜х墿鍛藉悕涓庡瓧娈靛懡鍚嶏紝绂佹鍚屼竴璇箟鍑虹幇澶氫釜鏍囧噯鍚嶃€?

#### Scenario: 浜х墿鍛藉悕鏍囧噯鍖?
- **WHEN** 绯荤粺鍐欏嚭瀹為獙浜х墿
- **THEN** 鍘熷洜鐮佽仛鍚堟枃浠?SHALL 浣跨敤 `reason_codes.csv` 浣滀负鏍囧噯鏂囦欢鍚?
- **THEN** `group_files.reason_codes` SHALL 鎸囧悜 `reason_codes.csv`

#### Scenario: run_meta counters 瀛楁鏍囧噯鍖?
- **WHEN** 绯荤粺鍐欏嚭 `run_meta.json`
- **THEN** `counters` SHALL 浣跨敤鐭悕瀛楁锛歚raw_signal`, `blocked`, `orders`, `skipped`, `closed_trades`
- **THEN** 鏂板啓鍑烘暟鎹?SHALL NOT 浣跨敤 `_count` 浣滀负鏍囧噯瀛楁鍚?

### Requirement: 璇诲彇渚у繀椤绘彁渚涗袱鐗堟湰鍏煎绐楀彛
绯荤粺 MUST 鍦ㄤ袱涓増鏈獥鍙ｅ唴鍏煎璇诲彇 legacy 鏂囦欢鍚嶄笌 legacy counters 瀛楁鍚嶃€?

#### Scenario: 鍏煎 legacy 鍘熷洜鐮佹枃浠跺悕
- **WHEN** 鏍囧噯鏂囦欢 `reason_codes.csv` 涓嶅瓨鍦ㄤ絾 legacy 鏂囦欢 `reason_code_counts.csv` 瀛樺湪
- **THEN** 璇诲彇娴佺▼ SHALL 鍥為€€璇诲彇 `reason_code_counts.csv`
- **THEN** 涓婂眰娑堣垂鏂?SHALL 鑾峰緱涓庢爣鍑嗘枃浠剁瓑浠风殑鏁版嵁缁撴瀯

#### Scenario: 鍏煎 legacy counters 瀛楁
- **WHEN** `run_meta.counters` 涓粎瀛樺湪 `_count` 鍛藉悕瀛楁
- **THEN** 璇诲彇娴佺▼ SHALL 鏄犲皠涓虹煭鍚嶅瓧娈佃繘琛屾秷璐?
- **THEN** 鍓嶇涓?API 杩斿洖 SHALL 缁х画杈撳嚭鐭悕鍙ｅ緞

### Requirement: 缂哄け浜х墿蹇呴』闄嶇骇涓哄彲瑙傛祴绌轰骇鐗?
绯荤粺 MUST 鍦ㄤ骇鐗╃己澶辨椂鐢熸垚绌烘枃浠跺苟璁板綍缂哄け鏉ユ簮锛岄伩鍏嶆祦绋嬩腑鏂笌闈欓粯澶辫触銆?

#### Scenario: 浜х墿婧愮己澶?
- **WHEN** 鏌愭爣鍑嗕骇鐗╂棤娉曚粠杩愯缁撴灉鎺ㄥ
- **THEN** 绯荤粺 SHALL 鍐欏嚭瀵瑰簲绌轰骇鐗╂枃浠讹紙鍚堟硶鏍煎紡锛?
- **THEN** `run_meta.missing_fields` SHALL 璁板綍绋冲畾閿悕鐨勭己澶辨潵婧?

#### Scenario: 涓嬫父娑堣垂绌轰骇鐗?
- **WHEN** 鍓嶇鎴?API 璇诲彇鍒扮┖浜х墿
- **THEN** 绯荤粺 SHALL 杩斿洖绌鸿鎴栭粯璁ょ粨鏋勶紝涓嶆姏鍑哄崗璁敊璇?
- **THEN** 鐘舵€佷腑蹇冩垨璇婃柇淇℃伅 SHALL 鍙缂哄け璇存槑

### Requirement: artifact 绋冲畾鍖?owner 蹇呴』闆嗕腑鍒版牳蹇?service
artifact 鍗忚鐨勭ǔ瀹氬寲鍜屾爣鍑嗕骇鐗╄ˉ榻?MUST 鐢辨牳蹇?artifact service 缁熶竴璐熻矗銆俥ndpoint 灞?MAY 鎻愪緵 HTTP 鍖呰锛屼絾 SHALL NOT 鎴愪负绋冲畾鍖栫殑鍞竴 owner銆?

#### Scenario: manifest 鍐欏叆
- **WHEN** 瀹為獙瀹屾垚骞堕渶瑕佸啓鍏?manifest
- **THEN** manifest SHALL 鐢辨牳蹇?artifact service 鐢熸垚

#### Scenario: 鏍囧噯浜х墿琛ラ綈
- **WHEN** 绯荤粺闇€瑕佽ˉ榻?`perf.json`銆乣nav.csv`銆乣run_meta.json`銆乣audit.json`
- **THEN** 杩欎簺鍔ㄤ綔 SHALL 鐢辨牳蹇?artifact service 璐熻矗

### Requirement: report.html 涓嶅啀灞炰簬褰撳墠 artifact 涓诲绾?
绯荤粺褰撳墠 artifact 涓诲绾?MUST 浠?`manifest.json`銆乣perf.json`銆乣nav.csv`銆乣run_meta.json`銆乣audit.json`銆丮arkdown 鍒嗘瀽鎶ュ憡绛変骇鐗╀负鏍稿績銆俙report.html` 鑻ュ瓨鍦紝浠呭彲瑙嗕负 legacy artifact锛屽綋鍓嶄富濂戠害 SHALL NOT 缁х画渚濊禆瀹冦€?

#### Scenario: 鏂板疄楠岀ǔ瀹氬寲
- **WHEN** 绯荤粺绋冲畾鍖栦竴涓柊瀹為獙鐩綍
- **THEN** manifest SHALL NOT 灏?`report.html` 鏍囪涓哄綋鍓嶆爣鍑嗕骇鐗?

#### Scenario: 鍘嗗彶瀹為獙鐩綍浠嶄繚鐣?report.html
- **WHEN** 鍘嗗彶瀹為獙鐩綍涓粛瀛樺湪 `report.html`
- **THEN** 绯荤粺 MAY 鍏煎淇濈暀鏂囦欢
- **THEN** 褰撳墠鍓嶇涓庨棬绂?SHALL NOT 渚濊禆璇ユ枃浠?

### Requirement: manifests MUST identify execution truth separately from compile snapshots

新实验产物 MUST 在 `manifest.json` 中显式区分执行真相与编译快照，禁止继续把 `compiled_plan`、`run_meta` 或输入快照视为并列执行真相。

#### Scenario: writing a new experiment manifest
- **WHEN** 系统写出 `manifest.json`
- **THEN** `execution_contract` MUST 作为独立核心 artifact 出现
- **THEN** `compiled_plan`、`input_config`、`resolved_config` SHALL 被标记为辅助快照或编译产物

### Requirement: run metadata MUST remain a runtime fact index

`run_meta.json` MUST 收口为运行事实索引，只保留运行事实、执行合同引用、依赖索引和 provenance。

#### Scenario: writing run metadata for a new experiment
- **WHEN** 系统写出 `run_meta.json`
- **THEN** `execution_contract_ref` MUST 成为正式执行真相定位锚
- **THEN** `provenance` MUST 独立表示来源与装配说明
- **THEN** 结果摘要、视图上下文和执行全文镜像 SHALL NOT 继续作为并列主真相对象

### Requirement: execution mirrors in run metadata MUST be compatibility-only

如果系统在兼容窗口内仍保留 `run_meta.execution_contract` 等全文镜像，它们 MUST 被明确标注为兼容副本，不得取代 `execution_contract_ref`。

#### Scenario: consuming run metadata during the compatibility window
- **WHEN** 调用方在 `run_meta.json` 中同时看到 `execution_contract_ref` 与 `execution_contract`
- **THEN** 调用方 MUST 以 `execution_contract_ref` 和独立 artifact 作为正式执行真相
- **THEN** 全文镜像 SHALL 只被视为兼容副本

