# baseline-moneyflow-overlay-diagnostics Specification

## Purpose

Define the formal capability boundary for `baseline-moneyflow-overlay-diagnostics` in the current mainline.
## Requirements
### Requirement: Overlay 杩愯鍏冧俊鎭繀椤昏繘鍏ュ疄楠屼骇鐗?
褰?overlay 寮€鍚椂锛岀郴缁?MUST 鍦ㄥ疄楠屼骇鐗╀腑璁板綍 overlay 鐨勯厤缃笌杈撳叆鏉ユ簮锛岃嚦灏戝寘鎷ā寮忋€乫actor panel 璺緞銆乧overage ledger 璺緞銆乻core 瀛楁鍜屾槸鍚﹀惎鐢ㄣ€?

#### Scenario: Run Meta 璁板綍 overlay 閰嶇疆
- **WHEN** overlay 瀹為獙杩愯瀹屾垚
- **THEN** `run_meta` 鎴栫瓑浠疯繍琛屽厓淇℃伅涓繀椤诲寘鍚?overlay 鐨勬牳蹇冮厤缃笌杈撳叆璺緞

### Requirement: 姣忎釜鍐崇瓥鏃ュ繀椤昏褰?overlay 鍚仠涓庡喕缁撴潵婧?
褰?overlay 寮€鍚椂锛岀郴缁?MUST 鍦ㄦ棩棰戣瘖鏂腑璁板綍姣忎釜鍐崇瓥鏃ョ殑 overlay 鐘舵€侊紝鑷冲皯鍖呮嫭锛?

- `overlay_enabled`
- `overlay_mode`
- `overlay_gate_on`
- `overlay_observation_date`
- `overlay_score_source`

褰?overlay 寮€鍚椂锛岀郴缁?MUST 鍦ㄦ棩棰戣瘖鏂腑璁板綍姣忎釜鍐崇瓥鏃ョ殑 overlay 鐘舵€侊紝鑷冲皯鍖呮嫭锛?

- `overlay_enabled`
- `overlay_mode`
- `overlay_gate_on`
- `overlay_observation_date`
- `overlay_score_source`

#### Scenario: 瑕嗙洊鐜囧叧闂殑鏈堜唤鍐欏叆绂佺敤鐘舵€?
- **WHEN** 鏌愬喅绛栨棩鎵€鍦ㄥ喕缁撳尯闂寸殑 coverage gate 涓哄叧闂?
- **THEN** 璇ユ棩璇婃柇涓繀椤昏褰?`overlay_gate_on=false` 鍜屽搴旂殑瑙傚療鏃ユ垨绂佺敤鍘熷洜

#### Scenario: 瑕嗙洊鐜囪揪鏍囩殑鏈堜唤鍐欏叆鍐荤粨鏉ユ簮
- **WHEN** 鏌愬喅绛栨棩浣跨敤浜嗘渶杩戜竴娆¤瀵熸棩鐨?overlay 鍒嗘暟
- **THEN** 璇ユ棩璇婃柇涓繀椤昏褰曞綋鍓嶅喕缁撴墍鏉ヨ嚜鐨?`overlay_observation_date`### Requirement: 鍊欓€夌骇璇婃柇蹇呴』鑳界湅瑙?overlay 鍒嗘暟
褰?overlay 寮€鍚椂锛岀郴缁?MUST 鍦ㄥ€欓€夌骇璇婃柇涓啓鍑烘瘡涓€欓€夋爣鐨勭殑 overlay 鍒嗘暟锛屽苟鍦ㄩ渶瑕佹椂鍐欏嚭 baseline 涓绘帓搴忓垎鏁帮紝纭繚鍚庣画鍙互澶嶇洏鈥滄帓搴忔病鍙樹絾浠撲綅鍙樹簡鈥濇垨鈥滄帓搴忎负浠€涔堣娆＄骇閿敼鍙樷€濄€?

#### Scenario: Tiebreak 璁板綍鍙屾帓搴忎俊鎭?
- **WHEN** overlay 妯″紡涓?`tiebreak`
- **THEN** 鍊欓€夌骇璇婃柇蹇呴』鑳藉悓鏃剁湅鍒?baseline 涓绘帓搴忓垎鏁颁笌 overlay 鍒嗘暟

#### Scenario: Soft Weight 璁板綍鏉冮噸缂╂斁渚濇嵁
- **WHEN** overlay 妯″紡涓?`soft_weight`
- **THEN** 鍊欓€夌骇璇婃柇蹇呴』璁板綍 overlay 鍒嗘暟浠ュ強鏈€缁堜娇鐢ㄧ殑浠撲綅缂╂斁淇℃伅

### Requirement: 鍊欓€夌骇璇婃柇蹇呴』鑳界湅瑙?overlay 鍒嗘暟
褰?overlay 寮€鍚椂锛岀郴缁?MUST 鍦ㄥ€欓€夌骇璇婃柇涓啓鍑烘瘡涓€欓€夋爣鐨勭殑 overlay 鍒嗘暟锛屽苟鍦ㄩ渶瑕佹椂鍐欏嚭 baseline 涓绘帓搴忓垎鏁帮紝纭繚鍚庣画鍙互澶嶇洏鈥滄帓搴忔病鍙樹絾浠撲綅鍙樹簡鈥濇垨鈥滄帓搴忎负浠€涔堣娆＄骇閿敼鍙樷€濄€?

#### Scenario: Tiebreak 璁板綍鍙屾帓搴忎俊鎭?
- **WHEN** overlay 妯″紡涓?`tiebreak`
- **THEN** 鍊欓€夌骇璇婃柇蹇呴』鑳藉悓鏃剁湅鍒?baseline 涓绘帓搴忓垎鏁颁笌 overlay 鍒嗘暟

#### Scenario: Soft Weight 璁板綍鏉冮噸缂╂斁渚濇嵁
- **WHEN** overlay 妯″紡涓?`soft_weight`
- **THEN** 鍊欓€夌骇璇婃柇蹇呴』璁板綍 overlay 鍒嗘暟浠ュ強鏈€缁堜娇鐢ㄧ殑浠撲綅缂╂斁淇℃伅

