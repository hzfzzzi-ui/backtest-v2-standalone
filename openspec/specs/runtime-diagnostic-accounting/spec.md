# runtime-diagnostic-accounting Specification

## Purpose

Define the formal capability boundary for `runtime-diagnostic-accounting` in the current mainline.
## Requirements
### Requirement: Runtime diagnostics 蹇呴』閫氳繃鐙珛 snapshot contract 浼犻€?
绯荤粺 MUST 瀹氫箟鐙珛鐨?runtime diagnostics snapshot / input contract锛岀敤浜庢壙鎺ユ墽琛屽眰浜х敓鐨勫師濮嬭瘖鏂緭鍏ワ紝骞朵綔涓?artifact diagnostics 涓?surface counters 鐨勫敮涓€杈撳叆杈圭晫銆?

#### Scenario: 鎵ц灞備骇鐢熸棩绾ц瘖鏂緭鍏?
- **WHEN** 鎵ц灞傚畬鎴愭煇涓氦鏄撴棩鐨勬寔浠撱€佽鍗曞拰淇″彿澶勭悊
- **THEN** 绯荤粺 MUST 浜у嚭鐙珛鐨?runtime diagnostics input锛岃€屼笉鏄洿鎺ュ湪鎵ц鍑芥暟涓畾涔夋渶缁?funnel 鍙ｅ緞
- **THEN** 璇?input MUST 鍖呭惈 stage 璁℃暟褰掍竴鍖栨墍闇€鐨勫師濮嬩簨浠跺瓧娈?

#### Scenario: artifact diagnostics 娑堣垂鎵ц璇婃柇
- **WHEN** diagnostics builder 鐢熸垚 buy funnel銆乺eason counters 鎴?surface diagnostics
- **THEN** 绯荤粺 MUST 鍙秷璐?runtime diagnostics snapshot / input
- **THEN** diagnostics builder SHALL NOT 鐩存帴渚濊禆鎵ц寰幆鍐呴儴鐨勯殣寮忓眬閮ㄥ彉閲?

### Requirement: Stage count 褰掍竴鍖栧繀椤诲睘浜?diagnostics 灞?
绯荤粺 MUST 灏?`buy_candidate_count`銆乣after_held_filter_count`銆乣after_slot_filter_count`銆乣after_cash_lot_count` 绛夋渶缁?stage 璁℃暟璇箟瀹氫箟鍦?diagnostics 灞傦紝鑰屼笉鏄墽琛屽眰銆?

绯荤粺 MUST 灏?`buy_candidate_count`銆乣after_held_filter_count`銆乣after_slot_filter_count`銆乣after_cash_lot_count` 绛夋渶缁?stage 璁℃暟璇箟瀹氫箟鍦?diagnostics 灞傦紝鑰屼笉鏄墽琛屽眰銆?

#### Scenario: route 涓撳睘 stage 璁℃暟褰掍竴鍖?
- **WHEN** breakout route 鎴栧叾浠?route 闇€瑕佸鍘熷璁℃暟鍋氬彛寰勫綊涓€鍖?
- **THEN** 绯荤粺 MUST 鍦?diagnostics builder 涓畬鎴愬綊涓€鍖?
- **THEN** 鎵ц灞?SHALL NOT 鐩存帴鍐欏叆鏈€缁?UI 鎴?artifact stage 璇箟

#### Scenario: baseline funnel 瀵圭収
- **WHEN** 绯荤粺瀵?`baseline_V10.1` 瀵瑰簲瀹為獙鎵ц diagnostics compare
- **THEN** 褰掍竴鍖栧悗鐨?stage count MUST 涓庢棦鏈?baseline 缁撴灉涓€鑷?
- **THEN** 浠讳竴宸紓閮?MUST 琚涓?diagnostics 鍙ｅ緞婕傜Щ

