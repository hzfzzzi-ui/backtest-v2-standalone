## Context

当前 VECTOR 引擎有两条仿真路径：
1. **SMA 路径**（`run_vector_portfolio_backtest_strict`，约 L313–L887）—— 预计算特征矩阵，向量化信号
2. **Generic 路径**（`_run_vector_portfolio_backtest_generic_signals`，约 L1094–L1300）—— 逐日调用 `strategy.generate_signals()`

两条路径共享相同的订单执行结构（fill at next-day open + 成本计算 + NAV 快照），但目前没有任何恒等式校验。产物层（`stabilize_experiment_result`）输出 perf.json / funnel.csv / run_meta.json 等，但这些面向展示，不面向正确性验证。

目标：在两条路径中插入统一的审计检查点，生成 `audit.json`，供外部 AI 审查回测正确性。

## Goals / Non-Goals

**Goals:**
- 在每个交易日的 fill/NAV/signal 阶段记录恒等式检查结果
- 循环结束后汇总为 audit_summary，包含通过率、价格分布、成本审计、可疑模式标记
- 输出 audit.json 到实验目录，与其他产物（perf.json 等）并列
- 对热循环性能影响可忽略（仅加减法和字典操作）

**Non-Goals:**
- 不在前端 UI 展示审计结果（audit.json 面向外部 AI 消费）
- 不增加用户可配置项（审计检查点始终开启，无开关）
- 不修改已有产物的 schema（audit.json 为纯新增）
- 不做自动化的通过/失败判定（由外部 AI 解读）

## Decisions

### D1: 审计逻辑提取为独立辅助类 `AuditCollector`

**选择**: 新建 `backend/core/engine_vector/audit_collector.py`，封装所有检查点逻辑。

**替代方案**: 直接在仿真循环中内联审计代码。

**理由**: 两条仿真路径（SMA / Generic）结构几乎相同，内联会导致审计逻辑重复两份。提取为独立类后，两条路径只需调用 `collector.record_fills(...)` / `collector.record_nav(...)` / `collector.record_signals(...)` 等方法，保持仿真代码干净。

### D2: "汇总 + 异常日"输出策略

**选择**: audit.json 顶层为 `audit_summary`（全量统计），`flagged_days` 数组仅保留检查失败或有异常成交的交易日完整记录。

**替代方案**: 全量逐日记录。

**理由**: 250 个交易日 × N 笔成交的全量记录可达数百 KB，大部分是重复的"全部通过"。汇总 + 异常日策略既保证 AI 可看到整体健康度，又提供具体证据用于深入分析。典型大小 < 20KB。

### D3: 五个检查点的位置与职责

```
CP1  数据加载后（循环前）
     └─ 价格矩阵统计：NaN 率、日期连续性、复权因子范围、标的数量

CP2  Fill 执行后（循环内，每日）
     └─ 现金守恒：cash_after == cash_before + Σ(sell_net) - Σ(buy_net)
     └─ 持仓守恒：positions_after == positions_before + buys - sells（按标的级别）
     └─ 成交价合理性：fill_price vs open_price 的偏差 == slippage_bps

CP3  NAV 快照后（循环内，每日）
     └─ NAV 一致性：nav == cash + Σ(pos[i] × close[i])
     └─ NAV 非负 / 非 NaN

CP4  信号生成 + 订单构建后（循环内，每日）
     └─ T+1 验证：今日信号排入 pending[next_day]，无同日成交
     └─ 信号→订单追踪：orders_count <= signals_count

CP5  循环结束后（汇总）
     └─ 聚合 CP1–CP4 所有结果
     └─ 价格跳空分布（signal_close → fill_open 的 gap_pct P50/P95/Max）
     └─ 成本审计（总佣金/印花税/滑点，占初始资金比例）
     └─ 可疑模式检测（见 D4）
```

### D4: 可疑模式自动检测

以下模式写入 `flags` 数组（字符串描述 + 严重级别）：

| 模式 | 检测条件 | 级别 |
|------|----------|------|
| 涨跌停成交 | fill_open gap_pct ≥ 9.5%（A股涨跌停 10%） | WARNING |
| 现金负值 | cash < 0 at any point | ERROR |
| 持仓超限 | positions_count > max_positions | ERROR |
| NAV 为 NaN | isnan(nav) | ERROR |
| 策略僵死 | 连续 N 天无信号且有持仓（N=20） | WARNING |
| 单日全换手 | turnover_pct > 100% | WARNING |
| 孤立成交 | trade 的 reason_code 为空 | WARNING |

### D5: 在 stabilize 阶段写入 audit.json

**选择**: 审计数据由引擎返回（附在 `PortfolioBacktestResult.metrics["audit"]` 中），`stabilize_experiment_result` → `ensure_standard_artifacts` 写入 `audit.json`。

**替代方案**: 引擎直接写文件。

**理由**: 保持引擎纯计算、无 IO 副作用的设计原则一致。产物写入统一在 stabilize 阶段完成。

## Risks / Trade-offs

**[性能] 热循环增加字典操作** → 检查点仅做加减法和 dict 赋值，无 IO、无字符串操作。预估对 250 天 × 10 持仓的典型回测增加 < 1ms 总开销。可忽略。

**[正确性] 审计代码本身可能有 bug** → AuditCollector 的核心是恒等式 `a + b == c` 形式的断言，逻辑极简。首次实现后可通过一次回测对比人工计算验证。

**[维护] 两条仿真路径需同步插入** → 通过 AuditCollector 统一接口，两条路径调用相同方法，降低漂移风险。

**[输出体积] 极端情况下 flagged_days 可能很多** → 如果整个回测都有问题（比如价格数据全 NaN），flagged_days 可能包含所有交易日。可设置上限（如最多 50 条 flagged day），超出后只保留 summary 计数。
