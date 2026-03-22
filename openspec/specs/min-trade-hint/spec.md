# min-trade-hint Specification

## Purpose

定义前端对最小成交资金门槛的提示要求，帮助用户在运行前识别 `SKIP_LOT_TOO_SMALL` 风险。

## Requirements

### Requirement: Minimum trade cost hint
The Position & Risk block SHALL display a hint estimating the minimum cash required to buy one lot, and warn when SKIP_LOT_TOO_SMALL may be triggered.

#### Scenario: Hint populated after data load
- **WHEN** universe validation completes and stock price data is available
- **THEN** the hint SHALL display an estimated "买一手所需现金" based on the most recent closing price of the most expensive stock in the universe multiplied by the lot size

#### Scenario: Warning when capital may be insufficient
- **WHEN** the estimated one-lot cost exceeds initial capital divided by max_positions
- **THEN** a warning message SHALL appear: "可能触发 SKIP_LOT_TOO_SMALL"

#### Scenario: Placeholder label
- **WHEN** no price data is available
- **THEN** the hint SHALL display "(即将支持)" badge
