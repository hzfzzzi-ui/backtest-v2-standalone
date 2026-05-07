# csi800-tushare-pit-history Specification

## Purpose

Define the formal capability boundary for `csi800-tushare-pit-history` in the current mainline.
## Requirements
### Requirement: CSI800 姝ｅ紡 PIT 鍘嗗彶蹇呴』鍩轰簬 Tushare 瀹為檯 trade_date 鍙樺寲閲嶅缓
绯荤粺 MUST 涓?`000906.SH` 鎻愪緵涓€鏉℃寮?`Tushare` PIT 鍘嗗彶閾撅紝鍩轰簬 `index_weight` 鐨勫疄闄?`trade_date` 鎴愬垎闆嗗悎鍙樺寲閲嶅缓 snapshots 鍜?changes锛岃€屼笉鏄户缁妸鏈堟湯閲嶅缓缁撴灉褰撲綔姝ｅ紡鍘嗗彶銆?

绯荤粺 MUST 涓?`000906.SH` 鎻愪緵涓€鏉℃寮?`Tushare` PIT 鍘嗗彶閾撅紝鍩轰簬 `index_weight` 鐨勫疄闄?`trade_date` 鎴愬垎闆嗗悎鍙樺寲閲嶅缓 snapshots 鍜?changes锛岃€屼笉鏄户缁妸鏈堟湯閲嶅缓缁撴灉褰撲綔姝ｅ紡鍘嗗彶銆?

#### Scenario: 鍩轰簬瀹為檯 trade_date 鐢熸垚 snapshots
- **WHEN** 绯荤粺鎵ц `CSI800` 姝ｅ紡 PIT 鎶撳彇鑴氭湰
- **THEN** 绯荤粺 MUST 浠?`Tushare index_weight(index_code='000906.SH')` 璇诲彇 `trade_date` 鍜屾垚鍒嗛泦鍚?
- **THEN** 绯荤粺 MUST 鍙鏈夋晥 trade_date 鐢熸垚鍙鏍哥殑 snapshots 鍜?changes 鏂囦欢

#### Scenario: 閮ㄥ垎 trade_date 涓嶅緱鍐掑厖姝ｅ紡蹇収
- **WHEN** 鏌愪釜 `trade_date` 鐨勬垚鍒嗛泦鍚堜笉瀹屾暣锛屾垨鏃犳硶鏋勬垚瀹屾暣鐨?800 鎴愬垎蹇収
- **THEN** 绯荤粺 MUST 灏嗚鏃ユ湡鎺掗櫎鍑烘寮?snapshots
- **THEN** 绯荤粺 MUST 鍦ㄦ憳瑕佷腑璁板綍琚烦杩囩殑鏃ユ湡缁熻锛岃€屼笉鏄潤榛樺苟鍏ユ寮忓巻鍙?## Requirement: CSI800 姝ｅ紡 Tushare 閾惧繀椤昏緭鍑虹粨鏋勫寲鎶撳彇鎽樿
绯荤粺 MUST 鍦?`CSI800` 姝ｅ紡 PIT 鎶撳彇瀹屾垚鍚庤緭鍑虹粨鏋勫寲鎽樿锛屼究浜庝汉宸ユ牳楠岃鐩栨儏鍐点€乻ource label 鍜屽彲鐢?trade_date 璐ㄩ噺銆?

#### Scenario: 鎶撳彇鎽樿鍖呭惈鍏抽敭缁熻
- **WHEN** `CSI800` 姝ｅ紡 PIT 鎶撳彇鑴氭湰鎴愬姛瀹屾垚
- **THEN** 绯荤粺 MUST 杈撳嚭鑷冲皯鍖呭惈 `snapshot_dates`銆乣usable_trade_dates`銆乣skipped_trade_dates`銆乣changes_rows` 鍜?`source_label` 鐨勬憳瑕?

#### Scenario: 鏃犳硶褰㈡垚姝ｅ紡鍘嗗彶鏃舵樉寮忓け璐?
- **WHEN** 鎸囧畾鍖洪棿鍐呮病鏈変换浣曞彲鐢ㄧ殑瀹屾暣 trade_date
- **THEN** 绯荤粺 MUST 缁堟姝ｅ紡鎶撳彇骞惰繑鍥為敊璇?
- **THEN** 绯荤粺 MUST NOT 鐢熸垚浼€犵殑姝ｅ紡 changes 鏂囦欢

### Requirement: CSI800 姝ｅ紡 Tushare 閾惧繀椤昏緭鍑虹粨鏋勫寲鎶撳彇鎽樿
绯荤粺 MUST 鍦?`CSI800` 姝ｅ紡 PIT 鎶撳彇瀹屾垚鍚庤緭鍑虹粨鏋勫寲鎽樿锛屼究浜庝汉宸ユ牳楠岃鐩栨儏鍐点€乻ource label 鍜屽彲鐢?trade_date 璐ㄩ噺銆?

#### Scenario: 鎶撳彇鎽樿鍖呭惈鍏抽敭缁熻
- **WHEN** `CSI800` 姝ｅ紡 PIT 鎶撳彇鑴氭湰鎴愬姛瀹屾垚
- **THEN** 绯荤粺 MUST 杈撳嚭鑷冲皯鍖呭惈 `snapshot_dates`銆乣usable_trade_dates`銆乣skipped_trade_dates`銆乣changes_rows` 鍜?`source_label` 鐨勬憳瑕?

#### Scenario: 鏃犳硶褰㈡垚姝ｅ紡鍘嗗彶鏃舵樉寮忓け璐?
- **WHEN** 鎸囧畾鍖洪棿鍐呮病鏈変换浣曞彲鐢ㄧ殑瀹屾暣 trade_date
- **THEN** 绯荤粺 MUST 缁堟姝ｅ紡鎶撳彇骞惰繑鍥為敊璇?
- **THEN** 绯荤粺 MUST NOT 鐢熸垚浼€犵殑姝ｅ紡 changes 鏂囦欢

