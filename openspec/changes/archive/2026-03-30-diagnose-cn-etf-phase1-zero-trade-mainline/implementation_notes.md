## 概要

这轮实现没有修改正式 ETF Phase 1 的交易逻辑，只新增了后端真相化诊断链路，用来定位为什么 `cn_etf_first_wave_core` 在正式窗口内出现 `orders = 0 / closed_trades = 0 / CAGR = 0`。

核心新增物：

- 诊断写入器：[backend/research/cn_etf_phase1_zero_trade_diagnostics.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/research/cn_etf_phase1_zero_trade_diagnostics.py)
- study runner 侧边诊断挂接：[backend/research/study_runner.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/research/study_runner.py)
- 正式 study 诊断模式入口：[research/studies/etf/cn_etf_first_wave_core.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_etf_first_wave_core.study.yaml)
- `research_audit` 扩展指标：[backend/core/audit/research_audit.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/audit/research_audit.py)

## 影响模块

- `backend/research`
  - 新增正式 Phase 1 诊断产物生成
  - 五层对照实验：`buy_and_hold / filter_only / allocation_only / filter_plus_allocation / full_strategy`
- `backend/core/audit`
  - 为 ETF sleeve 增加仓位利用率、现金/风险/防守占比、信号数、未成交数等部署指标
- `research/studies/etf`
  - 正式 study 增加 `diagnostic_mode: cn_etf_phase1_zero_trade_mainline`
- `tests/unit`
  - 新增诊断模块单测
  - 扩展 ETF audit contract 回归断言

## 主要产物

正式诊断实验：

- [exp_20260327_072101765_060a](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260327_072101765_060a)

诊断产物目录：

- [outputs/ops/diagnose_cn_etf_phase1_zero_trade_mainline/exp_20260327_072101765_060a](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/diagnose_cn_etf_phase1_zero_trade_mainline/exp_20260327_072101765_060a)

关键文件：

- [rebalance_day_summary.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/diagnose_cn_etf_phase1_zero_trade_mainline/exp_20260327_072101765_060a/rebalance_day_summary.csv)
- [ranking_detail.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/diagnose_cn_etf_phase1_zero_trade_mainline/exp_20260327_072101765_060a/ranking_detail.csv)
- [effective_parameters.json](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/diagnose_cn_etf_phase1_zero_trade_mainline/exp_20260327_072101765_060a/effective_parameters.json)
- [position_utilization.json](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/diagnose_cn_etf_phase1_zero_trade_mainline/exp_20260327_072101765_060a/position_utilization.json)
- [lineage_samples.json](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/diagnose_cn_etf_phase1_zero_trade_mainline/exp_20260327_072101765_060a/lineage_samples.json)
- [layer_compare.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/diagnose_cn_etf_phase1_zero_trade_mainline/exp_20260327_072101765_060a/layer_compare.csv)
- [rootcause_summary.json](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/diagnose_cn_etf_phase1_zero_trade_mainline/exp_20260327_072101765_060a/rootcause_summary.json)

## 诊断结论

这轮已经把零交易主因定位清楚：

- 正式窗口内 Governor 每天都把 `total_exposure_cap` 压到 `0`
- ETF `requested_budget` 被正式 contract 直接绑定为 Governor sleeve budget，因此预算也长期为 `0`
- provider 在 `slot_cap <= 0` 时直接短路，候选和 eligible 虽然存在，但不会生成 targets / orders / trades
- 当前 `absolute_filter_mode=none`、`fallback_mode=none`，所以零交易不是由绝对过滤、fallback 或交易成本造成
- 五层对照里 `buy_and_hold / filter_only` 仍能跑出正收益，而 `allocation_only / full_strategy` 为 0，问题集中在预算承接链，而不是数据可用性

## 验证命令

```powershell
pytest tests/unit/test_cn_etf_phase1_zero_trade_diagnostics.py tests/unit/test_research_audit_contract.py tests/unit/test_etf_beta_contract.py tests/unit/test_semantic_config_compiler.py tests/unit/test_cn_etf_beta_signal_provider.py -q
python -m py_compile backend/research/cn_etf_phase1_zero_trade_diagnostics.py backend/research/study_runner.py backend/core/audit/research_audit.py
python -m backend.cli study_run etf/cn_etf_first_wave_core --dry-run
docker exec backtest-v2-standalone python -m backend.cli study_run etf/cn_etf_first_wave_core
openspec validate diagnose-cn-etf-phase1-zero-trade-mainline --type change --strict
```

## 风险

- 诊断层通过 `resolved_config.config_json.data_source` 直接取正式 ETF 日线表；如果后续正式 config 包装层再改结构，这里需要同步更新解包逻辑。
- 五层对照是离线诊断，不应被误用成正式交易逻辑。
- `research_audit` 指标是 additive 扩展；如果下游有人硬编码 ETF deployment metrics 字段白名单，需要同步检查兼容性。

## 回退方案

如果要回退这轮改动，撤回以下文件即可：

- [backend/research/cn_etf_phase1_zero_trade_diagnostics.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/research/cn_etf_phase1_zero_trade_diagnostics.py)
- [backend/research/study_runner.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/research/study_runner.py)
- [backend/core/audit/research_audit.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/audit/research_audit.py)
- [research/studies/etf/cn_etf_first_wave_core.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_etf_first_wave_core.study.yaml)
- [tests/unit/test_cn_etf_phase1_zero_trade_diagnostics.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/tests/unit/test_cn_etf_phase1_zero_trade_diagnostics.py)
- [tests/unit/test_research_audit_contract.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/tests/unit/test_research_audit_contract.py)

产物目录 `outputs/ops/diagnose_cn_etf_phase1_zero_trade_mainline/*` 属于运行产物，按需删除即可，不影响源码回退。
