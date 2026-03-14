## Context

V9.1 baseline 已经在运行时支持 `strategy.params.breakout_entry_buffer_pct`，并且该参数从语义配置层可以完整编译到 `breakout_signal_provider`。当前缺少的不是策略实现，而是一个可复现、可审计、只允许单一主改动的研究执行入口。

本次变更只针对 `V9.1 baseline` 做实验研究，不修改 baseline 默认值，也不改动主链成交、退出、股票池、成本和报表口径。

## Goals / Non-Goals

**Goals:**
- 提供一个固定锚点的研究脚本，基于 `V9.1 baseline` 运行 `breakout_entry_buffer_pct` 对照实验。
- 在脚本中显式校验配置漂移，确保除 `strategy.params.breakout_entry_buffer_pct` 外不发生其他主改动。
- 输出结构化摘要，便于后续审计、比较和归档。

**Non-Goals:**
- 不修改 `breakout_signal_provider`、`experiment_runner` 或前后端配置协议。
- 不同时引入 entry confirm、delay、trend gate、risk-off 等其他策略变化。
- 不做大规模参数扫描，只做最小可证伪对照。

## Decisions

### 决策 1：复用现有运行时参数，不改策略主链
- 方案：直接基于已有 `breakout_entry_buffer_pct` 参数构造实验变体。
- 原因：参数已经贯通到运行时，实现层再改代码只会增加不必要风险。
- 备选：改 provider 逻辑后再跑实验。
- 不选原因：这会把“参数研究”变成“逻辑重写”，破坏可比性。

### 决策 2：新增独立研究脚本，而不是直接手工改 baseline 配置
- 方案：在 `backend/scripts/` 下新增一个专用研究脚本。
- 原因：脚本可复现、可重复执行、可在代码库中留下实验口径。
- 备选：直接复制 `run_config.json` 手工改值并运行。
- 不选原因：难以审计，也不利于后续对照。

### 决策 3：用配置 diff 审计锁定“单一主改动”
- 方案：脚本运行前比较 baseline 配置与候选配置，只允许 `strategy.params.breakout_entry_buffer_pct` 不同。
- 原因：防止无意改动成本、股票池、执行或退出参数。
- 备选：靠人工肉眼检查。
- 不选原因：不稳健，且容易漏掉嵌套字段漂移。

### 决策 4：最小实验集固定为 baseline、0.5%、1.0%
- 方案：先跑 `0.0 / 0.005 / 0.01` 三组。
- 原因：足够验证“小缓冲带是否改善假突破”这一假设，同时避免一开始做大网格搜索。
- 备选：更细粒度 sweep。
- 不选原因：会引入过度调参风险。

## Risks / Trade-offs

- [Risk] 研究脚本误把 baseline 之外的字段一并改掉
  - Mitigation：在脚本中做嵌套 diff 校验，只放行允许路径。
- [Risk] 只看聚合绩效导致误判
  - Mitigation：摘要同时输出交易数、持仓数和结果目录，后续可继续做阶段切片复核。
- [Risk] 实验结果依赖本地数据库连接参数
  - Mitigation：脚本复用现有研究脚本的数据库环境变量归一化逻辑。
