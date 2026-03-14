## Why

当前系统已经有 `audit.json`、`stage_summary.json`、`run_meta.json`、`validate_data.json` 等审计相关产物，但它们分别回答的是执行轨迹、源数据质量和实验元信息，无法统一回答“这次回测结果是否可信”。在继续推进策略研究、候选晋级和结果对比前，需要一个实验级的 research audit 收口层，把已有证据整理成统一 verdict，而不是继续依赖人工拼接判断。

## What Changes

- 在现有 `audit.json` 中新增 `research_audit` 子树，统一输出 `overall_status`、五个 gate 状态和证据引用，不新增新的元数据文件。
- 新增共享的 experiment research audit 构建模块，复用 `run_meta.json`、`manifest.json`、`stage_summary.json`、`perf.json`、`portfolio_trades.csv`、`symbol_performance.csv`，并可选引用 `validate_data.json`。
- 为 `universe_lineage` 定义四种标准模式：`PIT_DYNAMIC`、`START_SNAPSHOT`、`CURRENT_SNAPSHOT`、`UNKNOWN`，并将当前 runtime universe 模式映射到统一审计口径。
- 增加最小化的 `execution_realism` 实验级检查，按成交记录与对应日线 bar 判断停牌成交、缺 bar 成交、零成交量成交、涨停买入、跌停卖出等失真风险。
- 保留现有 execution audit trail、`stage_summary.json`、`manifest.json`、`run_meta.json` 的职责和字段，不复制已有内容，只在 `research_audit.evidence_refs` 中引用。
- 明确 v1 不做完整未来函数检测、不重写旧 `AuditCollector` 体系、不强制把 `validate_data` 变成实验前置步骤、不要求大规模修改报表系统。

## Capabilities

### New Capabilities
- `backtest-research-audit`: 为每次实验生成统一的 research audit verdict，评估 timing、股票池来源、成交现实性、可复现性和结果异常性。

### Modified Capabilities
- `backtest-audit`: 在不破坏现有 execution audit trail 的前提下，扩展 `audit.json` 契约，使其可承载 `research_audit` 子树与证据引用。

## Impact

- 影响代码：
  - `backend/core/audit/`
  - `backend/api/endpoints/backtest_v2_artifacts.py`
  - `backend/core/engine_compat/foundation_shell.py`
  - `backend/api/endpoints/backtest_v2.py`
  - `backend/core/tools/experiment_runner.py`
  - `backend/core/report/report_generator.py`（v1 可保持不改，或仅追加只读展示）
- 影响产物：
  - `audit.json`
  - `run_meta.json`、`stage_summary.json`、`manifest.json` 的引用关系
  - 可选引用 `validate_data.json`
- 影响系统：
  - 实验可信度判定
  - 研究候选晋级前的审计门槛
  - 历史实验与新实验的 audit contract 区分
