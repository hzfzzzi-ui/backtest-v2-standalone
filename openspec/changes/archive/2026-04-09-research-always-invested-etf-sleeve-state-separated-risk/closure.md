# Closure

结论：`no-go`

原因：
- `always-invested ETF sleeve` 的确提高了 ETF 非零持仓率，但同时把 ETF 做成了第二条权益腿：
  - baseline：`exp_20260407_070626665_8e4d`
  - always-on：`exp_20260407_071543297_3437`
  - `CAGR 13.76% -> 4.14%`
  - `Sharpe 0.4821 -> 0.3052`
  - `Calmar 0.4318 -> 0.0904`
  - `MaxDD -31.86% -> -45.81%`
- 风险错开失败：
  - `stock/ETF corr 0.0614 -> 0.4883`
  - `stock-down-day corr 0.0339 -> 0.7419`

明确结论：
- 当前阶段不能把 ETF 直接做成全程常驻权益腿。
- 这条 change 不进入主线。
