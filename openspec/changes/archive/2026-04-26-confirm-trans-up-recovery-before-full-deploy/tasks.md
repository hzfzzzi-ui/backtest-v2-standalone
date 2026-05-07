## 1. Spec and implementation

- [x] 1.1 新增 `trans_up_recovery_confirmed_top_up_scale_when_benchmark_on`
- [x] 1.2 在 `TRANS_UP + benchmark_off` 下输出 staged entry metadata
- [x] 1.3 在 `TRANS_UP + benchmark_on` 下对 staged holdings 输出一次性 confirmed top-up metadata
- [x] 1.4 放行 confirmed top-up 的 existing holding planning
- [x] 1.5 补 focused unit tests

focused tests:

- `pytest tests/unit/test_semantic_config_compiler.py tests/unit/test_bridge_adapter_route_control.py tests/unit/test_multi_alpha_order_planning.py -q`
- `127 passed`

## 2. A/B

- [x] 2.1 用旧主线 carrier 跑 `2012-2026`
- [x] 2.2 用旧主线 carrier 跑 `2018-2026`
- [x] 2.3 回填结论，判断是否 go

实验：

- `2012-2026 false`: `exp_20260409_080602224_ad14`
- `2012-2026 true`: `exp_20260409_081505587_429a`
- `2012-2026 staged 0.5 + confirmed 0.5`: `exp_20260409_082408608_0ea3`
- `2018-2026 false`: `exp_20260409_083001297_5bbb`
- `2018-2026 true`: `exp_20260409_083533377_f62c`
- `2018-2026 staged 0.5 + confirmed 0.5`: `exp_20260409_084101552_c69b`

结果：

- `2012-2026`
  - `false`: `CAGR 13.30%`, `Sharpe 0.4908`, `MaxDD -31.39%`, `Calmar 0.4239`
  - `true`: `CAGR 12.42%`, `Sharpe 0.4676`, `MaxDD -34.14%`, `Calmar 0.3639`
  - `staged`: `CAGR 12.16%`, `Sharpe 0.4614`, `MaxDD -30.23%`, `Calmar 0.4024`
- `2018-2026`
  - `false`: `CAGR 5.68%`, `Sharpe 0.5449`, `MaxDD -19.15%`, `Calmar 0.2967`
  - `true`: `CAGR 7.18%`, `Sharpe 0.6645`, `MaxDD -19.82%`, `Calmar 0.3622`
  - `staged`: `CAGR 5.84%`, `Sharpe 0.5793`, `MaxDD -19.73%`, `Calmar 0.2958`

结论：

- `0.5 + 0.5` 的 staged deploy 只部分缓和了 `2012-2026` 的全样本伤害
- 但它没有保住 `2018-2026` 相对 `true` 的主要收益改善
- 因此当前这条最小 staged/confirmed 方案判定为 `no-go`
- 不建议提升为主线默认值
