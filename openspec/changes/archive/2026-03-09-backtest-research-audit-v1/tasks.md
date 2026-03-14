## 1. Research Audit Contract

- [x] 1.1 新增 `backend/core/audit/research_audit.py`，定义 `build_research_audit()`、五个 gate 输出骨架、`overall_status` 聚合规则与 `evidence_refs` 结构；DoD：模块能独立生成符合 spec 的 research audit 字典；验证：定向断言覆盖 `FAIL/WARN/UNKNOWN/PASS` 四种聚合结果；风险：新 schema 与现有 `audit.json` merge 口径冲突。
- [x] 1.2 实现 research evidence 收集与 `timing_alignment`、`universe_lineage` 两个纯证据 gate，复用 `stage_summary/stage_pipeline/run_meta.universe` 与 universe lineage policy；DoD：能稳定输出 `PIT_DYNAMIC/START_SNAPSHOT/CURRENT_SNAPSHOT/UNKNOWN` 四种 lineage mode 与对应状态；验证：用 `ALL_A`、`HS300_ZZ500`、`CUSTOM` 样例做定向断言；风险：现有元信息不足时容易把缺证据误判成 `PASS/WARN`。

## 2. Gate Evaluation

- [x] 2.1 实现 `execution_realism`，基于 `portfolio_trades.csv` 与成交涉及 `symbol/date` 的日线 bar 回查，统计停牌成交、缺 bar 成交、零成交量成交、零成交额成交、涨停买入、跌停卖出；DoD：gate 能输出 status、异常计数和占比；验证：构造 `FAIL/WARN/UNKNOWN/PASS` 四类样例或夹具覆盖阈值规则；风险：artifact stabilize 阶段追加数据回查可能带来性能或可用性波动。
- [x] 2.2 实现 `reproducibility` 与 `result_sanity`，复用 `manifest/config_snapshots/resolved_config_hash/perf/run_meta.counters/symbol_performance`，支持样本门槛与口径矛盾检测；DoD：两个 gate 能按 spec 产出 verdict 与最小证据摘要；验证：覆盖缺核心产物、配置快照不全、`trades=0` 但净值变动、极端 Sharpe/CAGR 等样例；风险：历史实验 schema 差异可能导致新规则误伤旧目录。

## 3. Artifact Integration

- [x] 3.1 在 `backend/api/endpoints/backtest_v2_artifacts.py` 的 `ensure_standard_artifacts()` 中接入 `research_audit` 构建与 `audit.json` merge，保留现有 execution audit 字段且 research audit 失败时不破坏旧写盘流程；DoD：新实验目录的 `audit.json` 同时包含 execution audit 与 `research_audit`，且异常时仍能落盘原有 execution audit；验证：对比新旧 `audit.json` 字段并做故障注入；风险：写盘顺序调整导致 `audit.json` 或 `manifest` 产物漂移。
- [x] 3.2 打通可选 `validation_audit_ref` 透传与 `research_audit.evidence_refs.validate_data` 写入，不改变现有 `/validate_data` 独立行为，也不复制 `validate_data.json` payload；DoD：提供 ref 时写入最小引用对象，未提供时为 `null`；验证：两条路径都能生成完整 `research_audit`；风险：`request_id/path` 口径在不同入口下不一致。

## 4. Verification

- [x] 4.1 补充 research audit 定向测试或夹具，覆盖 `overall_status` 聚合、四种 `universe_lineage` 模式、`execution_realism` 阈值、`result_sanity` 样本门槛，以及“不复制 run_meta/stage_summary/manifest payload” 约束；DoD：关键 contract 都有回归保护；验证：测试运行通过并能定位 gate 级失败；风险：测试夹具与真实 artifact 结构脱节。
- [x] 4.2 运行至少一个端到端实验并复核产物，确认未新增 metadata 文件，且 `run_meta.json`、`manifest.json`、`stage_summary.json`、`audit.json` 的引用关系与 `research_audit` verdict 稳定；DoD：形成一组可人工复核的实验产物样本；验证：检查实验目录文件与 `audit.json.research_audit` 内容符合 spec；风险：真实实验数据口径暴露此前未显式处理的边界情况。
