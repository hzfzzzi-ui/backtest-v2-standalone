## Why

`cn_etf` 数据链、研究 preset 和 `cn_etf_beta` Phase 1 contract 已经存在，但真正接到研究/运行主线后仍有 truth 漂移：ETF 运行会继承股票基准 `000300.SH`，部分 audit/governor 摘要也会退化成 `cn_a_equity` 语义。现在需要把 ETF 主线的 provider/read path、运行时真相和最小 smoke 证据链收口，避免后续继续在“看起来能跑、实际说错话”的状态上叠功能。

## What Changes

- 修正 `asset_scope=cn_etf` 运行时的基准解析与 read path 真相，避免默认回落到股票 `000300.SH` 语义。
- 修正 `run_meta / audit / governed snapshot / research audit` 中与 `cn_etf_beta` 相关的 `asset_scope`、`daily_table`、`benchmark_source`、ETF sleeve 选择摘要，使其与 ETF 真值表保持一致。
- 为 `cn_etf_beta` 主线接入补充一条最小 smoke run 路径，固定使用现有 ETF preset 验证 provider/read path 和产物真相，不以是否产生交易为通过条件。

## Capabilities

### New Capabilities
- 无

### Modified Capabilities
- `cn-etf-beta-sleeve`: 要求 ETF beta sleeve 运行时真值与 ETF 真值表、Phase 1 范围和 sleeve 摘要保持一致。
- `cn-etf-research-entry`: 要求 `cn_etf` 研究入口在进入主线时显式暴露 ETF 基准来源、日线表来源和覆盖窗口真相。
- `cn-a-portfolio-governor`: 要求 Governor 最新快照在 `cn_etf` 运行中保留 ETF 资产语义，而不是退化为股票 alpha 语义。
- `backtest-research-audit`: 要求研究审计按 ETF 主线解释 `asset_scope`、entry type 和 sleeve 证据链，不再混入股票 PIT 口径。

## Impact

- 影响代码：
  - `backend/core/tools/data_bundle_builder.py`
  - `backend/core/api/backtest_v2/artifacts_finalize.py`
  - `backend/core/audit/research_audit.py`
  - `backend/core/stage_pipeline/adapters/result_bridge.py`
  - 相关 ETF runtime / smoke 测试
- 影响产物：
  - `run_config.json`
  - `run_meta.json`
  - `audit.json`
  - smoke run 对比摘要
- 不涉及数据库 schema 变更，不扩首波 ETF 目录范围。
