## Why

回测报告的 §6「策略参数」几乎全部显示"-"。`buildConfigSummary()` 读的 key 路径（`bc.position_risk`、`bc.signal`、`bc.exit`）与 config.json 的实际结构完全不匹配。同时，信号策略核心参数（快慢线、ATR、趋势过滤）、退出规则、复合信号配置、选股过滤条件、成本假设等关键信息从未被写入报告，导致报告缺乏可复现性 — 看了报告无法知道"这个回测到底用了什么策略"。

## What Changes

- 重写 `buildConfigSummary()` 函数，正确读取 `config.json` 中 `base_config` 和 `overrides.workbench_config` 两层数据
- 将原来的单一 8 行表格，拆分为 5 个子表：
  1. **信号策略** — 策略名、快慢线周期、ATR 窗口/倍数、趋势过滤 MA、入场缓冲
  2. **退出规则** — 反转退出/ATR 止损/追踪止损/时间退出各自的 enabled + 参数 + 退出优先级
  3. **仓位与风控** — 最大持仓、单票上限、行业上限、手数、现金策略、风险门（回撤阈值/动作/冷却）
  4. **选股范围** — 模式（CUSTOM/ALL_A/INDUSTRY）、标的数、过滤条件（ST/停牌/上市天数/成交额/价格区间/ATR 波动/涨跌停规则）、价格口径
  5. **执行假设** — 佣金率、印花税率、滑点 bps、手数、T+1、成交假设
- 如果使用了复合信号（signal_composition.enabled），额外渲染一个复合信号子表，列出各模块的 name/role/weight/priority

## Capabilities

### New Capabilities
- `backtest-report-export`: 回测报告导出的完整策略参数展示

### Modified Capabilities
（无已有 spec 需要修改）

## Impact

- **前端**：`frontend/assets/js/backtest_v2.js` — 仅 `buildConfigSummary()` 函数（~15 行 → ~100 行）
- **后端**：无变更（数据已全部存在 config.json 中）
- **产物协议**：无变更（不新增文件，只修改报告 HTML 的渲染逻辑）
