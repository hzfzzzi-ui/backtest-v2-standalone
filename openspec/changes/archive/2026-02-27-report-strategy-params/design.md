## Context

`generateReport()` 内部的 `buildConfigSummary()` 负责渲染 §6「策略参数」。当前实现只有 8 行表格，且 key 路径全部错误。config.json 有两层数据可用：

```
config.json
├── base_config                  ← 后端原始配置
│   ├── strategy: { name, fast, slow, params: {atr_n, atr_k, trend_ma} }
│   ├── costs: { commission_rate, stamp_tax_rate, slippage_bps }
│   ├── execution: { lot_size, t_plus_one, limit_pct_default }
│   └── universe: { symbols, benchmark }
│
└── overrides
    └── workbench_config         ← UI configDraft 完整快照
        ├── signal_generation: { strategy, sma: {fast_ma, slow_ma, entry_buffer_pct} }
        ├── signal_composition: { enabled, compose_mode, modules: [...] }
        ├── exit_rules: { signal_reverse, atr_stop, trailing, time_exit }
        ├── position_risk: { max_positions, single_stock_cap, industry_cap, lot }
        ├── risk_gate: { enabled, drawdown_threshold, action, cooldown_days }
        ├── exit_priority: [...]
        └── universe: { filters: {...}, price_adj }
```

当通过 UI 运行时 `workbench_config` 存在；通过 API 直接调用时可能不存在。需要做好 fallback。

## Goals / Non-Goals

**Goals:**
- 报告 §6 完整呈现所有策略/风控/执行参数，看报告就能完全复现回测
- 优先从 `workbench_config` 读取（UI 真实设置），缺失时 fallback 到 `base_config`
- 复合信号模块有独立子表

**Non-Goals:**
- 不修改 config.json 的写入逻辑（后端不变）
- 不修改报告其他 section（§1-§5, §7）
- 不新增后端 API

## Decisions

### 决策 1：数据读取优先级

`workbench_config`（wc）优先，`base_config`（bc）兜底。定义一个辅助函数链式读取：

```
读 wc.signal_generation.sma.fast_ma → fallback bc.strategy.fast → 显示 "-"
```

原因：wc 是用户在 UI 上实际配置的值，bc 是后端编译前的原始配置，可能被 overrides 覆盖。

### 决策 2：5 个子表结构

每个子表用独立的 `<h3>` + `<table>` 渲染，而非单一大表。这样视觉层次清晰，也方便打印分页。

### 决策 3：复合信号表的条件渲染

仅当 `wc.signal_composition.enabled === true` 且 `modules.length > 0` 时才渲染复合信号子表。非复合模式下不显示空表。

### 决策 4：百分比字段的显示约定

- 仓位上限（single_stock_cap / industry_cap）：wc 中存的是 0~1 小数 → 显示为百分比
- 回撤阈值（drawdown_threshold）：wc 中存的是 0~1 小数 → 显示为百分比
- 佣金率、印花税率：存的是小数 → 显示为万分比（‱）或千分比（‰）更直观

## Risks / Trade-offs

**[兼容] API 直接调用时无 workbench_config** → fallback 到 base_config，核心字段（策略名、fast/slow）仍可显示。UI 特有字段（退出规则、风控）会显示 "-"，可接受。

**[维护] 字段同步** → 如果后续新增策略参数，需要同时更新 buildConfigSummary。但这是纯前端展示逻辑，改动成本低。
