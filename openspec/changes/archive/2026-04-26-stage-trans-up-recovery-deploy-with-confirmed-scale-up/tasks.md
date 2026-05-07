## 1. 合同与配置链路
- [x] 1.1 扩展 `market_filter` 增加 `trans_up_recovery_entry_scale_when_benchmark_off`
DoD: schema、runtime dataclass、runner compile 均可透传；验证: focused unit tests；风险: 默认值必须保持 `1.0`，不能引入默认行为漂移。
- [x] 1.2 新增 `trans-up-staged-recovery-deploy` spec 并明确 diagnostics 合同
DoD: proposal/design/specs/tasks 齐全；验证: `openspec status` apply-ready；风险: 不得把 pyramiding 混入本次 change。

## 2. 最小实现
- [x] 2.1 在 `TRANS_UP + benchmark_off` 放行路径上对买入信号注入 `order_value_scale` 缩放
DoD: 只影响恢复态放行买单；验证: route-control test；风险: 不能影响其它状态。
- [x] 2.2 写出 staged deploy diagnostics
DoD: `trans_up_recovery_entry_scale_applied` 和 `trans_up_recovery_scaled_entry_count` 可观测；验证: route-control test；风险: 不新增主产物 schema。

## 3. 最小验证
- [x] 3.1 跑 focused unit tests
DoD: 相关测试通过；验证: `pytest tests/unit/test_semantic_config_compiler.py tests/unit/test_bridge_adapter_route_control.py -q`；结果: `95 passed`；风险: 未引入默认行为漂移。
- [x] 3.2 跑旧主线 carrier 的最小 A/B
DoD: 比较 `2012-2026` 与 `2018-2026`，缩放值固定为 `0.3`；验证: 新实验 `perf.json`；风险: 不混入其它变量。

## 4. 结果结论
- [x] 4.1 `2012-2026` 全样本 A/B 已完成
基线 `scale=1.0`: [exp_20260409_072309682_2993](C:\Users\hzfzzzi\openclaw\backtest_V2_standalone\outputs\experiments\exp_20260409_072309682_2993)
候选 `scale=0.3`: [exp_20260409_073117974_8c03](C:\Users\hzfzzzi\openclaw\backtest_V2_standalone\outputs\experiments\exp_20260409_073117974_8c03)
结果:
- `CAGR`: `12.42% -> 11.99%`
- `Sharpe`: `0.4676 -> 0.4563`
- `MaxDD`: `-34.14% -> -32.69%`
- `Calmar`: `0.3639 -> 0.3667`
判断: 收益与 Sharpe 略差，回撤略好，Calmar 只有极小改善，不足以支持主线推进。

- [x] 4.2 `2018-2026` 后半段 A/B 已完成
基线 `scale=1.0`: [exp_20260409_073652226_86b2](C:\Users\hzfzzzi\openclaw\backtest_V2_standalone\outputs\experiments\exp_20260409_073652226_86b2)
候选 `scale=0.3`: [exp_20260409_074207058_20da](C:\Users\hzfzzzi\openclaw\backtest_V2_standalone\outputs\experiments\exp_20260409_074207058_20da)
结果:
- `CAGR`: `7.18% -> 5.39%`
- `Sharpe`: `0.6645 -> 0.5498`
- `MaxDD`: `-19.82% -> -18.30%`
- `Calmar`: `0.3622 -> 0.2945`
判断: 后半段也没有保住原来的收益改善，说明 `0.3` 的统一轻仓地板过强。

- [x] 4.3 change 结论
结论: 当前最小 staged deploy 方案 `no-go`。
原因:
- 它确实降低了恢复态仓位冲击和部分回撤。
- 但没有在 `2018-2026` 保住恢复态松绑带来的收益改善。
- 因此不建议把 `trans_up_recovery_entry_scale_when_benchmark_off=0.3` 推进为主线默认值。

后续建议:
- 如果继续研究，只能做更温和的条件化方案，例如更高 scale 或“确认后加仓”，而不是统一 `0.3` 缩放。
