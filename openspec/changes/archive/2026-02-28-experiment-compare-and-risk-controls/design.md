## Context

当前回测工作台已完成代码拆分（前端 6 个 JS 模块 + 后端 6 个 Python 子模块），交易成本已接入 VECTOR 引擎。系统有完整的实验历史和产物存储，但缺少多实验对比能力和高级风控机制。

引擎退出优先级链（当前）：
```
风控退出 > 趋势破位 > ATR止损 > ATR追踪止损 > 时间退出 > 信号反转
```

仓位计算公式（当前）：
```
qty = floor(nav / max_positions × order_value_scale × mf_scale / price) // lot_size × lot_size
```

## Goals / Non-Goals

**Goals:**
- G1: 用户可在历史面板勾选 2-5 个实验进行 KPI 对比 + NAV 曲线叠加
- G2: 引擎支持止盈退出（固定百分比 / ATR 倍数）
- G3: 引擎支持固定百分比止损
- G4: 引擎支持 ATR 反比波动率调仓
- G5: 引擎支持组合级回撤熔断
- G6: 所有新增规则有完整的 reason_code + 计数器 + 前端展示

**Non-Goals:**
- 参数网格搜索 / 自动优化（单独 change）
- 行业集中度限制（后续 change）
- 风险平价 / Kelly 公式（高级，后续）
- 多实验 Level 3 深度对比（漏斗差异、个股重叠，后续）

## Decisions

### D1: 多实验对比用独立弹窗，不改变主面板
**选择**：对比视图作为覆盖层（overlay modal）出现，不嵌入现有面板结构。

**理由**：
- 现有右侧面板已紧凑，嵌入对比表会打乱布局
- 弹窗可以全宽展示多列 KPI + 图表
- 关闭后回到原始状态，无副作用

**替代方案**：Tab 切换模式（在 dock 区域加"对比"tab）— 拒绝，因为 dock 高度有限

### D2: 对比 API 批量读取，避免 N 次请求
**选择**：新增 `POST /api/backtest_v2/experiments/compare` 端点，一次返回多个实验的 perf + nav。

**理由**：
- 前端逐个调用 artifact_read 需要 N×2 次请求（perf + nav），延迟高
- 批量端点在后端并行读取文件，响应更快

### D3: 止盈排在 ATR 止损之后
**选择**：退出优先级更新为：
```
风控退出 > 趋势破位 > ATR止损 / 固定止损 > 止盈 > 时间退出 > 信号反转
```

**理由**：
- 止损是保护性退出，优先级应高于止盈
- 同一天如果同时触发止损和止盈（极端行情），保护性退出优先
- ATR 止损和固定止损同级，先触发者生效

### D4: 波动率调仓在 build_rebalance_orders 中实现
**选择**：在 `portfolio_builder.py` 的 `build_rebalance_orders()` 中，`calc_lot_qty` 之前插入 ATR 调仓逻辑。

**理由**：
- 仓位计算集中在 portfolio_builder，不应该分散到策略层
- ATR 数据已通过 signal.meta 传递（引擎在信号生成时已计算 ATR）
- 不改变策略接口，只改变下单金额

**替代方案**：在 portfolio_simulator_strict.py 的热循环中计算 — 拒绝，order building 逻辑应保持在 builder 层

### D5: 回撤熔断在模拟循环中计算
**选择**：在 `portfolio_simulator_strict.py` 的日循环中，每日更新 NAV 峰值和回撤比例，在买入判断前检查熔断状态。

**理由**：
- 回撤是组合级指标，必须在持仓模拟中逐日计算
- 不能放在策略层（策略不知道组合状态）
- 在 `buy_slots` 计算之前检查，如果熔断则 `buy_slots = 0`

### D6: 配置结构扩展
**选择**：在 `models.py` 的 `ExitConfig`（新增）中集中所有退出配置，在 `SizingConfig` 中加波动率调仓，在 `RiskConfig`（新增）中加回撤熔断。

```python
class ExitConfig:
    enable_take_profit: bool = False
    take_profit_mode: str = "pct"       # "pct" | "atr"
    take_profit_pct: float = 0.10       # 10%
    take_profit_atr_k: float = 3.0
    enable_fixed_stop_loss: bool = False
    fixed_stop_loss_pct: float = 0.05   # 5%

class RiskConfig:
    enable_drawdown_breaker: bool = False
    drawdown_breaker_pct: float = 0.15      # -15% 触发
    drawdown_breaker_recover_pct: float = 0.10  # -10% 恢复

# SizingConfig 扩展
class SizingConfig:
    ...existing fields...
    enable_volatility_sizing: bool = False
    vol_target_risk_pct: float = 0.02   # 2%
```

### D7: 前端配置编译路径
**选择**：复用现有 `_build_runtime_cfg_from_workbench()` 函数，将新增 UI 字段映射到上述配置结构。

字段映射：
- `wbExitTakeProfit` checkbox → `exit.enable_take_profit`
- `wbTakeProfitMode` select → `exit.take_profit_mode`
- `wbTakeProfitPct` input → `exit.take_profit_pct`
- `wbTakeProfitAtrK` input → `exit.take_profit_atr_k`
- `wbExitFixedStop` checkbox → `exit.enable_fixed_stop_loss`
- `wbFixedStopPct` input → `exit.fixed_stop_loss_pct`
- `wbVolSizing` checkbox → `sizing.enable_volatility_sizing`
- `wbVolRiskPct` input → `sizing.vol_target_risk_pct`
- `wbDrawdownBreaker` checkbox → `risk.enable_drawdown_breaker`
- `wbDrawdownBreakerPct` input → `risk.drawdown_breaker_pct`
- `wbDrawdownRecoverPct` input → `risk.drawdown_breaker_recover_pct`

## Risks / Trade-offs

- **[风险] 退出优先级变更可能影响现有回测结果** → 缓解：新增退出规则默认全部关闭，不改变默认行为
- **[风险] 波动率调仓在高波动市场可能导致仓位过小** → 缓解：设置下限（target × 0.3），保证最小仓位
- **[风险] 回撤熔断恢复阈值 < 触发阈值时逻辑正确性** → 缓解：前端校验 recover_pct < breaker_pct
- **[权衡] 批量对比 API vs 前端并行请求** → 选择批量 API，牺牲一点后端复杂度换取前端简洁
- **[权衡] 对比视图复杂度** → Level 1 + Level 2 先做，Level 3（漏斗/个股对比）后续
