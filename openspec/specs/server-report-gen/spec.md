# server-report-gen Specification

## Purpose

Define the formal capability boundary for `server-report-gen` in the current mainline.

## Requirements

### Requirement: 鍚庣鑷姩鐢熸垚 report.html
绯荤粺 SHALL 鍦ㄦ瘡娆″洖娴?stabilize 闃舵鑷姩鐢熸垚 `report.html` 鏂囦欢锛屽瓨鏀惧湪瀹為獙鐩綍鍐呫€?

#### Scenario: 姝ｅ父鐢熸垚
- **WHEN** stabilize_experiment_result 瀹屾垚鎵€鏈夋爣鍑嗕骇鐗╁啓鍏?
- **THEN** 绯荤粺 SHALL 璋冪敤 report_generator.generate_report(results_dir)锛岀敓鎴愯嚜鍖呭惈 HTML 鎶ュ憡鍐欏叆 results_dir/report.html

#### Scenario: 鎶ュ憡鍖呭惈瀹屾暣 7 涓珷鑺?
- **WHEN** report.html 鐢熸垚
- **THEN** 鎶ュ憡 SHALL 鍖呭惈锛毬? 姒傝锛圞PI 鍗＄墖锛夈€伮? 鏈堝害鏀剁泭琛ㄣ€伮? 鍥炴挙鍒嗘瀽銆伮? 浜ゆ槗鍒嗘瀽锛堝惈婕忔枟鍜屽師鍥犲垎甯冿級銆伮? 鎸佷粨鍒嗘瀽銆伮? 绛栫暐鍙傛暟锛? 涓瓙琛級銆伮? 浜ゆ槗鏄庣粏闄勫綍

#### Scenario: 鎶ュ憡鑷寘鍚?
- **WHEN** report.html 鐢熸垚
- **THEN** 鎶ュ憡 SHALL 浣跨敤鍐呰仈 CSS锛屾棤澶栭儴渚濊禆锛屽彲鐩存帴鐢ㄦ祻瑙堝櫒鎵撳紑鎴?Ctrl+P 鎵撳嵃涓?PDF

#### Scenario: 涓枃鑲＄エ鍚嶆樉绀?
- **WHEN** report.html 娓叉煋浜ゆ槗鏄庣粏涓?stock_names.json 瀛樺湪
- **THEN** 鏍囩殑鍒?SHALL 鏄剧ず涓枃鍚嶇О锛堝銆岃吹宸炶寘鍙般€嶏級锛屽師濮嬩唬鐮佷綔涓?title 灞炴€?

#### Scenario: reason_code 涓枃鍖?
- **WHEN** report.html 娓叉煋浜ゆ槗鏄庣粏鎴栧钩浠撳師鍥犲垎甯?
- **THEN** 宸茬煡 reason_code SHALL 缈昏瘧涓轰腑鏂囷紙SMA_CROSS_UP 鈫?鍧囩嚎閲戝弶锛夛紝鏈煡 code 鏄剧ず鍘熷鍊?

#### Scenario: 鐢熸垚澶辫触涓嶉樆濉炲洖娴?
- **WHEN** report_generator 鎵ц杩囩▼涓彂鐢熷紓甯?
- **THEN** 绯荤粺 SHALL 璁板綍閿欒鏃ュ織锛屼絾涓嶅奖鍝嶅洖娴嬬粨鏋滅殑姝ｅ父杩斿洖锛沵anifest.json 涓?report 瀛楁涓?null


