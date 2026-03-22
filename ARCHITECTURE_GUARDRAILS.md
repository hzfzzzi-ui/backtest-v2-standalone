# ARCHITECTURE_GUARDRAILS.md
# 架构宪法 v1（Architecture Constitution v1）

> 目标：彻底定死本回测系统的架构、协议、边界与变更流程，杜绝反复返工。
> 任何改代码（尤其是 AI 改代码）必须先阅读本文件并遵守“守门人流程”。

---

## 0) 守门人流程（每次改代码前必须执行）

在写任何代码前，必须输出一段 6 行以内的 Checklist，逐项确认：

1) 本次改动类别：P0协议 / 后端API / 前端展示 / 观测与报告 / 引擎逻辑 / 数据与特征 / Runner
2) 会触及哪些稳定接口（第2章）
3) 是否影响：标准产物协议 / rows schema / run_meta schema
4) 是否新增字段/文件；是否向后兼容
5) 是否发现冲突/不确定（若是，必须立即提问，最多 5 问，并给保守/激进两方案及影响）
6) 执行顺序：先写测试与 schema 校验，再改代码，再验收（文件存在、类型稳定、前端可消费）

若存在冲突/不确定：必须停下问用户，等待选择后再动手改。

---

## 1) 系统定位与非目标

### 定位
- A股日频研究与决策平台（非实盘下单系统）
- 第一优先级：可复现、可解释、可规模化实验（Runner）
- 结果逐步逼近可用：明确撮合与成本假设，但不追求交易所级细节

### 非目标
- 不做分钟级/高频撮合
- 不直接接券商下单（当前版本）
- 不允许为速度牺牲可复现性（run_meta/version 必须存在）

---

## 2) 稳定接口（绝对不能随意改动）

### 2.1 HTTP API（必须保持兼容，允许新增字段但不允许破坏）
- GET  /api/backtest_v2/validate_data
- POST /api/backtest_v2/experiment/run_async
- GET  /api/backtest_v2/jobs/{job_id}
- POST /api/backtest_v2/jobs/{job_id}/cancel

硬约束：
- `rows` 必须是严格 JSON（数值=number|null），严禁 PowerShell `@{...}` 字符串
- 严禁 NaN/Inf（必须清洗为 null）

### 2.2 标准产物协议（必须每次运行必出，缺一算失败）
对每个实验结果目录必须存在：
- manifest.json
- run_meta.json
- perf.json
- nav.csv
- funnel.csv
- reason_codes.csv
- config.json

可选增强产物：
- audit.json
- stage_summary.json
- input_config.json
- resolved_config.json
- compiled_plan.json
- portfolio_trades.csv
- portfolio_daily.csv
- symbol_performance.csv
- execution_lineage_ledger.csv

增强产物不得代替最小必出文件。

### 2.3 rows schema（必须稳定）
当前稳定的 row-shaped public payload 以 history rows 与 compare rows 为主，正式文档见：
- `docs/SCHEMA_rows.json.md`

硬约束：
- `exp_id`、`label`、`perf` 不得无声删除
- 数值字段必须保持 `number|null`
- compare rows 的 `nav` 序列必须保持 `[{date, nav}]` 结构

### 2.4 run_meta.json schema（唯一真相，必须稳定）
当前正式 schema 见：
- `docs/SCHEMA_run_meta.json.md`

硬约束：
- 顶层必须保持 `exp_id`、`tier`、`status`、`data`、`code`、`counters`、`missing_fields`
- canonical funnel counters 必须保持：
  `raw_signal`、`blocked`、`orders`、`skipped`、`closed_trades`
- `missing_fields` 必须记录协议补齐缺口，不能靠省略文件掩盖

---

## 3) 模块职责边界（禁止越界）

- 引擎层：策略决策/组合更新/风控/生成原始结果。禁止写前端展示结构。
- 报告层：从原始结果生成 perf/nav/回撤/集中度/结论。必须至少支持最小协议。
- API/Router 层：异步作业、参数校验、调用引擎+报告、落盘标准协议、返回稳定 schema。
  允许做“补齐协议”的最小计算（例如从 nav 计算 MDD），但禁止实现策略逻辑。
- 前端层：只消费 API 与落盘文件映射；可做展示级派生（如 drawdown 从 nav 计算）但不得改变口径。

---

## 4) 实验分级 Tier（硬规则）

默认规则（可配置但不得随意改口径）：
- T0: years<1 OR universe<50 OR trades<50
- T1: 1<=years<3 OR 50<=universe<300 OR 50<=trades<300
- T2: years>=3 AND universe>=300 AND trades>=300
- T3: years>=5 AND universe>=700 AND trades>=1000

约束：
- 前端必须展示 Tier
- T0/T1 禁止标为“最优结论”
- T2 才能进入 Candidate
- T3 才能进入鲁棒性/WF/成本压力测试

---

## 5) 可解释性与诊断（不可妥协）

每次运行必须能回答：
- 跑了什么（run_meta/pipeline/config）
- 为什么没交易（funnel + reason_code_counts）
- 模块是否生效（trigger counters）
- 结果是否可信（Tier + 分段/WF 若启用）

reason_code taxonomy 至少分层：
- Universe 过滤
- Signal 过滤
- Gate/Regime 过滤
- Execution 不可成交
- Risk/Exit 原因
- 资金/仓位约束

---

## 6) 变更规则（防返工）

若触及 2.2/2.3/2.4（协议/rows/meta）：
- 必须先更新 `docs/SCHEMA_rows.json.md`、`docs/SCHEMA_run_meta.json.md`、`docs/SCHEMA_manifest.json.md`
- 必须新增/更新 schema 校验测试
- 只允许向后兼容新增；禁止改名/删字段

禁止“无声破坏”：
- 不允许返回 NaN/Inf
- 不允许 rows schema 漂移
- 不允许只靠前端兜底掩盖后端破坏

冲突处理：
- 若需求与本宪法冲突，必须向用户提问并给两方案（保守/激进）等待选择。

---

## 7) 必须长期存在的文件与测试

- `ARCHITECTURE.md`
- `docs/SCHEMA_rows.json.md`
- `docs/SCHEMA_run_meta.json.md`
- `docs/SCHEMA_manifest.json.md`
- `docs/RUNBOOK_baseline_regression.md`
- `examples/experiment_contract_minimal/`
- `tests/integration/test_schema_and_artifacts.py`
