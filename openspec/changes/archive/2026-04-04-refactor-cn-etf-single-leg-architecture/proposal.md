## Why

当前 ETF 单腿主链把合同真相、执行实现、日级审计和 summary 固化长期混在少数超大文件里，导致定位瓶颈、验证 target/actual 偏差来源、局部替换实现都非常困难。当前结果已经证明 ETF 单腿存在明显的低暴露问题，因此需要先把架构拆清，再继续分析和优化行为。

## What Changes

- 将 ETF 单腿从“超大合同文件 + 超大 provider 文件 + 分散审计拼装”重构为清晰的分层结构。
- 为 ETF 单腿建立稳定 facade，保留现有调用入口，同时把内部实现拆分为规则/配置、执行、审计、summary 四类模块。
- 将 `etf_beta_contract.py` 拆分为默认值、归一化、暴露语义、summary builder 等职责单一模块。
- 将 `cn_etf_beta_signal_provider.py` 拆分为 provider 配置装配、候选池/排序、执行路径、诊断聚合等模块。
- 将 ETF 的 actual exposure 解释与 formal/research view 组装从通用 accounting 热点中收口为 ETF 专属边界。
- 保持 ETF 单腿对外契约、研究入口和 artifact 字段兼容，不把本次重构扩展成 stock+ETF combo、前端或研究语义改造。

## Capabilities

### New Capabilities
- `cn-etf-single-leg-architecture`: 约束 ETF 单腿在不改 combo 和前端的前提下，按规则、执行、审计、summary 分层重构，并保留稳定 facade 入口。

### Modified Capabilities
- 无

## Impact

- 受影响代码：
  - `backend/core/config/etf_beta_contract.py`
  - `backend/core/engine_vector/cn_etf_beta_signal_provider.py`
  - `backend/core/stage_pipeline/adapters/daily_accounting.py`
  - `backend/api/backtest_v2/artifacts_finalize.py`
- 受影响系统：
  - ETF 单腿 formal/research contract
  - ETF 单腿 provider 执行路径
  - ETF 单腿审计与 run_meta 固化
- 不在本次范围：
  - `cn_stock_etf_unified_runtime_service.py`
  - stock+ETF 联跑语义
  - 前端加载链路
