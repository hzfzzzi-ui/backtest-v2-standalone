# upstream-candidate-boundary-contracts Specification

## Purpose

Define the formal capability boundary for `upstream-candidate-boundary-contracts` in the current mainline.
## Requirements
### Requirement: 涓荤郴缁熷繀椤诲湪璁㈠崟瑙勫垝鍓嶆彁渚涘€欓€夎竟鐣屽悎鍚?
绯荤粺 MUST 鍦ㄥ叡浜墽琛岃繘鍏?`order_planning` 涔嬪墠鐢熸垚 `candidate_boundary_v1` 鍚堝悓锛岀敤浜庤〃杈惧綋鏃ュ凡缁忓畬鎴愬瓙绯荤粺鍚嶉銆佸吋瀹硅鍐冲拰鍊欓€夋埅鏂悗鐨勬寮忎拱鍏ュ€欓€夐泦鍚堛€傝鍚堝悓 MUST 鏃╀簬璁㈠崟瑙勫垝鐢熸垚锛屼笖 SHALL NOT 涓庢渶缁堢洰鏍囨寔浠撳崟娣蜂负鍚屼竴鐪熺浉銆?

#### Scenario: 澶氫俊鍙蜂釜鑲¤矾寰勮繘鍏ヨ鍗曡鍒掑墠鐢熸垚鍊欓€夎竟鐣?
- **WHEN** A鑲′釜鑲″淇″彿璺緞鍦ㄥ綋鏃ュ凡缁忓緱鍒?`day_signals`銆乣controls` 鍜屽崠鍑哄悗鐨勬寔浠撳崰鐢?
- **THEN** 绯荤粺 MUST 鍏堢敓鎴?`candidate_boundary_v1`
- **THEN** `order_planning` MUST 娑堣垂璇ュ悎鍚屼腑鐨勬渶缁堝€欓€夐泦鍚堬紝鑰屼笉鏄噸鏂拌В鏋愬瓙绯荤粺鏉冮噸鍜屽悕棰?

### Requirement: 鍊欓€夎竟鐣屽悎鍚屽繀椤昏褰曟渶灏忓彲瀹¤瑁佸喅鎽樿
`candidate_boundary_v1` MUST 鑷冲皯璁板綍 `decision_date`銆乣boundary_mode`銆乣selected_buy_symbols`銆乣owner_system_counts`銆乣slot_caps`銆乣available_slots`銆乣reject_reason_counts` 鍜屾渶灏忚瘖鏂憳瑕併€傝鍚堝悓 SHALL 鍙洖绛斺€滃摢浜涘€欓€夎鍏佽杩涘叆璁㈠崟瑙勫垝鈥濓紝鑰?SHALL NOT 鐩存帴鎵胯浇璁㈠崟鎴栨垚浜ょ粨鏋溿€?

#### Scenario: 璇诲彇鍊欓€夎竟鐣屾憳瑕?
- **WHEN** 鐮旂┒璇婃柇鎴栨棩绾у璁¤鍙栧綋鏃ュ€欓€夎竟鐣岀粨鏋?
- **THEN** 绯荤粺 MUST 杩斿洖鍊欓€夎竟鐣岀殑宸查€夊€欓€夈€佸悕棰濇憳瑕佸拰鎷掔粷鍘熷洜鎽樿
- **THEN** 杩斿洖缁撴灉 SHALL NOT 浼鎴愭渶缁堢洰鏍囨寔浠撴垨姝ｅ紡璁㈠崟鐪熺浉

