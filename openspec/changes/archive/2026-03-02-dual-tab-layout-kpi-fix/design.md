## Context

右侧面板当前为上下分割结构：`wb-main-content`（scrollable）+ `wb-dock`（固定 260px）。底部 Dock 包含 Explain/Execution/Logs 三个子标签面板。总高 ~1240px 超过 1080p，Dock 内容被严重压缩。

同时 KPI 面板的卡尔马比率、Top10集中度、评级三个字段后端未计算，始终显示空值。

## Goals / Non-Goals

**Goals:**
- 将上下分割改为顶部 Tab 切换（概览/分析），消除 260px Dock 对概览区的压缩
- 分析 Tab 获得全高空间，信号漏斗/交易明细不再被挤在小窗口
- 修复三个空 KPI 字段的后端计算和前端透传
- 保持所有 DOM ID 不变，最小化对 artifacts.js/charts.js/report.js 等文件的影响

**Non-Goals:**
- 不改变概览 Tab 内部的内容排列（KPI 数量、图表高度等保持不变）
- 不重新设计 KPI 卡片样式
- 不改变评级算法的复杂度（用简单分级规则即可）

## Decisions

### D1: Tab 位置选择 — 顶部独立行

Tab Bar 放在 `wb-main` 的最顶部，命令栏下方，占 ~36px 高度。

理由：与左侧 drawer 的模块 Tab 风格一致，用户视线自然从上到下扫描。虽然多占 36px，但消除 260px Dock 后净增 224px。

### D2: 分析 Tab 保留子标签

分析 Tab 内部保留 [Explain] [Execution] [Logs] 三个子标签，复用原 Dock 的切换逻辑。

理由：三类信息性质不同（诊断/执行/日志），全部平铺会过长。子标签给用户清晰的信息层次。

### D3: DOM ID 保持不变

`wbDockExplain`、`wbDockExecution`、`wbDockLogs`、`wbFunnel`、`wbTriggers`、`wbTradesList` 等 ID 全部保留。

理由：artifacts.js、charts.js、report.js 通过 `byId()` 操作这些 DOM 节点。保持 ID 不变意味着这些文件零改动。

### D4: Calmar 计算位置 — portfolio_builder._compute_metrics()

在已有 cagr 和 max_drawdown 的位置直接计算 `calmar = cagr / abs(max_drawdown)`。

### D5: Top10 集中度计算位置 — experiment_runner.py

从 trade_rows（已序列化为 CSV/list）按 symbol 聚合利润，取 Top10 利润占比。放在 experiment_runner 而非 portfolio_builder，因为需要完整 trade 列表且只在结果汇总时计算一次。

### D6: 评级规则 — 简单四级

```
T1: sharpe >= 1.0 且 max_dd > -20% 且 calmar >= 1.0
T2: sharpe >= 0.5 且 max_dd > -30%
T3: sharpe >= 0.0
T4: 其他
```

### D7: HTML 结构

```
<main class="wb-main">
  <div class="wb-main-tabs">                    ← 新增
    <button class="active" data-main-tab="overview">概览</button>
    <button data-main-tab="analysis">分析</button>
  </div>
  <div class="wb-main-panel active" id="wbTabOverview">
    <!-- 原 wb-main-content 内容不变 -->
  </div>
  <div class="wb-main-panel" id="wbTabAnalysis">
    <div class="wb-analysis-tabs">              ← 原 dock-tabs 提升
      <button class="active" data-dock="explain">Explain</button>
      <button data-dock="execution">Execution</button>
      <button data-dock="logs">Logs</button>
    </div>
    <div class="wb-analysis-body">
      <div id="wbDockExplain" class="wb-dock-panel active">...</div>
      <div id="wbDockExecution" class="wb-dock-panel">...</div>
      <div id="wbDockLogs" class="wb-dock-panel">...</div>
    </div>
  </div>
</main>
```

## Risks / Trade-offs

- **不能同时看图表和日志**：原 Dock 理论上可同时显示，但 260px 实际体验极差。分 Tab 后每个视图都更舒适，整体更优。
- **Tab 切换增加一步操作**：用户需点击切换。可在回测完成后自动定位到概览 Tab，减少摩擦。
- **评级规则主观性**：T1-T4 阈值为经验值，后续可通过配置调整。当前先固化简单规则。
