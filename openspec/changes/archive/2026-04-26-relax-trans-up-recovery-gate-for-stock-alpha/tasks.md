## 1. 实现

- [x] 1.1 在 `MarketFilterConfig` 和 semantic schema 中新增 `allow_trans_up_recovery_entries_when_benchmark_off`，并打通 compiler
- [x] 1.2 在 `signal_postprocess` 中只对 `TRANS_UP + TREND_LIGHT + provider_breakout_runtime` 放松 benchmark gate，其他路径保持不变

## 2. 验证

- [x] 2.1 focused unit tests 通过
  - `tests/unit/test_semantic_config_compiler.py`
  - `tests/unit/test_bridge_adapter_route_control.py`
- [x] 2.2 `2018-2022` 个股窗口 A/B 已完成
  - 基线：[exp_20260408_153714815_9a45](C:\Users\hzfzzzi\openclaw\backtest_V2_standalone\outputs\experiments\exp_20260408_153714815_9a45)
  - 放松门控：[exp_20260408_153823418_6ee2](C:\Users\hzfzzzi\openclaw\backtest_V2_standalone\outputs\experiments\exp_20260408_153823418_6ee2)
  - 结果：
    - `CAGR`: `0.97% -> 5.78%`
    - `Sharpe`: `0.1465 -> 0.3863`
    - `MaxDD`: `-33.49% -> -25.43%`
    - `TRANS_UP` 非零暴露率：`2.5% -> 90.0%`
    - `TRANS_UP` 平均暴露：`2.04% -> 73.02%`
    - `TRANS_UP` 选股日占比：`0.0% -> 16.25%`

## 3. 副作用检查

- [x] 3.1 `2023-2026` 个股窗口 A/B 已完成
  - 基线：[exp_20260408_153937473_2016](C:\Users\hzfzzzi\openclaw\backtest_V2_standalone\outputs\experiments\exp_20260408_153937473_2016)
  - 放松门控：[exp_20260408_154021600_4203](C:\Users\hzfzzzi\openclaw\backtest_V2_standalone\outputs\experiments\exp_20260408_154021600_4203)
  - 结果：
    - `CAGR`: `7.64% -> 9.36%`
    - `Sharpe`: `0.4915 -> 0.5639`
    - `MaxDD`: `-22.92% -> -23.17%`
    - `TRANS_UP` 非零暴露率：`11.11% -> 97.78%`
    - `TRANS_UP` 平均暴露：`10.36% -> 97.42%`
    - `TRANS_UP` 选股日占比：`6.67% -> 20.00%`
- [x] 3.2 本 change 当前结论为 `go`
  - 事实：
    - `2018-2022` 明显改善
    - `2023-2026` 也改善
    - `MaxDD` 仅在 `2023-2026` 略差，幅度很小
  - 判断：
    - 当前恢复态 benchmark gate 过硬，确实压制了 stock alpha 的恢复重建
    - 这条最小松绑值得进入下一轮组合级验证

## 4. 下一步

- [x] 4.1 在组合窗口 `2023-2026` 上完成组合级 replay A/B
  - 基线 replay：[exp_20260408_161102367_ada4](C:\Users\hzfzzzi\openclaw\backtest_V2_standalone\outputs\experiments\exp_20260408_161102367_ada4)
  - 放松门控 replay：[exp_20260408_161156425_d314](C:\Users\hzfzzzi\openclaw\backtest_V2_standalone\outputs\experiments\exp_20260408_161156425_d314)
  - 结果：
    - `CAGR`: `2.25% -> 3.00%`
    - `Sharpe`: `0.2279 -> 0.2755`
    - `MaxDD`: `-26.55% -> -26.66%`
    - `Calmar`: `0.0848 -> 0.1126`
    - `stock/ETF corr`: `0.6522 -> 0.6269`
    - `stock/ETF corr on stock-down days`: `0.6843 -> 0.6528`
- [x] 4.2 提升为当前主线默认值
  - 当前有效窗口基线登记为：[exp_20260408_162019474_2450](C:\Users\hzfzzzi\openclaw\backtest_V2_standalone\outputs\experiments\exp_20260408_162019474_2450)
  - 当前有效窗口对照为：[exp_20260408_162125178_21b6](C:\Users\hzfzzzi\openclaw\backtest_V2_standalone\outputs\experiments\exp_20260408_162125178_21b6)
  - 结果：
    - `CAGR`: `2.25% -> 3.00%`
    - `Sharpe`: `0.2279 -> 0.2755`
    - `MaxDD`: `-26.55% -> -26.66%`
    - `Calmar`: `0.0848 -> 0.1126`
    - `stock/ETF corr`: `0.6522 -> 0.6269`
    - `stock/ETF corr on stock-down days`: `0.6843 -> 0.6528`
  - 判断：
    - 在当前代码基线上，放松 `TRANS_UP` 恢复态门控对 stock alpha 和组合层都为正向
    - 因此将 `allow_trans_up_recovery_entries_when_benchmark_off` 提升为当前主线默认值
