# symbol-performance-ranking Specification

## Purpose

Define the formal capability boundary for `symbol-performance-ranking` in the current mainline.
## Requirements
### Requirement: 鍥炴祴缁撴灉蹇呴』杈撳嚭涓偂缁╂晥姹囨€讳骇鐗?
绯荤粺 MUST 鍦ㄦ瘡娆″疄楠屽畬鎴愬悗杈撳嚭鍙鍙栫殑涓偂缁╂晥姹囨€讳骇鐗╋紝鑷冲皯鍖呭惈姣忎釜 symbol 鐨勬敹鐩婄巼銆佸洖鎾ゃ€佸噣鏀剁泭銆佷氦鏄撴鏁颁笌鏈钩浠撹繎浼兼敹鐩婂瓧娈点€?

#### Scenario: 瀹為獙瀹屾垚骞剁敓鎴愭爣鍑嗕骇鐗?
- **WHEN** 鍥炴祴浠诲姟鐘舵€佸彉涓烘垚鍔熷苟鍐欏叆 artifacts
- **THEN** 绯荤粺 SHALL 鐢熸垚 `symbol_performance.csv` 浜х墿
- **THEN** `result.artifacts.symbol_performance` SHALL 鎸囧悜璇ユ枃浠剁殑鐩稿璺緞
- **THEN** 姣忔潯璁板綍 SHALL 鑷冲皯鍖呭惈 `symbol`, `return_pct`, `max_drawdown`, `net_pnl`, `trades`, `unrealized_approx_pnl`

### Requirement: 涓偂缁╂晥浜х墿蹇呴』鏀寔绌烘枃浠堕檷绾?
绯荤粺 MUST 鍦ㄦ棤娉曡绠椾釜鑲＄哗鏁堟椂鍐欏嚭鍚堟硶绌轰骇鐗╋紝閬垮厤鍗忚缂哄け銆?

#### Scenario: 鏃犱氦鏄撴垨鏃犲彲鐢ㄤ及鍊兼暟鎹?
- **WHEN** 鍥炴祴鏈熼棿鏃犱氦鏄撹褰曪紝鎴栦釜鑲′及鍊兼暟鎹笉鍙敤
- **THEN** 绯荤粺 SHALL 鍐欏嚭 `symbol_performance.csv` 涓斾粎鍖呭惈琛ㄥご鎴栫┖璁板綍
- **THEN** 绯荤粺 SHALL 鍦?`run_meta.missing_fields` 璁板綍瀵瑰簲缂哄け鏉ユ簮

#### Scenario: 鍓嶇璇诲彇绌轰釜鑲＄哗鏁堜骇鐗?
- **WHEN** 鍓嶇鍔犺浇 `symbol_performance.csv` 涓旀棤鏁版嵁琛?
- **THEN** 鍓嶇 SHALL 鏄剧ず绌虹姸鎬佽€岄潪鎶ラ敊
- **THEN** 鍏朵粬缁╂晥闈㈡澘涓庡浘琛?SHALL 姝ｅ父宸ヤ綔

