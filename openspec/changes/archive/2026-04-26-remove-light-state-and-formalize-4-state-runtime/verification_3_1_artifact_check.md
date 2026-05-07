# 3.1 主回放证据补充

## 结论

当前宿主机直连环境仍无法解析 `pams-postgres`，因此**没有在本地现环境重新跑一遍主回放**。  
但可以用当前正式基线链接的正式实验产物完成“无正式 `LIGHT` 输出”的证据型闭环。

## 正式证据源

- baseline: [outputs/baselines/CN_STOCK_ETF_FORMAL_V1/baseline.json](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/baselines/CN_STOCK_ETF_FORMAL_V1/baseline.json)
- linked experiment: `exp_20260426_005716047_8650`
- unified mainline manifest: [manifest.json](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260426_005716047_8650/manifest.json)

## 检查范围

以下正式产物已核查：

- [portfolio_daily.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260426_005716047_8650/portfolio_daily.csv)
- [run_meta.json](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260426_005716047_8650/run_meta.json)
- [audit.json](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260426_005716047_8650/audit.json)
- [regime_audit_summary.json](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260426_005716047_8650/regime_audit_summary.json)

结论：

- 正式状态输出中未检出 `LIGHT`
- 正式 5-state 输出使用 `BULL / TRANS_UP / TRANS_DOWN / RISK_OFF`
- 该实验可作为当前 4-state 正式化的主线证据

## 保留说明

这是一种**artifact-verified** 结案，而不是**environment-replayed** 结案。  
环境阻塞仍然存在：宿主机直连运行链路不能解析 `pams-postgres`，所以不能把本条误写成“现环境已可重跑主回放”。
