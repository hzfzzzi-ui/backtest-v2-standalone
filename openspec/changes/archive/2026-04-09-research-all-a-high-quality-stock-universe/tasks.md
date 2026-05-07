## 1. Change 准备
- [x] 1.1 明确本研究是 L3，仅改股票池  
  DoD：proposal/design 完成；风险与边界清楚。

## 2. 运行两组实验
- [x] 2.1 运行基线 stock-only：`HS300_ZZ500 + PIT_DYNAMIC`  
  DoD：得到 `2023-2026` 窗口基线实验。
- [x] 2.2 运行实验组 stock-only：`ALL_A + min_avg_turnover_20d=2e8`  
  DoD：得到同窗口实验结果。

## 3. 结果分析
- [x] 3.1 对比窗口绩效  
  DoD：至少比较 `CAGR / Sharpe / MaxDD / trades`。
- [x] 3.2 对比风格重叠  
  DoD：比较交易标的与 `CSI800 / CSI1000` 的窗口重叠比例。

## 4. 结论
- [x] 4.1 形成 go / no-go 结论  
  结论：`ALL_A + min_avg_turnover_20d=2e8` 在 `2023-2026` stock-only 窗口下为 `no-go`。  
  基线：`exp_20260408_144924107_9b92`  
  - `CAGR = 7.64%`
  - `Sharpe = 0.4915`
  - `MaxDD = -22.92%`
  - `traded_symbols = 98`
  - `CSI800 overlap = 100.0%`
  - `CSI1000 overlap = 8.16%`

  实验组：`exp_20260408_145007240_1a01`
  - `CAGR = -2.40%`
  - `Sharpe = -0.0324`
  - `MaxDD = -27.57%`
  - `traded_symbols = 80`
  - `CSI800 overlap = 51.25%`
  - `CSI1000 overlap = 33.75%`

  判断：
  - 风格上，实验组确实显著降低了对 `CSI800` 的绑定，并提高了对 `CSI1000` 的暴露。
  - 但收益和风险调整收益大幅恶化。
  - 同时 `ALL_A` 当前在审计上属于 `CURRENT_SNAPSHOT` lineage，不如基线 `PIT_DYNAMIC` 可信。
  - 因此这条“直接放开到高质量全市场池”的方向目前不值得并入主线。
