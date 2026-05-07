# Spec

## ADDED Requirements

### Requirement: Moneyflow overlay veto mode for research A/B

系统 MUST 支持通过 `asset_context.moneyflow_overlay.mode` 以字符串模式声明底部分桶 veto。

#### Example: veto bottom 20 percent

- Given `mode = veto_bottom20`
- And moneyflow overlay gate is on
- When candidate planning runs
- Then the bottom 20 percent of candidates by overlay score are rejected with `MONEYFLOW_OVERLAY_VETO`

#### Example: veto bottom 30 percent

- Given `mode = veto_bottom30`
- And moneyflow overlay gate is on
- When candidate planning runs
- Then the bottom 30 percent of candidates by overlay score are rejected with `MONEYFLOW_OVERLAY_VETO`

#### Example: legacy overlay modes remain unchanged

- Given `mode = tiebreak` or `soft_weight` or `shadow`
- When candidate planning runs
- Then legacy behavior remains unchanged
