# Qlib Q1/Q2/Q3/Q5/Q6 深入借鉴分析

更新时间：2026-05-02

## 结论

这五项不应作为“引入 Qlib”的理由，而应拆成五个本项目本地能力：

1. 安全特征表达式子集
2. 数据视图契约
3. 拟合窗口纪律
4. 产物记录模板
5. 执行边界对照

短期优先级建议：

`Q2 数据视图契约` > `Q3 拟合窗口纪律` > `Q5 产物记录模板` > `Q1 安全特征表达式子集` > `Q6 执行边界对照`

原因是：Q2/Q3/Q5 能先增强可信与可审计，不直接改变收益口径；Q1 和 Q6 一旦进入实现，容易触碰信号时点、成交时点和主回测口径，应按 L3 管控。

## 分析基准

本分析基于 Qlib `microsoft/qlib` main 分支浅克隆：

- commit：`d5379c520f66a39953bad76234a7019a72796fd0`
- commit date：`2026-04-22T15:08:01+08:00`
- subject：`docs: replace broken RD-Agent demo links in README (#2150)`

参考的 Qlib 模块：

- `qlib/data/ops.py`
- `qlib/data/dataset/handler.py`
- `qlib/data/dataset/__init__.py`
- `qlib/data/dataset/processor.py`
- `qlib/workflow/record_temp.py`
- `qlib/workflow/recorder.py`
- `qlib/backtest/exchange.py`
- `qlib/backtest/executor.py`
- `qlib/backtest/decision.py`
- `qlib/strategy/base.py`

## Q1：表达式化特征系统

### Qlib 中值得借鉴的点

Qlib 将特征定义抽象为表达式和算子，例如：

- 字段：`$close`、`$volume`
- 引用：`Ref($close, 1)`
- 滚动：`Mean($close, 20)`
- 组合：`Ref($close, -2) / Ref($close, -1) - 1`

其中最值得借鉴的不是具体实现，而是三点：

1. 特征定义可以从脚本中抽离成可审计表达式。
2. 算子可以声明窗口依赖，例如最长回看窗口、是否需要未来窗口。
3. 表达式可以统一编译、缓存、审计、复用。

### 本项目应借鉴什么

本项目应设计自己的“安全特征表达式子集”，不复用 Qlib 表达式引擎。

建议最小子集：

| 类型 | 建议算子 | 说明 |
| --- | --- | --- |
| 字段 | `Field(close)`、`Field(volume)`、`Field(amount)` | 只能映射到本地 canonical PIT 字段 |
| 滞后 | `Lag(close, 1)` | 正数只表示向过去取值，禁止 Qlib 式正负歧义 |
| 滚动 | `RollingMean(close, 20)`、`RollingStd(close, 20)`、`RollingMax(close, 60)` | 必须声明 warmup 和 min_periods |
| 横截面 | `RankCS(x)`、`ZScoreCS(x)` | 必须限定同一交易日、同一可交易池 |
| 基础运算 | `Add/Sub/Mul/Div/Clip/Where` | 不允许任意 Python 表达式 |
| 可用性 | `IsAvailable(x)` | 进入 feature availability audit |

每个特征必须生成以下元数据：

```json
{
  "feature_id": "ma20_slope",
  "expression": "Div(Field(close), RollingMean(Field(close), 20)) - 1",
  "asset_scope": "cn_a_equity",
  "clock": "POST_CLOSE",
  "max_lookback_bars": 20,
  "max_forward_bars": 0,
  "pit_required": true,
  "warmup_policy": "drop_until_ready",
  "null_policy": "propagate",
  "allowed_in_runtime": true
}
```

### 本项目不应借鉴什么

- 不借鉴 Qlib `Ref` 的正负方向语义。Qlib 中 `N < 0` 表示未来数据，这在本项目 runtime feature 中必须禁止。
- 不允许 runtime feature 使用 forward return label。
- 不允许表达式引擎支持任意 eval 或任意 Python 函数。
- 不借鉴 Qlib `Rolling(..., 0)` 的 expanding 语义作为正式口径。
- 不把 `Alpha158 / Alpha360` 直接变成本项目正式特征集。

### 落地位置建议

先只做 spec，不实现：

- `docs/01_系统接口模块定义/共享层/安全特征表达式接口.md`

未来如果实现，建议放：

- `backend/core/features/expression_ast.py`
- `backend/core/features/expression_compiler.py`
- `backend/core/features/feature_audit.py`

### 验收门槛

- `max_forward_bars > 0` 的表达式不得进入 runtime signal。
- `clock=POST_CLOSE` 的表达式最多只能看到当前交易日收盘后数据，并只能驱动下一交易日执行。
- 每个表达式必须能输出依赖字段、回看窗口、未来窗口、PIT 表依赖。
- 必须有未来函数单测。

## Q2：DataHandler / Dataset 分层

### Qlib 中值得借鉴的点

Qlib 的 `DataHandlerLP` 明确区分三类数据：

- `DK_R`：raw data
- `DK_I`：infer data
- `DK_L`：learn data

`DatasetH` 再用 segments 描述 train、valid、test 等时间切片。

这个设计的价值是：数据处理视图和时间切片是两件事，不混在一起。

### 本项目当前已有基础

本项目已有：

- `DataBundle.raw_history`
- `DataBundle.signal_history`
- `DataBundleView.raw_history_view()`
- `DataBundleView.signal_history_view()`
- `DataBundleView.current_raw_frame()`
- `DataBundleView.current_signal_frame()`

并且 `DataBundleView` 会按 `trading_day` 切片并返回 copy，已经比 Qlib 的可变 DataFrame 更适合当前审计要求。

### 本项目应借鉴什么

应把现有隐含结构正式化为“数据视图契约”：

| 本项目视图 | 类似 Qlib | 用途 | 是否可进 runtime |
| --- | --- | --- | --- |
| `raw_view` | `DK_R` | 原始 canonical 数据，带 PIT 审计 | 可读，不直接产信号 |
| `signal_view` | `DK_I` | runtime 可见特征视图 | 可以 |
| `learn_view` | `DK_L` | 标签、训练、拟合专用视图 | 不可以 |
| `execution_view` | 无直接等价 | 价格、涨跌停、停牌、lot、费用 | 可以，仅执行层 |
| `audit_view` | 无直接等价 | 数据缺口、降级、可用性、lineage | 可读，不驱动交易 |

时间段也应正式化：

| 本项目窗口 | 用途 |
| --- | --- |
| `2016-2026` | 主开发窗口 |
| `2012-2017` | 硬门槛窗口 |
| `2012-2026` | 全周期审计窗口 |

这比直接套用 train/valid/test 更符合当前项目纪律。

### 本项目不应借鉴什么

- 不把 label processor 放进 runtime data view。
- 不为了省内存让 processor 原地修改正式 DataBundle。
- 不把 Qlib 的 `DatasetH.prepare(data_key=...)` 直接复制为运行接口；本项目需要更硬的视图权限。
- 不允许前端或报告层重新构建 learn/infer 视图。

### 落地位置建议

先补文档和测试，不改运行行为：

- 文档：`docs/01_系统接口模块定义/共享层/数据视图契约.md`
- 测试：扩展 `tests/unit/test_stage_pipeline_contracts.py`

未来代码上可加：

- `DataBundle.learn_history`，仅 research/sandbox 可用
- `DataBundle.execution_history`，执行层专用
- `DataBundleAudit`，统一数据 lineage 与 missing policy

### 验收门槛

- runtime stage handler 默认只能拿到 `signal_view`、`execution_view`、`audit_view`。
- `learn_view` 在 stage pipeline 中必须不可访问。
- `DataBundleView` 必须继续隐藏未来交易日。
- 任何 view 都必须声明 `clock` 和 `as_of_date`。

## Q3：Processor fit 窗口纪律

### Qlib 中值得借鉴的点

Qlib 的 processor 明确区分：

- stateless processor：例如 fill/drop
- fitted processor：例如 `ZScoreNorm`
- label-dependent processor：例如 `DropnaLabel`

Qlib 还在 `ZScoreNorm / MinMaxNorm / RobustZScoreNorm` 中强调：`fit_end_time` 不能包含测试数据。

这是本项目应该吸收的核心纪律。

### 本项目应借鉴什么

本项目应建立 `ProcessorSpec` 或 `FactorTransformSpec`：

```json
{
  "processor_id": "cross_sectional_zscore_v1",
  "processor_type": "fitted",
  "fit_scope": "cross_sectional_by_date",
  "fit_start": "2016-01-01",
  "fit_end": "2020-12-31",
  "apply_start": "2021-01-01",
  "apply_end": "2026-04-30",
  "uses_label": false,
  "allowed_in_runtime": true,
  "fitted_params_hash": "..."
}
```

处理器分级建议：

| 类型 | 说明 | runtime 允许 |
| --- | --- | --- |
| `stateless_runtime` | 不 fit，不用标签，例如缺失值传播、简单 clip | 是 |
| `fitted_runtime` | 有 fit 参数，但 fit 窗口固定且可审计 | 谨慎允许 |
| `learn_only` | 用标签、收益、未来窗口 | 否 |
| `audit_only` | 只生成覆盖率、缺口、诊断 | 可读，不驱动交易 |

### 本项目不应借鉴什么

- 不允许 processor 默认全样本 fit。
- 不允许 fit 参数在回测过程中随 test/audit 窗口更新。
- 不允许 label-dependent processor 输出进入 `signal_view`。
- 不允许同一个 processor 在不同窗口下无版本记录地产生不同结果。

### 落地位置建议

先做标准，不急于实现框架：

- `docs/01_系统接口模块定义/共享层/特征处理器拟合窗口纪律.md`

未来实现位置：

- `backend/core/features/processor_contract.py`
- `backend/research/*_snapshots.py` 中逐步接入 processor metadata

### 验收门槛

- 所有 fitted processor 必须输出 fit window。
- fit window 不得覆盖 hard gate 或 audit evaluation 窗口，除非明确声明为全周期描述性统计且不参与交易决策。
- 产物必须记录 fitted params hash。
- 单测必须覆盖“fit_end 越界即失败”。

## Q5：Recorder / Artifact Template

### Qlib 中值得借鉴的点

Qlib 的 `RecordTemp` 有几个好设计：

- 每类记录有 `artifact_path`
- 每类记录能声明依赖 `depend_cls`
- `check()` 能检查上游产物是否存在
- `list()` 能列出本记录应生成的产物
- `generate()` 只负责生成本记录产物

`SignalRecord -> SigAnaRecord -> PortAnaRecord` 是一个明确的产物依赖链。

### 本项目当前已有基础

本项目已经有：

- `manifest.json`
- `core_artifacts`
- `execution_contract.json`
- `stage_summary.json`
- `execution_lineage_ledger.csv`
- baseline regression contract
- experiment ledger

缺的是：更统一的“产物记录模板”和“依赖检查规范”。

### 本项目应借鉴什么

建议建立本项目自己的 artifact record template：

| Record | 依赖 | 产物 |
| --- | --- | --- |
| `ExecutionContractRecord` | config truth | `execution_contract.json` |
| `SignalDiagnosticsRecord` | signal output | `candidate_diagnostics.csv`、`stage_summary.json` |
| `PortfolioAccountingRecord` | fills/orders | `portfolio_daily.csv`、`portfolio_trades.csv`、`nav.csv` |
| `PerfRecord` | portfolio daily/nav | `perf.json` |
| `AuditRecord` | all above | `research_audit.json`、`execution_lineage_ledger.csv` |
| `BaselineCompareRecord` | audit + baseline contract | baseline regression report |

每个 record 应有：

```json
{
  "record_id": "portfolio_accounting",
  "schema_version": "artifact_record@1",
  "depends_on": ["execution_contract", "fills"],
  "produces": ["portfolio_daily.csv", "portfolio_trades.csv", "nav.csv"],
  "content_hashes": {},
  "blocking_if_missing": true
}
```

### 本项目不应借鉴什么

- 不使用 MLflow 作为当前实验真相。
- 不把 pickle 作为正式可审计产物。
- 不只检查文件存在；必须检查 schema、hash、关键字段。
- 不允许 `skip_existing` 只凭文件存在跳过生成。

### 落地位置建议

先做 record spec 和校验工具：

- `docs/01_系统接口模块定义/共享层/实验产物记录模板.md`

未来实现：

- `backend/core/artifacts/record_template.py`
- `backend/core/artifacts/manifest_validator.py`

### 验收门槛

- 任何核心产物缺失必须 fail fast。
- manifest 中必须有 core artifact 的 schema version 和 hash。
- baseline regression 不能从 ledger-only 指标伪造 artifact。
- 产物模板本身要可回滚，不改变现有 outputs 布局。

## Q6：Strategy / Executor / Exchange / Order 分层

### Qlib 中值得借鉴的点

Qlib 的执行抽象很清楚：

| Qlib | 职责 |
| --- | --- |
| `Strategy` | 生成交易决策 |
| `Executor` | 按交易日/频率推进执行 |
| `Exchange` | 提供价格、涨跌停、成交约束、费用 |
| `Order` | 交易意图与成交结果 |
| `Account / Position` | 账户状态 |

这个分层适合用来对照本项目 stage pipeline，但不适合直接替换。

### 本项目当前对应关系

| 本项目 | Qlib 对照 | 说明 |
| --- | --- | --- |
| S1-S6/S9/S8 | Strategy 前半段 | 候选、过滤、预算、持仓处理 |
| S7 order planning | Strategy 输出 / Order intent | 当前应保持本项目 action intent contract |
| `fill_accounting` / `daily_accounting` | Executor + Account 部分 | 本项目已有 T+1 与会计口径 |
| market data + price limits | Exchange 部分 | 本项目应显式化 execution view |
| `PortfolioState` | Account / Position | 本项目更偏不可变状态快照 |
| `ActionIntentContract` | TradeDecision / Order 前态 | 本项目更适合用于手机端闭环 |

### 本项目应借鉴什么

建议只借鉴边界命名和责任切分：

1. `StrategyIntent`：策略想做什么，不含成交假设。
2. `ExecutionOrder`：执行层接受的订单，含有效日、价格策略、数量单位。
3. `ExchangeConstraint`：涨跌停、停牌、lot、sellable qty、费用、滑点。
4. `FillResult`：实际成交结果，含拒单原因。
5. `AccountingState`：成交后账户状态。

建议本项目未来本地合同：

```json
{
  "order_id": "20260430-000001.SZ-BUY-001",
  "as_of_date": "2026-04-30",
  "execution_date": "2026-05-06",
  "symbol": "000001.sz",
  "side": "BUY",
  "quantity_mode": "target_weight",
  "quantity_value": 0.08,
  "price_policy": "NEXT_OPEN",
  "lot_size": 100,
  "validity": "DAY",
  "source_stage": "S7",
  "reason_codes": ["RANK_SELECTED"]
}
```

### 本项目不应借鉴什么

- 不采用 Qlib 示例常见的 `deal_price: close` 作为默认成交口径。
- 不采用 `TopkDropoutStrategy` 替换当前趋势主线。
- 不采用 Qlib adjusted amount 的订单语义。
- 不采用 Qlib serial/parallel execution 默认行为作为本项目现金口径。
- 不引入嵌套 executor，除非未来做日频到分钟级执行。

### 落地位置建议

短期只做对照文档：

- `docs/01_系统接口模块定义/共享层/执行边界对照.md`

未来如实现，属于 L3：

- `backend/core/execution/order_contract.py`
- `backend/core/execution/exchange_constraints.py`
- `backend/core/execution/fill_result.py`

### 验收门槛

- 必须验证 T+1。
- 必须验证 NEXT_OPEN / POST_CLOSE 时钟。
- 必须验证涨跌停、停牌、交易单位、最小费用、现金不足、sellable qty。
- 必须验证同一 symbol 不允许同日同时 BUY 和 SELL。
- 必须验证手机端 action sheet 不反向污染研究口径。

## 推荐拆解成的本地任务

| 顺序 | 任务 | 等级 | 产出 | 是否改运行口径 |
| --- | --- | --- | --- | --- |
| 1 | 数据视图契约文档 | L1 | `数据视图契约.md` | 否 |
| 2 | 拟合窗口纪律文档 | L1 | `特征处理器拟合窗口纪律.md` | 否 |
| 3 | 产物记录模板 spec | L2 | artifact record schema + manifest validator 计划 | 否 |
| 4 | 安全特征表达式 spec | L2/L3 | 表达式 AST、禁止未来函数规则 | 暂不改 |
| 5 | 执行边界对照文档 | L1 | stage pipeline vs execution abstraction 对照 | 否 |
| 6 | 安全特征表达式最小实现 | L3 | 编译器 + 单测 + 回归 | 可能 |
| 7 | ExecutionOrder / FillResult 合同实现 | L3 | 执行合同扩展 | 是 |

## 当前最值得马上做的不是实现

下一步最合理的是先补三个 spec：

1. `数据视图契约`
2. `特征处理器拟合窗口纪律`
3. `执行边界对照`

这三件事不会改变收益和回测口径，但能把后续 Q1/Q6 的高风险实现约束住。等这些边界清楚后，再决定是否做安全特征表达式引擎。
