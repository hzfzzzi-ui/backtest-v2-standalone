# 4.3 A/B 对比报告

## 结论

`CN_STOCK_ETF_FORMAL_V1` 对应的 formal 候选组合已经满足“审计全 PASS”，但**不满足**当前收益守门线，因此本次 change 的合同收口可以结束，**baseline 晋升不成立**。

- formal 候选：`exp_20260426_005716047_8650`
- 守门线锚点：`exp_20260413_051231810_0b74`

## 证据

formal 候选：

- `outputs/experiments/exp_20260426_005716047_8650/perf.json`
- `outputs/experiments/exp_20260426_005716047_8650/audit.json`

守门线锚点：

- `outputs/experiments/archive/2026-04-26-retention-sweep/exp_20260413_051231810_0b74/perf.json`

## 指标对比

| 指标 | 守门线锚点 | formal 候选 | 差值 | 判断 |
|---|---:|---:|---:|---|
| CAGR | 13.3043% | 8.1989% | -5.1053pct | 明显更差 |
| Sharpe | 0.4908 | 0.7775 | +0.2868 | 更好 |
| MaxDD | -31.3888% | -16.6413% | +14.7475pct | 明显更好 |
| Calmar | 0.4239 | 0.4927 | +0.0688 | 更好 |
| 审计 | 未作为 formal PASS 候选 | PASS | - | formal 候选通过 |

## 判定

1. formal 候选在审计侧已经完成 promotion 所需的 formal 合同收口，`overall_status = PASS`。
2. formal 候选在风险调整后表现更好，`Sharpe / MaxDD / Calmar` 均优于守门线锚点。
3. 但 formal 候选的 `CAGR` 从 `13.30%` 降到 `8.20%`，降幅超过 `5pct`，不能解释为“不明显差于”。
4. 因此本次 change 的**实现结论**是：
   - ETF formal contract、combo formal audit、formal output truth 已收口完成
   - baseline 晋升结论为 **deferred / not promoted**
   - 当前 live combo baseline 不因本 change 自动升级

## 对后续治理的影响

- `promote-stock-etf-combo-to-formal-mainline` 可以归档，因为 formal mainline 合同与验证路径已经完成。
- 是否将 `CN_STOCK_ETF_FORMAL_V1` 提升为唯一 active baseline，不由本 change 解决，应继续留在 `govern-single-active-baseline-and-study-conclusions` 中处理。
