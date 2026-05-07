# sim-account-db-persistence Specification

## Purpose

Define the formal capability boundary for `sim-account-db-persistence` in the current mainline.
## Requirements
### Requirement: sim_account 姝ｅ紡瀵硅薄杩涘叆涓氬姟浜嬪姟鍩熸暟鎹簱
绯荤粺 SHALL 灏?`accounts`銆乣holdings_snapshots`銆乣cash_ledger` 涓?`sync_logs` 瀹氫箟涓?`sim_account` 鍦ㄤ笟鍔′簨鍔″煙涓殑姝ｅ紡鏁版嵁搴撳璞★紝鑰屼笉鍐嶉暱鏈熶緷璧?`outputs/ops/sim_account/*` 鏂囦欢璺緞銆?
#### Scenario: 璐︽埛鐘舵€佹寮忎粠鏁版嵁搴撳璞¤鍙?- **WHEN** 绯荤粺闇€瑕佽鍙栨煇涓ā鎷熻处鎴风殑褰撳墠鎸佷粨涓庣幇閲戠姸鎬?- **THEN** 姝ｅ紡璇诲彇璺緞 MUST 鏉ヨ嚜浜嬪姟鍩熸暟鎹簱瀵硅薄

### Requirement: reconcile 鍙繚鐣欐憳瑕佷笌寮曠敤
绯荤粺 SHALL 灏?`reconcile` 瀹氫箟涓烘淳鐢熷垎鏋愮粨鏋滐紝鍙厑璁?`reconcile_summary` 鎴栧紩鐢ㄧ储寮曡繘鍏ユ寮忎簨鍔″煙瀵硅薄銆?
#### Scenario: reconcile 涓嶅啀鍏呭綋搴曞眰鐪熺浉
- **WHEN** 绯荤粺闇€瑕佸睍绀烘渶杩戜竴娆?reconcile 缁撴灉
- **THEN** 姝ｅ紡鏁版嵁搴撳璞?MUST 鍙繑鍥炴憳瑕佷笌寮曠敤锛岃€屼笉鏄畬鏁存淳鐢?payload

### Requirement: compat 鏂囦欢鍙綔涓鸿縼绉绘湡褰卞瓙鍐欏嚭
绯荤粺 SHALL 鍏佽杩佺Щ鏈熺户缁繚鐣?`outputs/ops/sim_account/*` 褰卞瓙鍐欏嚭锛屼絾 compat 鏂囦欢 MUST 涓嶅啀瀹氫箟姝ｅ紡璇诲彇杈圭晫銆?
#### Scenario: 鏁版嵁搴撶湡鐩镐紭鍏堜簬 compat 鏂囦欢
- **WHEN** 鏁版嵁搴撳璞′笌 compat 鏂囦欢鍚屾椂瀛樺湪
- **THEN** 姝ｅ紡璇诲彇璺緞 MUST 浼樺厛浣跨敤鏁版嵁搴撳璞?

