## Context

当前回测报告链路由 `stabilize_experiment_result -> run_meta/perf/config/report.html` 组成，前端也可通过 `report.js` 做客户端报告渲染。现状存在三类问题：
1. 口径漂移：报告区间、Universe 数量、策略摘要可能回退到模板配置或不一致字段；
2. 编码质量：服务端报告模板中文文案出现乱码，影响可读性；
3. 观测不足：报告未明确字段来源，出现冲突时难以定位“显示值来自哪里”。

该变更跨越后端产物稳定层、报告生成层与前端报告展示层，属于跨模块一致性修复，必须先统一设计再实施。

## Goals / Non-Goals

**Goals:**
- 建立报告关键字段的统一来源优先级，确保同一 `exp_id` 在概览、报告、产物中口径一致。
- 修复服务端报告中文乱码与 BREAKOUT 参数摘要错误映射。
- 在报告生成过程中引入最小可观测信息（字段来源/冲突标记），支持快速复核。
- 在不改动既有 API 路由的前提下完成修复，保证前端调用兼容。

**Non-Goals:**
- 不重构报告 UI 风格与版式。
- 不新增复杂报告指标（如新增统计模型、归因模块）。
- 不调整回测引擎交易逻辑，仅修复报告与产物口径。

## Decisions

### 决策 1：定义报告字段优先级合同（Report Consistency Contract）
- 决策：对报告核心字段定义统一优先级。
  - 回测区间/基准：优先 `run_config.json.universe`，其次 `config.overrides.original_workbench_config.universe`，最后 `run_meta.data`。
  - Universe 数量：优先 `run_meta.universe.raw_count`（resolver 实际结果），其次 `run_meta.universe.after_filters_symbols`，最后配置层 `symbols.length`。
  - 绩效指标：统一来自 `perf.json`。
  - 漏斗指标：优先 `funnel.csv`，缺失时回退 `run_meta.counters`。
  - 策略摘要：优先 `original_workbench_config.signal_generation`，若缺失回退 `run_config.strategy.params`。
- 备选方案：继续按“就近字段”读取。
- 取舍理由：就近读取实现简单但不可复核；统一合同可稳定多端一致性。

### 决策 2：run_meta 写入改为“最终运行配置回填”
- 决策：`backtest_v2_artifacts` 在写 `run_meta.data` 时，优先读取本次运行的最终配置（即 `run_config` 对应字段），而非 `base_cfg + overrides` 推导。
- 备选方案：保留当前推导方式，在 report 层额外修补。
- 取舍理由：在产物源头修正可避免下游重复补丁，减少未来歧义。

### 决策 3：服务端报告文案统一 UTF-8 常量并清理历史乱码
- 决策：`report_generator.py` 统一替换乱码常量，保持文案中文可读，避免模板污染后续报告。
- 备选方案：仅前端展示层兜底转码。
- 取舍理由：乱码来自服务端模板，应在源头修复；前端兜底无法修复导出 HTML 文件本体。

### 决策 4：BREAKOUT 摘要使用专用映射
- 决策：当策略为 `BREAKOUT_TREND` 时，摘要不再展示 MA 快慢线，改为展示：
  - `breakout_window`
  - `entry_confirm_mode`
  - `entry_delay_mode`
  - `portfolio_mode`
  - 关键退出参数（ATR stop/trail、LOW10）
- 备选方案：继续沿用 MA 通用摘要模板。
- 取舍理由：通用模板导致语义错误，误导研究结论。

### 决策 5：报告增加最小冲突可观测输出
- 决策：在 `run_meta` 或报告附注中记录关键字段来源（如 `source: run_config/funnel/perf`）与冲突策略（fallback 是否触发）。
- 备选方案：不记录来源，仅在代码注释说明。
- 取舍理由：线上问题排查依赖产物自描述，注释无法帮助运行后复核。

## Risks / Trade-offs

- [风险] 历史实验缺少部分产物（如旧实验无 `funnel.csv`）导致新合同下字段缺失。  
  → Mitigation：保留向后兼容 fallback，并在报告中显示“数据来源与缺失状态”。

- [风险] 修复 run_meta 口径后，新旧实验对比时同名字段定义变化。  
  → Mitigation：在 change 文档中声明口径修复时间点，并对历史结果标注“legacy”。

- [风险] 前后端双报告实现（服务端 HTML 与前端 report.js）再次漂移。  
  → Mitigation：抽取统一映射规则并写入 spec，要求双端遵守同一字段合同。

- [风险] 文案批量替换引入新拼写错误。  
  → Mitigation：新增最小报告快照校验（关键标题与字段标签断言）。

## Migration Plan

1. 在 `backtest_v2_artifacts` 修正 `run_meta.data` 来源逻辑，并补充来源标记字段。
2. 在 `report_generator` 落地字段优先级合同，修复乱码和 BREAKOUT 摘要映射。
3. 在 `frontend/report.js` 对齐相同合同（仅映射，不改 UI 行为）。
4. 选取已知问题实验（含冠军配置）回放并重生成报告，做三项校验：
   - 区间与 `run_config` 一致；
   - Universe 数量与 resolver 一致；
   - CAGR/Sharpe/MDD 与 `perf.json` 一致。
5. 回滚策略：若发现兼容性问题，可临时回退到旧字段映射，同时保留 run_meta 来源标记不回退。

## Open Questions

- 是否将“字段来源”展示在最终 HTML 正文，还是仅保存在 `run_meta` 供调试？
- 历史已生成 `report.html` 是否需要批量重算，还是仅对新实验生效？
- 对于 `funnel.csv` 与 `run_meta.counters` 冲突，是否需要在报告中显式展示双值对照？
