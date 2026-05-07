# Notes

- 这条 change 只把 `volume_price_quality_score` 与 `breakout_quality_score` 从主线组合里单独拉出。
- 当前研究样本仍然锚定到 `baseline_V10.1` 的 traded-core 真实样本。
- 本条能力不改变主线排序与执行，后续若要做 runtime A/B，必须单独起 change。
