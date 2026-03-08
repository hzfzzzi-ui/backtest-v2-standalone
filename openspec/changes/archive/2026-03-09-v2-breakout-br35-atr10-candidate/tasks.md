## 1. Locked Candidate
- [x] 1.1 新增 `v2-breakout-br35-atr10-candidate` locked candidate，锚定 ATR1.0 formal candidate 底座，只允许 `strategy.params.breakout_window=35` 漂移。
- [x] 1.2 为新 candidate 写出 provenance、summary 和 evidence bundle，并保持旧 ATR1.0 candidate 入口不变。

## 2. Frontend Exposure
- [x] 2.1 在前端 preset 下拉中显式暴露 BR35 candidate，并保持默认草稿入口不变。
- [x] 2.2 在 builtin config store 中新增 `BR35+ATR1.0+CSI800+10Y`，使其自动出现在前端“加载”列表中。

## 3. Verification
- [x] 3.1 端到端验证：前端能加载 builtin config；新 preset 能跑出 locked candidate artifacts。
- [x] 3.2 重启容器并复核接口可用，供后续手动实验使用。
