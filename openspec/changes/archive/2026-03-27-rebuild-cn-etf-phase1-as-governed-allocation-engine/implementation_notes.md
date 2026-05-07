## 实现结论

这轮实现把 `cn_etf_beta` 的正式 Phase 1 主线从“筛票型 beta sleeve”收口成了“受统一 Governor 预算约束的 ETF 配置引擎”。

当前正式入口为：

- `study_id`: `etf/cn_etf_first_wave_core`
- `source_entry_type`: `cn_etf_phase1_allocation_entry`
- `strategy_role`: `phase1_allocation_engine`
- `local_policy_mode`: `phase1_bucket_allocation`

正式资产池固定为：

- `510300.SH`
- `510500.SH`
- `510050.SH`
- `512100.SH`
- `512890.SH` 仅作 limited defense

## 关键改动

### 1. Contract 与 schema

更新了：

- [backend/core/config/etf_beta_contract.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/config/etf_beta_contract.py)
- [backend/api/backtest_v2/semantic_config_schema.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/backtest_v2/semantic_config_schema.py)

新增或收口了以下正式字段：

- `allocation_engine_mode`
- `bucket_policy_profile`
- `equity_core_bucket_by_state_5`
- `defense_tilt_bucket_by_state_5`
- `cash_buffer_bucket_by_state_5`
- `equity_core_template_weights`
- `equity_core_tilt_limits`
- `defense_asset_weights`
- `requested_budget`
- `applied_budget`
- `targets`
- `cash_weight`
- `defense_weight`

### 2. Provider 主路径

更新了：

- [backend/core/engine_vector/cn_etf_beta_signal_provider.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_vector/cn_etf_beta_signal_provider.py)

正式主路径现在按：

1. Governor 输出 sleeve 预算
2. Phase 1 三桶分配
3. 桶内低自由度配置
4. 写回正式 diagnostics / reason codes

旧 `dual_momentum` / `broad_based_rotation_template_a` 等研究线仍保留兼容分支，但不再作为默认语义。

### 3. 审计与 formal alignment

更新了：

- [backend/core/audit/research_audit.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/audit/research_audit.py)

现在 `run_meta / audit` 会显式输出：

- `formal_alignment_status`
- `formal_mainline_compatible`
- `governor_boundary`
- `local_policy_decision`
- `requested_budget`
- `applied_budget`
- `targets`
- `cash_weight`
- `defense_weight`

### 4. 正式 study 入口

重写了：

- [research/studies/etf/cn_etf_first_wave_core.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_etf_first_wave_core.study.yaml)

这条 study 现在只表达正式 Phase 1 主线，不再混入研究分支资产或旧筛票语义。

## 验证

已通过：

```bash
pytest tests/unit/test_etf_beta_contract.py tests/unit/test_research_audit_contract.py tests/unit/test_semantic_config_compiler.py tests/unit/test_cn_etf_beta_signal_provider.py -q
```

结果：

- `112 passed`

已通过：

```bash
python -m backend.cli study_run etf/cn_etf_first_wave_core --dry-run
```

正式实验在容器内通过：

```bash
docker exec backtest-v2-standalone python -m backend.cli study_run etf/cn_etf_first_wave_core
```

产物：

- [exp_20260327_062418786_3bc7](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260327_062418786_3bc7)

补充说明：

- 本机直接执行正式 `study_run` 时，因宿主进程无法解析 `pams-postgres` 而失败。
- 这不是策略实现问题，是本机 Python 进程不在容器网络中。
- 容器内执行已通过，因此正式实验验证以容器结果为准。

OpenSpec 校验已通过：

```bash
openspec validate rebuild-cn-etf-phase1-as-governed-allocation-engine --type change --strict
```

## 当前结果与风险

这轮 change 的目标是“重建正式口径”，不是优化收益。

当前最小正式实验结果：

- `orders = 0`
- `closed_trades = 0`
- `CAGR = 0.0`

这说明：

- Formal Phase 1 contract、provider、audit、study 入口已经打通
- 但正式口径下的 ETF 配置引擎还没有形成有效交易结果

因此下一步研究应继续围绕：

- 正式配置语义
- 正式资产池下的预算承接
- 为什么 formal mainline 仍然没有落地成交

而不是回退到 `159915 / 588000 / 511010` 这类 research-only 资产。

## 回退

如果需要回退这轮实现，优先撤回：

- [backend/core/config/etf_beta_contract.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/config/etf_beta_contract.py)
- [backend/api/backtest_v2/semantic_config_schema.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/backtest_v2/semantic_config_schema.py)
- [backend/core/engine_vector/cn_etf_beta_signal_provider.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_vector/cn_etf_beta_signal_provider.py)
- [backend/core/audit/research_audit.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/audit/research_audit.py)
- [research/studies/etf/cn_etf_first_wave_core.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_etf_first_wave_core.study.yaml)
- [tests/unit/test_etf_beta_contract.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/tests/unit/test_etf_beta_contract.py)
- [tests/unit/test_research_audit_contract.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/tests/unit/test_research_audit_contract.py)
- [tests/unit/test_semantic_config_compiler.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/tests/unit/test_semantic_config_compiler.py)
- [tests/unit/test_cn_etf_beta_signal_provider.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/tests/unit/test_cn_etf_beta_signal_provider.py)
