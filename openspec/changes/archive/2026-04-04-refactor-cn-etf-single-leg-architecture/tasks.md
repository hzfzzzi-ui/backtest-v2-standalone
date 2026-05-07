## 1. Contract 分层

- [x] 1.1 新建 `backend/core/config/etf_beta/` 模块骨架与 facade 导出策略；DoD: `defaults.py`、`normalization.py`、`exposure_semantics.py`、`summary.py` 和 `__init__.py` 路径确定，`etf_beta_contract.py` 目标职责收口为 facade；验证: 代码搜索可见新模块边界，`pytest tests/unit/test_etf_beta_contract.py -q`；风险: 导入循环与公开符号遗漏。
- [x] 1.2 迁移 ETF 默认值与归一化逻辑；DoD: 默认 contract、常量和 normalize 路径由子模块提供，旧文件不再直接承载这部分实现；验证: `pytest tests/unit/test_etf_beta_contract.py -q`；风险: formal 与 legacy 路径的默认值兼容性回归。
- [x] 1.3 迁移 ETF 暴露语义与 phase1 summary 构建；DoD: `resolve_*exposure_semantics` 与 `build_*summary` 由专属模块实现，旧文件仅转发；验证: `pytest tests/unit/test_etf_beta_contract.py tests/unit/test_artifacts_finalize_regime_meta.py -q`；风险: summary 字段兼容性与 target/deployment 解释漂移。

## 2. Provider 分层

- [x] 2.1 新建 `backend/core/engine_vector/etf_beta/` 模块骨架与 provider state/config owner；DoD: `provider_config.py`、`provider_state.py`、`candidate_pool.py`、`selection.py`、`execution_paths.py`、`diagnostics.py` 路径确定，公共状态 owner 可承接现有 provider 字段；验证: `pytest tests/unit/test_cn_etf_beta_signal_provider.py -q`；风险: 大量隐式 `self` 状态迁移时漏字段。
- [x] 2.2 迁移配置翻译、候选池和选择逻辑；DoD: provider facade 不再直接承载 governed config 翻译和 target selection 主实现；验证: `pytest tests/unit/test_cn_etf_beta_signal_provider.py tests/unit/test_cn_etf_catalog.py -q`；风险: ETF 池解析与 phase1 候选排序回归。
- [x] 2.3 迁移 monthly rebalance、`TRANS_UP` redeploy 与诊断聚合；DoD: 执行路径和 diagnostics 各有独立 owner，旧 provider 文件主要做调度；验证: `pytest tests/unit/test_cn_etf_beta_signal_provider.py tests/unit/test_cn_etf_phase1_zero_trade_diagnostics.py -q`；风险: 执行路径与 reason code 证据脱节。

## 3. Accounting 与 Artifact 收口

- [x] 3.1 新建 ETF 专属 accounting 边界并接入 `daily_accounting.py`；DoD: ETF actual exposure、gap 拆分、formal/research view 由 `etf_beta_accounting.py` 或等价模块输出，`daily_accounting.py` 只保留编排；验证: `pytest tests/unit/test_bridge_adapter_accounting.py tests/unit/test_stage_pipeline_contracts.py -q`；风险: 日级口径或 formal/research view 漂移。
- [x] 3.2 收口 ETF summary 固化边界；DoD: `artifacts_finalize.py` 仅消费稳定 summary API，不再拥有 ETF 细节拼装真相；验证: `pytest tests/unit/test_artifacts_finalize_regime_meta.py tests/unit/test_backtest_v2_artifacts.py -q`；风险: run_meta / governed_snapshot 字段兼容性回归。

## 4. 兼容性与回归验证

- [x] 4.1 保持 ETF 单腿公开入口兼容；DoD: 旧 import 路径、公开函数名和 `CNETFBetaSignalProvider` 保持可用；验证: `pytest tests/unit/test_api_compat_boundaries.py tests/unit/test_provider_boundary_hygiene.py -q`；风险: facade 过薄但漏掉旧调用点。
- [x] 4.2 运行 ETF 单腿主链回归；DoD: ETF contract、provider、accounting、artifact 相关主测通过，且本次 change 未触及 combo/front-end 主链；验证: `pytest tests/unit/test_etf_beta_contract.py tests/unit/test_cn_etf_beta_signal_provider.py tests/unit/test_bridge_adapter_accounting.py tests/unit/test_artifacts_finalize_regime_meta.py tests/unit/test_backtest_v2_artifacts.py -q`；风险: 局部测试通过但跨层集成回归未暴露。
