# bull-breakout-quality-veto Specification

## Purpose

Define the formal capability boundary for `bull-breakout-quality-veto` in the current mainline.
## Requirements
### Requirement: BULL breakout quality veto

绯荤粺 SHALL 鏀寔涓€涓彲閫夌殑 `bull_breakout_quality_veto`锛屼粎鍦?`BULL / TREND_MAIN` 璇箟涓嬪 breakout 鏂颁拱鍏ュ€欓€夋墽琛屼綆鑷敱搴︺€佸彲瑙ｉ噴鐨勫潖 breakout 闃绘柇銆?

棣栬疆 veto 鍙厑璁镐娇鐢ㄤ互涓嬩袱涓幇鏈夌壒寰侊細

- `residual_strength_score`
- `breakout_margin_score`

涓斿彧浣滅敤浜庯細

- `alpha_source = breakout`
- `alpha_source = pullback_overlap`

绯荤粺 SHALL 鏀寔涓€涓彲閫夌殑 `bull_breakout_quality_veto`锛屼粎鍦?`BULL / TREND_MAIN` 璇箟涓嬪 breakout 鏂颁拱鍏ュ€欓€夋墽琛屼綆鑷敱搴︺€佸彲瑙ｉ噴鐨勫潖 breakout 闃绘柇銆?

棣栬疆 veto 鍙厑璁镐娇鐢ㄤ互涓嬩袱涓幇鏈夌壒寰侊細

- `residual_strength_score`
- `breakout_margin_score`

涓斿彧浣滅敤浜庯細

- `alpha_source = breakout`
- `alpha_source = pullback_overlap`

#### Scenario: veto 鍏抽棴鏃惰涓轰笉鍙?
- **WHEN** `bull_breakout_quality_veto_enabled = false` 鎴栨湭閰嶇疆
- **THEN** breakout provider 鐨勪拱鍏ュ€欓€夎涓?SHALL 涓庡彉鏇村墠瀹屽叏涓€鑷?

#### Scenario: 鍙湪 BULL 涓昏秼鍔胯涔変笅搴旂敤
- **WHEN** `ctx.market_state != "BULL"` 鎴?`ctx.risk_on = false`
- **THEN** bull breakout quality veto SHALL 涓嶇敓鏁?

#### Scenario: 鍙樆鏂?breakout / overlap
- **WHEN** 鍊欓€?`alpha_source` 涓嶅睘浜?`breakout` 鎴?`pullback_overlap`
- **THEN** bull breakout quality veto SHALL 涓嶇敓鏁?

#### Scenario: residual_strength 涓嶈揪鏍囨椂闃绘柇
- **WHEN** `bull_breakout_quality_veto_enabled = true`
- **AND** `ctx.market_state = "BULL"`
- **AND** 鍊欓€変负 breakout / overlap
- **AND** `residual_strength_score < bull_breakout_quality_veto_min_residual_strength_score`
- **THEN** 璇ュ€欓€?SHALL 琚樆鏂?
- **THEN** 闃绘柇 reason_code SHALL 璁板綍涓?`BLOCK_BULL_QUALITY_VETO`

#### Scenario: breakout_margin 涓嶈揪鏍囨椂闃绘柇
- **WHEN** `bull_breakout_quality_veto_enabled = true`
- **AND** `ctx.market_state = "BULL"`
- **AND** 鍊欓€変负 breakout / overlap
- **AND** `breakout_margin_score < bull_breakout_quality_veto_min_breakout_margin_score`
- **THEN** 璇ュ€欓€?SHALL 琚樆鏂?
- **THEN** 闃绘柇 reason_code SHALL 璁板綍涓?`BLOCK_BULL_QUALITY_VETO`### Requirement: Bull breakout quality veto AB

绯荤粺 SHALL 鏀寔鍩轰簬褰撳墠姝ｅ紡 `baseline_V10.2` 鎵ц涓€杞渶灏?A/B锛?

- A = `baseline_V10.2`
- B = `baseline_V10.2 + bull_breakout_quality_veto`

AB 鐨勫敮涓€ intended diff SHALL 鏄細

- `bull_breakout_quality_veto_enabled = true`
- `bull_breakout_quality_veto_min_residual_strength_score`
- `bull_breakout_quality_veto_min_breakout_margin_score`

#### Scenario: intended diff 鍗曚竴
- **WHEN** 杩愯鏈疆 A/B
- **THEN** 闄?veto 涓変釜瀛楁澶栵紝鍏朵綑 universe / data_role / market_filter / exit / sizing / ranking 鏍?SHALL 淇濇寔涓€鑷?

#### Scenario: 杈撳嚭姝ｅ紡瀵圭収浜х墿
- **WHEN** A/B 杩愯瀹屾垚
- **THEN** 杈撳嚭鐩綍 SHALL 鑷冲皯鍖呭惈锛?
  - `summary.json`
  - `report.md`
  - `performance_comparison.csv`
  - `bull_trade_quality_comparison.csv`

### Requirement: Bull breakout quality veto AB

绯荤粺 SHALL 鏀寔鍩轰簬褰撳墠姝ｅ紡 `baseline_V10.2` 鎵ц涓€杞渶灏?A/B锛?

- A = `baseline_V10.2`
- B = `baseline_V10.2 + bull_breakout_quality_veto`

AB 鐨勫敮涓€ intended diff SHALL 鏄細

- `bull_breakout_quality_veto_enabled = true`
- `bull_breakout_quality_veto_min_residual_strength_score`
- `bull_breakout_quality_veto_min_breakout_margin_score`

#### Scenario: intended diff 鍗曚竴
- **WHEN** 杩愯鏈疆 A/B
- **THEN** 闄?veto 涓変釜瀛楁澶栵紝鍏朵綑 universe / data_role / market_filter / exit / sizing / ranking 鏍?SHALL 淇濇寔涓€鑷?

#### Scenario: 杈撳嚭姝ｅ紡瀵圭収浜х墿
- **WHEN** A/B 杩愯瀹屾垚
- **THEN** 杈撳嚭鐩綍 SHALL 鑷冲皯鍖呭惈锛?
  - `summary.json`
  - `report.md`
  - `performance_comparison.csv`
  - `bull_trade_quality_comparison.csv`

